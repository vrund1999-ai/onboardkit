"""The CRM source: Cedarline CRM's contacts and linked accounts.

Tidy and machine-friendly: ``snake_case`` headers, ISO dates, separate name parts. The system of
record for people data. Its own identifiers carry no relation to the truth identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from onboardkit.datagen.rng import derive_rng
from onboardkit.datagen.sources.base import (
    ColumnSpec,
    SourceProfile,
    SourceRow,
    TableSpec,
    TruthRefs,
    WriteResult,
)
from onboardkit.datagen.sources.writers import write_csv_tables
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import AccountType

SOURCE = "crm"
CONTACTS = "contacts"
LINKED_ACCOUNTS = "linked_accounts"

ROLE_LABELS = {"primary": "Primary", "spouse": "Spouse", "dependent": "Dependent"}
ACCOUNT_TYPE_LABELS = {
    AccountType.INDIVIDUAL.value: "Individual Brokerage",
    AccountType.JOINT.value: "Joint Brokerage",
    AccountType.TRADITIONAL_IRA.value: "Traditional IRA",
    AccountType.ROTH_IRA.value: "Roth IRA",
    AccountType.ROLLOVER_IRA.value: "Rollover IRA",
    AccountType.EDUCATION_529.value: "529 Education",
}


def _iso_date(concept: str, header: str) -> ColumnSpec:
    return ColumnSpec(concept=concept, header=header, formatter="date")


def build_profile() -> SourceProfile:
    contacts = TableSpec(
        name=CONTACTS,
        file_name="crm_contacts.csv",
        columns=[
            ColumnSpec(concept="person.source_id", header="contact_id"),
            ColumnSpec(concept="person.first_name", header="first_name"),
            ColumnSpec(concept="person.last_name", header="last_name"),
            ColumnSpec(concept="person.suffix", header="suffix"),
            _iso_date("person.date_of_birth", "date_of_birth"),
            ColumnSpec(concept="person.email", header="email"),
            ColumnSpec(concept="person.phone", header="phone", formatter="phone"),
            ColumnSpec(concept="person.address_line1", header="street"),
            ColumnSpec(concept="person.address_city", header="city"),
            ColumnSpec(concept="person.address_state", header="state"),
            ColumnSpec(concept="person.address_postal", header="zip"),
            ColumnSpec(concept="household.source_id", header="household_id"),
            ColumnSpec(concept="household.name", header="household_name"),
            ColumnSpec(
                concept="person.household_role",
                header="household_role",
                formatter="map",
                options={"mapping": ROLE_LABELS},
            ),
            ColumnSpec(concept="household.advisor", header="advisor"),
            _iso_date("person.client_since", "client_since"),
        ],
    )
    linked = TableSpec(
        name=LINKED_ACCOUNTS,
        file_name="crm_linked_accounts.csv",
        columns=[
            ColumnSpec(concept="person.source_id", header="contact_id"),
            ColumnSpec(concept="account.number", header="account_number"),
            ColumnSpec(
                concept="account.type",
                header="account_type",
                formatter="map",
                options={"mapping": ACCOUNT_TYPE_LABELS},
            ),
        ],
    )
    return SourceProfile(
        source=SOURCE,
        file_type="csv",
        encoding="utf-8",
        delimiter=",",
        line_ending="\n",
        quoting="minimal",
        tables=[contacts, linked],
    )


@dataclass
class CrmIdMaps:
    """Truth id to CRM id, kept for the answer keys. Never written to the export directory."""

    person: dict[str, str] = field(default_factory=dict)
    household: dict[str, str] = field(default_factory=dict)


class CrmExporter:
    """Projects the truth into the CRM's two tables and writes them."""

    def __init__(self) -> None:
        self.profile = build_profile()
        self.id_maps = CrmIdMaps()

    def project(self, firm: TruthFirm) -> list[SourceRow]:
        """One contact row per person; one link row per owner of each account."""
        rng = derive_rng(firm.root_seed, "crm", "source_ids")
        contact_numbers = rng.sample(range(100_000, 1_000_000), k=len(firm.people))
        household_numbers = rng.sample(range(1_000, 10_000), k=len(firm.households))
        self.id_maps = CrmIdMaps(
            person={
                p.person_id: f"C{n:06d}" for p, n in zip(firm.people, contact_numbers, strict=True)
            },
            household={
                h.household_id: f"H{n:04d}"
                for h, n in zip(firm.households, household_numbers, strict=True)
            },
        )
        households = firm.households_by_id()

        rows: list[SourceRow] = []
        for person in firm.people:
            household = households[person.household_id]
            rows.append(
                SourceRow(
                    row_uid=f"{SOURCE}:{CONTACTS}:{person.person_id.removeprefix('P-')}",
                    source=SOURCE,
                    table=CONTACTS,
                    values={
                        "person.source_id": self.id_maps.person[person.person_id],
                        "person.first_name": person.first_name,
                        "person.last_name": person.last_name,
                        "person.suffix": person.suffix,
                        "person.date_of_birth": person.date_of_birth,
                        "person.email": person.email,
                        "person.phone": person.phone,
                        "person.address_line1": person.address_line1,
                        "person.address_city": person.address_city,
                        "person.address_state": person.address_state,
                        "person.address_postal": person.address_postal,
                        "household.source_id": self.id_maps.household[household.household_id],
                        "household.name": household.display_name,
                        "person.household_role": person.household_role,
                        "household.advisor": household.advisor,
                        "person.client_since": household.client_since,
                    },
                    refs=TruthRefs(
                        person_ids=(person.person_id,), household_id=household.household_id
                    ),
                )
            )

        link_number = 0
        for account in firm.accounts:
            for owner_id in account.owner_ids:
                link_number += 1
                rows.append(
                    SourceRow(
                        row_uid=f"{SOURCE}:{LINKED_ACCOUNTS}:{link_number:06d}",
                        source=SOURCE,
                        table=LINKED_ACCOUNTS,
                        values={
                            "person.source_id": self.id_maps.person[owner_id],
                            "account.number": account.account_number,
                            "account.type": account.account_type,
                        },
                        refs=TruthRefs(
                            person_ids=(owner_id,),
                            household_id=account.household_id,
                            account_id=account.account_id,
                        ),
                    )
                )
        return rows

    def write(self, rows: list[SourceRow], out_dir: Path) -> WriteResult:
        return write_csv_tables(self.profile, rows, out_dir)
