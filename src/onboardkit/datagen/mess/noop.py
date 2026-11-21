"""A mess type that does nothing. Used in tests and as a template; it is not registered."""

from __future__ import annotations

from onboardkit.datagen.mess.base import MessContext, MessEvent, SourceDataset


class NoopMess:
    name = "noop"
    description = "Changes nothing."
    touches: frozenset[str] = frozenset()
    structural = False
    max_rate = 0.0

    def apply(self, ctx: MessContext, data: SourceDataset) -> list[MessEvent]:
        return []
