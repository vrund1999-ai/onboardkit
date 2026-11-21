from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from onboardkit.datagen.mess.base import (
    MessContext,
    MessEvent,
    MessType,
    SourceDataset,
    flatten,
    group_by_table,
)
from onboardkit.datagen.mess.engine import MessContractError, run_mess
from onboardkit.datagen.mess.noop import NoopMess
from onboardkit.datagen.mess.registry import DEFAULT_REGISTRY, MessRegistry
from onboardkit.datagen.sources.base import SourceRow, TruthRefs
from onboardkit.datagen.truth.builder import build_firm
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import load_profile

FIRM = build_firm(load_profile(), 3, 5)
AS_OF = date(2025, 12, 31)


def make_data() -> SourceDataset:
    def row(uid: str, **values: object) -> SourceRow:
        return SourceRow(row_uid=uid, source="crm", table="contacts", values=dict(values))

    return {
        "crm": {
            "contacts": [
                row(
                    "crm:contacts:1",
                    **{"person.first_name": "Wesley", "person.last_name": "Arnold"},
                ),
                row(
                    "crm:contacts:2", **{"person.first_name": "Bruce", "person.last_name": "Arnold"}
                ),
            ]
        }
    }


def ctx_for(firm: TruthFirm = FIRM, seed: int = 5) -> Callable[[MessType], MessContext]:
    def factory(mess: MessType) -> MessContext:
        return MessContext(mess.name, mess.max_rate, seed, firm, AS_OF)

    return factory


def refs() -> TruthRefs:
    return TruthRefs()


class Renamer:
    """Changes a first name and explains it."""

    name = "renamer"
    description = "test"
    touches = frozenset({"person.first_name"})
    structural = False
    max_rate = 1.0

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        row = data["crm"]["contacts"][0]
        before = str(row.values["person.first_name"])
        row.values["person.first_name"] = "Wes"
        return [
            ctx.event(
                subtype="nickname",
                source="crm",
                table="contacts",
                row_uids=(row.row_uid,),
                effect="entity_variant",
                refs=refs(),
                concept="person.first_name",
                before=before,
                after="Wes",
            )
        ]


class Undeclared(Renamer):
    name = "undeclared"
    touches = frozenset({"person.first_name"})

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        events = super().apply(ctx, data)
        data["crm"]["contacts"][1].values["person.last_name"] = "Changed"
        return events


class Silent(Renamer):
    name = "silent"

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        data["crm"]["contacts"][0].values["person.first_name"] = "Wes"
        return []


class Remover(Renamer):
    name = "remover"
    touches = frozenset[str]()

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        data["crm"]["contacts"].pop()
        return []


class StructuralRemover(Renamer):
    name = "structural_remover"
    structural = True

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        gone = data["crm"]["contacts"].pop()
        return [
            ctx.event(
                subtype="drop",
                source="crm",
                table="contacts",
                row_uids=(gone.row_uid,),
                effect="structural",
                refs=refs(),
            )
        ]


class UnexplainedStructural(StructuralRemover):
    name = "unexplained_structural"

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        data["crm"]["contacts"].pop()
        return []


class BadIds(Renamer):
    name = "bad_ids"

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        return [replace(event, event_id="wrong-id") for event in super().apply(ctx, data)]


class Drawer:
    """Draws two numbers from its own stream and records them; touches nothing."""

    description = "test"
    touches = frozenset[str]()
    structural = False
    max_rate = 1.0

    def __init__(self, name: str) -> None:
        self.name = name

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        rng = ctx.rng("crm")
        return [
            ctx.event(
                subtype=f"draw-{n}",
                source="crm",
                table="contacts",
                row_uids=(),
                effect="format_variant",
                refs=refs(),
                after=str(rng.random()),
            )
            for n in range(2)
        ]


class DrawA(Drawer):
    def __init__(self) -> None:
        super().__init__("draw_a")


class DrawB(Drawer):
    def __init__(self) -> None:
        super().__init__("draw_b")


def registry_with(*types: Any) -> MessRegistry:
    registry = MessRegistry()
    for cls in types:
        registry.register(cls)
    return registry


def test_registered_type_runs_and_returns_events_in_stable_order() -> None:
    registry = registry_with(DrawA, DrawB)
    first = run_mess(make_data(), ["draw_b", "draw_a"], ctx_for(), registry)
    again = run_mess(make_data(), ["draw_a", "draw_b"], ctx_for(), registry)
    assert first == again
    assert [e.event_id for e in first] == [
        "mess:draw_a:1",
        "mess:draw_a:2",
        "mess:draw_b:1",
        "mess:draw_b:2",
    ]


def test_valid_change_with_event_passes_and_applies() -> None:
    data = make_data()
    events = run_mess(data, ["renamer"], ctx_for(), registry_with(Renamer))
    assert data["crm"]["contacts"][0].values["person.first_name"] == "Wes"
    assert events[0].before == "Wesley"
    assert events[0].after == "Wes"


def test_undeclared_concept_fails_with_clear_message() -> None:
    with pytest.raises(MessContractError, match=r"undeclared concept 'person.last_name'.*row"):
        run_mess(make_data(), ["undeclared"], ctx_for(), registry_with(Undeclared))


def test_change_without_event_fails() -> None:
    with pytest.raises(MessContractError, match="without emitting an event"):
        run_mess(make_data(), ["silent"], ctx_for(), registry_with(Silent))


def test_non_structural_row_removal_fails() -> None:
    with pytest.raises(MessContractError, match="not structural but removed row"):
        run_mess(make_data(), ["remover"], ctx_for(), registry_with(Remover))


def test_structural_removal_needs_an_event() -> None:
    data = make_data()
    run_mess(data, ["structural_remover"], ctx_for(), registry_with(StructuralRemover))
    assert len(data["crm"]["contacts"]) == 1
    with pytest.raises(MessContractError, match="row set"):
        run_mess(
            make_data(),
            ["unexplained_structural"],
            ctx_for(),
            registry_with(UnexplainedStructural),
        )


def test_event_ids_must_be_sequential_and_named_for_the_type() -> None:
    with pytest.raises(MessContractError, match="sequential event ids"):
        run_mess(make_data(), ["bad_ids"], ctx_for(), registry_with(BadIds))


def test_streams_are_independent_between_types() -> None:
    registry = registry_with(DrawA, DrawB)
    alone = run_mess(make_data(), ["draw_a"], ctx_for(), registry)
    both = run_mess(make_data(), ["draw_a", "draw_b"], ctx_for(), registry)
    assert [e for e in both if e.mess_type == "draw_a"] == alone
    b_events = [e for e in both if e.mess_type == "draw_b"]
    assert [e.after for e in b_events] != [e.after for e in alone]


def test_engine_does_not_mutate_truth() -> None:
    before = FIRM.model_dump_json()
    run_mess(make_data(), ["renamer"], ctx_for(), registry_with(Renamer))
    assert FIRM.model_dump_json() == before


def test_unknown_type_lists_valid_names() -> None:
    with pytest.raises(KeyError, match=r"unknown mess type 'nope'.*renamer"):
        run_mess(make_data(), ["nope"], ctx_for(), registry_with(Renamer))


def test_structural_types_run_before_value_types() -> None:
    registry = registry_with(Renamer, StructuralRemover)
    ordered = [m.name for m in registry.ordered(["renamer", "structural_remover"])]
    assert ordered == ["structural_remover", "renamer"]


def test_canonical_order_among_value_types() -> None:
    class Balances(Drawer):
        def __init__(self) -> None:
            super().__init__("balances")

    class Names(Drawer):
        def __init__(self) -> None:
            super().__init__("names")

    registry = registry_with(Balances, Names, DrawA)
    assert [m.name for m in registry.ordered(["draw_a", "balances", "names"])] == [
        "names",
        "balances",
        "draw_a",
    ]


def test_duplicate_registration_is_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):
        registry_with(Renamer, Renamer)


def test_noop_changes_nothing_and_default_registry_stays_clean() -> None:
    registry = registry_with(NoopMess)
    data = make_data()
    assert run_mess(data, ["noop"], ctx_for(), registry) == []
    assert "noop" not in DEFAULT_REGISTRY.names()


def test_context_streams_are_seeded_per_type_and_source() -> None:
    one = MessContext("names", 0.1, 7, FIRM, AS_OF)
    two = MessContext("names", 0.1, 7, FIRM, AS_OF)
    other = MessContext("formats", 0.1, 7, FIRM, AS_OF)
    assert one.rng("crm").random() == two.rng("crm").random()
    assert one.rng("crm") is one.rng("crm")
    assert two.rng("custodian").random() != other.rng("custodian").random()


def test_group_by_table_and_flatten_round_trip() -> None:
    data = make_data()
    flat = flatten(data)
    assert group_by_table(flat) == data
