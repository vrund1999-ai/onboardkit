"""The custodian source: Meridian Custody Services' account master file.

Flat, one row per account, upper case, no household concept. The system of record for balances,
status, and registration.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from onboardkit.datagen.sources.base import (
    ColumnSpec,
    SourceProfile,
    SourceRow,
    TableSpec,
    TruthRefs,
    WriteResult,
)
from onboardkit.datagen.sources.formatters import NameParts
from onboardkit.datagen.sources.writers import write_csv_tables
from onboardkit.datagen.truth.model import TruthFirm, TruthPerson
from onboardkit.datagen.truth.profile import AccountType

SOURCE = "custodian"
TABLE = "accounts"
FILE_NAME = "custodian_accounts.csv"

ACCOUNT_TYPE_CODES = {
    AccountType.INDIVIDUAL.value: "IND",
    AccountType.JOINT.value: "JNT",
    AccountType.TRADITIONAL_IRA.value: "TIRA",
    AccountType.ROTH_IRA.value: "ROTH",
    AccountType.ROLLOVER_IRA.value: "RIRA",
    AccountType.EDUCATION_529.value: "529",
}

_LAST_FIRST_UPPER = {"upper": True}


def _columns() -> list[ColumnSpec]:
    return [
        ColumnSpec(concept="account.number", header="Acct #"),
        ColumnSpec(concept="account.registration", header="Account Title", formatter="upper"),
        ColumnSpec(
            concept="account.type",
            header="Acct Type",
            formatter="map",
            options={"mapping": ACCOUNT_TYPE_CODES},
        ),
        ColumnSpec(concept="account.status", header="Status", formatter="upper"),
        ColumnSpec(
            concept="account.open_date",
            header="Open Date",
            formatter="date",
            options={"pattern": "%m/%d/%Y"},
        ),
        ColumnSpec(
            concept="account.balance",
            header="Market Value",
            formatter="money",
            options={"style": "commas"},
        ),
        ColumnSpec(
            concept="account.balance_as_of",
            header="Value As Of",
            formatter="date",
            options={"pattern": "%Y%m%d"},
        ),
        ColumnSpec(
            concept="account.owner_names",
            header="Owner 1",
            formatter="name_last_first",
            options={**_LAST_FIRST_UPPER, "index": 0},
        ),
        ColumnSpec(
            concept="account.owner_names",
            header="Owner 2",
            formatter="name_last_first",
            options={**_LAST_FIRST_UPPER, "index": 1},
        ),
        ColumnSpec(concept="person.address_line1", header="Mail Addr"),
        ColumnSpec(concept="person.tax_id_last4", header="TIN Last4"),
    ]


def build_profile(custodian_name: str, as_of_date: date, record_count: int = 0) -> SourceProfile:
    """The custodian's file conventions. ``record_count`` fills the trailer line."""
    table = TableSpec(
        name=TABLE,
        file_name=FILE_NAME,
        columns=_columns(),
        preamble=[
            f"{custodian_name.upper()} - ACCOUNT MASTER",
            f"Report date: {as_of_date.strftime('%m/%d/%Y')}",
        ],
        trailer=[f"Total records: {record_count}"],
    )
    return SourceProfile(
        source=SOURCE,
        file_type="csv",
        encoding="utf-8-sig",
        delimiter=",",
        line_ending="\r\n",
        quoting="all",
        tables=[table],
    )


def _mailing_address(person: TruthPerson) -> str:
    return (
        f"{person.address_line1}, {person.address_city}, "
        f"{person.address_state} {person.address_postal}"
    )


def _name(person: TruthPerson) -> NameParts:
    return NameParts(
        first=person.first_name,
        last=person.last_name,
        middle=person.middle_initial,
        suffix=person.suffix,
    )


class CustodianExporter:
    """Projects the truth into the custodian's account master and writes it."""

    def __init__(self, custodian_name: str, as_of_date: date) -> None:
        self.custodian_name = custodian_name
        self.as_of_date = as_of_date
        self.profile = build_profile(custodian_name, as_of_date)

    @classmethod
    def for_firm(cls, firm: TruthFirm) -> CustodianExporter:
        return cls(firm.profile.firm.custodian, firm.as_of_date)

    def project(self, firm: TruthFirm) -> list[SourceRow]:
        """One row per truth account. Mailing address and tax id come from the first owner."""
        people = firm.people_by_id()
        rows: list[SourceRow] = []
        for account in firm.accounts:
            owners = [people[owner_id] for owner_id in account.owner_ids]
            first_owner = owners[0]
            rows.append(
                SourceRow(
                    row_uid=f"{SOURCE}:{TABLE}:{account.account_id.removeprefix('ACCT-')}",
                    source=SOURCE,
                    table=TABLE,
                    values={
                        "account.number": account.account_number,
                        "account.registration": account.registration_title,
                        "account.type": account.account_type,
                        "account.status": account.status,
                        "account.open_date": account.open_date,
                        "account.balance": account.balance,
                        "account.balance_as_of": account.balance_as_of,
                        "account.owner_names": [_name(owner) for owner in owners],
                        "person.address_line1": _mailing_address(first_owner),
                        "person.tax_id_last4": first_owner.tax_id_last4,
                    },
                    refs=TruthRefs(
                        person_ids=tuple(owner.person_id for owner in owners),
                        household_id=account.household_id,
                        account_id=account.account_id,
                    ),
                )
            )
        return rows

    def write(self, rows: list[SourceRow], out_dir: Path) -> WriteResult:
        """Write the file; the trailer counts the rows actually written."""
        profile = build_profile(self.custodian_name, self.as_of_date, record_count=len(rows))
        return write_csv_tables(profile, rows, out_dir)
