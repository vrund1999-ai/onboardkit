# E3-S5: Format and identifier mess

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | M |
| **Depends on** | E3-S1, E3-S2 |
| **Blocks** | E3-S7 |

## User story

As a contributor, I want mixed date formats and inconsistent identifiers inside the exports, so that normalization can be tested on realistic format problems.

## Context

The README calls out dates in multiple formats and account numbers that differ by source (`Acct #`, `account_number`, `AcctNo`). Each source has a default format (E2). This mess type makes a share of values within a column deviate from that default, the way hand-edited data does. The value is the same, only its textual form differs, so these events do not change meaning.

## Scope

**In scope**
- A `formats` mess type covering dates, account numbers, phone numbers, state values, and text-typed money in the book of business.
- A `RawText` value wrapper so writers emit a pre-formatted string verbatim.

**Out of scope**
- Changes in the actual amount or date (E3-S6).
- Encoding corruption.

## Technical design

### `RawText`

Add to `sources/base.py`:

```python
@dataclass(frozen=True)
class RawText:
    text: str
    original: Any      # the typed value it replaced
```

Writers (`write_csv`, the XLSX writer) output `RawText.text` unchanged, bypassing the column formatter. This story updates the writers and their tests. Answer keys read `original` to know the true value.

### Mess type

`name = "formats"`, `max_rate = 0.40`, `structural = False`,
`touches = {"person.date_of_birth", "person.client_since", "account.open_date", "meta.review_date", "account.number", "person.phone", "person.address_state", "account.balance"}`.

### Subtypes

| Subtype | Concept | Example | Ambiguity |
|---|---|---|---|
| `date_alt_format` | any date | `1980-03-04` to `03/04/1980`, `4 Mar 1980`, `March 4, 1980`, `04.03.1980` | low |
| `date_two_digit_year` | any date | `03/04/80` | medium |
| `date_day_month_swap` | any date | `04/03/1980` meaning 4 March in a US-format column | high |
| `acct_separators` | `account.number` | `12345678` to `1234-5678` or `1234 5678` | low |
| `acct_leading_zeros` | `account.number` | `00123456` to `123456` | medium |
| `acct_prefix_case` | `account.number` | `AB123456` to `ab123456`, or a stray trailing space | low |
| `phone_style` | `person.phone` | `(555) 010-1234` to `555.010.1234` or `+1 555 010 1234` | low |
| `state_full_name` | `person.address_state` | `NY` to `New York` | low |
| `money_text` | `account.balance` (book of business) | `120000` to `$120k`, `120,000.00 `, `~120000` | medium |

Selection: rate applies per eligible value; the subtype list is filtered by the concept's type. Weights favor the low-ambiguity subtypes.

### Rules

- Each concept's deviating values are bounded so the default format stays the majority (the rate is capped at 0.5 for any single column).
- `date_day_month_swap` is only emitted when the day is 12 or lower, otherwise the value would be unambiguously invalid; this is the intended trap, labelled `high`.
- Variants must be parseable by a careful human; `money_text` does not use words.
- Account numbers must stay unique per source after variation; reject variants that collide.

### Events

`effect = "format_variant"`, with `before` and `after` as text, `ambiguity` as in the table. Events carry the `original` typed value as text so normalization can be scored.

## Files to create or change

- `src/onboardkit/datagen/sources/base.py` (add `RawText`)
- `src/onboardkit/datagen/sources/writers.py` (pass `RawText` through)
- `src/onboardkit/datagen/mess/formats.py`
- `tests/datagen/mess/test_formats.py`, `tests/datagen/sources/test_rawtext.py`

## Acceptance criteria

- [ ] Writers emit `RawText.text` verbatim in CSV and XLSX.
- [ ] At intensity 0, no values change.
- [ ] A dataset at high intensity contains at least three different date formats in the CRM date-of-birth column.
- [ ] README example headers `Acct #`, `account_number`, and `AcctNo` remain unchanged (header mess is not in scope).
- [ ] `date_day_month_swap` only occurs when the day is 12 or lower and always carries `ambiguity = high`.
- [ ] Account numbers remain unique within each source.
- [ ] Majority-format rule holds per column.

## Test plan

- Table-driven tests per subtype.
- Parse-back test: each variant, parsed by a reference parser per format, yields the original date (except flagged ambiguous ones).
- Uniqueness test for account numbers after variation.

## Risks and notes

- `RawText` slightly widens the E2-S1 writer interface; changes there should be minimal and covered by the existing tests.
- Excel stores real dates as serial numbers; format mess in the workbook is expressed as text cells in the date column, which is realistic.
