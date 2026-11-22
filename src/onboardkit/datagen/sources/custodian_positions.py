"""The custodian's position report: one row per holding of every account it exports.

Same house style as the account master (shouted upper case, preamble and trailer lines, a byte
order mark), but a separate file, as a real custodian delivers positions.
"""

from __future__ import annotations

from datetime import date

from onboardkit.datagen.sources.base import ColumnSpec, SourceRow, TableSpec, TruthRefs
from onboardkit.datagen.truth.model import TruthFirm
from onboardkit.datagen.truth.profile import AssetClass

SOURCE = "custodian"
TABLE = "positions"
FILE_NAME = "custodian_positions.csv"

ASSET_CLASS_CODES = {
    AssetClass.EQUITY.value: "EQ",
    AssetClass.FIXED_INCOME.value: "FI",
    AssetClass.FUND.value: "FUND",
    AssetClass.CASH.value: "CASH",
}


def positions_table(custodian_name: str, as_of_date: date, record_count: int = 0) -> TableSpec:
    """The position file's layout. ``record_count`` fills the trailer line."""
    return TableSpec(
        name=TABLE,
        file_name=FILE_NAME,
        columns=[
            ColumnSpec(concept="holding.account_number", header="Acct #"),
            ColumnSpec(concept="holding.security_symbol", header="Symbol", formatter="upper"),
            ColumnSpec(
                concept="holding.security_name",
                header="Security Description",
                formatter="upper",
            ),
            ColumnSpec(
                concept="holding.asset_class",
                header="Asset Class",
                formatter="map",
                options={"mapping": ASSET_CLASS_CODES},
            ),
            ColumnSpec(
                concept="holding.quantity",
                header="Quantity",
                formatter="decimal",
                options={"places": 4, "commas": True},
            ),
            ColumnSpec(
                concept="holding.price",
                header="Price",
                formatter="decimal",
                options={"places": 4},
            ),
            ColumnSpec(
                concept="holding.value",
                header="Market Value",
                formatter="money",
                options={"style": "commas"},
            ),
            ColumnSpec(
                concept="holding.as_of",
                header="Price Date",
                formatter="date",
                options={"pattern": "%Y%m%d"},
            ),
        ],
        preamble=[
            f"{custodian_name.upper()} - POSITION REPORT",
            f"Report date: {as_of_date.strftime('%m/%d/%Y')}",
        ],
        trailer=[f"Total positions: {record_count}"],
    )


def project_positions(firm: TruthFirm) -> list[SourceRow]:
    """One row per truth holding."""
    accounts = {a.account_id: a for a in firm.accounts}
    securities = {s.security_id: s for s in firm.securities}
    rows: list[SourceRow] = []
    for holding in firm.holdings:
        security = securities[holding.security_id]
        rows.append(
            SourceRow(
                row_uid=f"{SOURCE}:{TABLE}:{holding.holding_id.removeprefix('HOLD-')}",
                source=SOURCE,
                table=TABLE,
                values={
                    "holding.account_number": accounts[holding.account_id].account_number,
                    "holding.security_symbol": security.symbol,
                    "holding.security_name": security.name,
                    "holding.asset_class": security.asset_class,
                    "holding.quantity": holding.quantity,
                    "holding.price": security.price,
                    "holding.value": holding.value,
                    "holding.as_of": firm.as_of_date,
                },
                refs=TruthRefs(holding_id=holding.holding_id),
            )
        )
    return rows
