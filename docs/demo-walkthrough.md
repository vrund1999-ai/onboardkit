# Demo walkthrough

A guided tour of the generated data: what each file holds, where the mess is, and how the answer key relates to the exports. About 15 minutes. All data is synthetic.

Examples below come from the `sample` dataset (preset `typical`, seed 42, generator 0.2.0). A test regenerates it and checks that every quoted line still exists, so if the generator changes, the build tells you to update this page. Set up first with the [getting started guide](getting-started.md).

## 1. Generate the datasets

Two standard datasets are used everywhere: a small `sample` and a larger `demo`. `--overwrite` replaces a dataset you already generated.

```bash
uv run onboardkit-gen generate --preset typical --size sample --seed 42 --overwrite
uv run onboardkit-gen generate --preset typical --size default --seed 42 --overwrite
```

The first makes `data/generated/typical-sample-s42-937ab0dd` (15 households), the second the full-size firm. The rest of this page uses the small one; every identifier you see is fictional.

```powershell
$d = "data/generated/typical-sample-s42-937ab0dd"
```

```bash
d=data/generated/typical-sample-s42-937ab0dd
```

## 2. Tour the exports

`exports/` is what a real firm would send: three systems that describe the same clients in three different ways.

### Custodian: `exports/custodian/custodian_accounts.csv`

The account master from the company that holds the money.

```quote exports/custodian/custodian_accounts.csv
"MERIDIAN CUSTODY SERVICES - ACCOUNT MASTER"
"Report date: 12/31/2025"
"Acct #","Account Title","Acct Type","Status","Open Date","Market Value","Value As Of","Owner 1","Owner 2","Mail Addr","TIN Last4"
"MC143753","BRUCE ARNOLD INDIVIDUAL","IND","OPEN","12/12/2023","18,497.87","20251231","ARNOLD, BRUCE"
"Total records: 43"
```

Notice: a title line and a report date before the header, a trailer line after the data, upper case names, `Acct #` for the account number, American dates (`12/12/2023`) next to compact ones (`20251231`), and balances with thousands separators. Only the last four digits of the tax id exist.

### CRM: `exports/crm/crm_contacts.csv` and `crm_linked_accounts.csv`

The advisors' contact system: one row per person.

```quote exports/crm/crm_contacts.csv
contact_id,first_name,last_name,suffix,date_of_birth,email,phone,street,city,state,zip,household_id,household_name,household_role,advisor,client_since
C896101,Bruce,Arnold,,1985-03-31,bruce.arnold80@example.com,(355) 555-0184,92017 Daniel Road Suite 681
```

```quote exports/crm/crm_linked_accounts.csv
contact_id,account_number,account_type
C896101,MC143753,Individual Brokerage
```

Notice: snake case headers, ISO dates, `example.com` emails and `555-01xx` phone numbers (reserved for fiction), `account_number` instead of `Acct #`, and a separate file linking people to accounts.

### Book of business: `exports/book_of_business/book_of_business.xlsx`

An advisor-maintained workbook: a summary sheet, one sheet per advisor, and an archive sheet.

```quote exports/book_of_business/book_of_business.xlsx
Lantern Ridge Wealth Partners - Book of Business
Advisor: Hannah Brecker
Household | Advisor | AcctNo | Type | Balance | Notes | Last Review
Arnold, Wesley & Bruce | Hannah Brecker | MC143753 | Indiv | 1849.79
```

Notice: title rows above the header, households named once with blank cells for the rows below them, blank spacer rows, `AcctNo`, balances rounded to hundreds (or typed as text such as `$171,600`), and free-text notes like `Closed per client`.

## 3. Find the mess

| Problem | Where to look | How to spot it |
|---|---|---|
| Column names differ | The account number column in all three sources | `Acct #`, `account_number`, `AcctNo` |
| Same client, several spellings | Custodian owners versus CRM names | `SMITH, A. C` for Alicia C Smith, `Joy Williams` stored as first name `Williams`, last name `Joy` |
| Duplicated or split households | CRM household columns | Ashley Hines appears twice with households `H2243` and `H4894` |
| Multiple date formats | CRM date of birth and the book's review dates | `31 Dec 1953` and `10/10/60` next to ISO dates |
| Balances do not match | Custodian versus book of business | One account is 18,497.87 in the custodian and 1849.79 in the book |
| Identifier formats differ | Account numbers across sources | `MC159-591` and `MC159591` for one account |

Check each with the quoted lines:

```quote exports/custodian/custodian_accounts.csv
"MC159-591","KAITLYN S SMITH INDIVIDUAL"
"SMITH, A. C"
```

```quote exports/crm/crm_contacts.csv
C954694,Kaitlyn,Smith,,1960-01-02
C825642,Alicia,Smith,,31 Dec 1953
C189871,Edward,Moore,Jr.,10/10/60
C958916,Williams,Joy,,1951-10-11
C862499,Ashley,Hines,,14 Aug 1976
C708817,Ashley,Hines,,1976-08-14
```

```quote exports/crm/crm_linked_accounts.csv
C954694,MC159591,Individual Brokerage
```

You can search for them yourself:

```bash
grep -n "Hines" $d/exports/crm/crm_contacts.csv
grep -n "MC143753" $d/exports/custodian/custodian_accounts.csv
```

```powershell
Select-String "Hines" $d/exports/crm/crm_contacts.csv
Select-String "MC143753" $d/exports/custodian/custodian_accounts.csv
```

## 4. Look behind the curtain

`truth/` is the answer key: what the data was generated from and exactly what was done to it. **It is internal.** A real firm never sends it, and nothing that ingests, maps, matches or reconciles exports may read it. It exists to score a product's answers.

| File | Answers |
|---|---|
| `entity_matches.csv` | Which rows in which files are the same person, account or household |
| `entity_groups.csv` | The same, one row per entity, with how hard it is to match |
| `mess_events.jsonl` | Every mess that was applied, with before and after values |
| `discrepancies.csv` | Every disagreement between sources and which source is authoritative |
| `column_mappings.csv` | What each column in each export means |
| `provenance.csv`, `source_id_map.csv` | Where each row came from, and each source's identifier for each entity |
| `coverage_events.jsonl`, `entities_not_exported.csv` | What was left out of which source |

Follow Bruce Arnold's account `MC143753` into the key. Its truth id is `ACCT-000001`, and the key lists one row in each source for it:

```quote truth/entity_matches.csv
account,ACCT-000001,book_of_business:accounts:000001,book_of_business,book_of_business/book_of_business.xlsx,Advisor - Hannah Brecker,6,easy,
account,ACCT-000001,crm:linked_accounts:000001,crm,crm/crm_linked_accounts.csv,,2,easy,
account,ACCT-000001,custodian:accounts:000001,custodian,custodian/custodian_accounts.csv,,4,easy,
```

The balance mismatch from section 3 is recorded as a discrepancy, naming the custodian as authoritative and the event that caused it:

```quote truth/discrepancies.csv
D-000023,value_conflict,account,ACCT-000001,account.balance,book_of_business|custodian,custodian,18497.87,book_of_business=1849.79,material,mess:balances:1
```

## 5. Turn the dial

The same seed with different presets changes only how messy the data is:

```bash
uv run onboardkit-gen presets
uv run onboardkit-gen generate --preset clean --size sample --seed 42 --overwrite
uv run onboardkit-gen generate --preset nightmare --size sample --seed 42 --overwrite
uv run onboardkit-gen show data/generated/clean-sample-s42-b3bb40be
```

(`show` prints the real dataset id; use the ids the `generate` commands print.) `clean` has complete sources and no mess (0 mess events), `typical` is realistic (90 mess events, 19 coverage gaps), and `nightmare` has gaps and heavy mess of every kind (161 mess events, 40 coverage gaps). The row counts in `generate`'s output show the gaps: the clean CRM has 75 rows, the typical one 70, the nightmare one 64. Individual kinds can be set on top of a preset:

```bash
uv run onboardkit-gen generate --preset typical --size sample --seed 42 --mess names=heavy --mess balances=off
```

## 6. Verify and reproduce

```bash
uv run onboardkit-gen verify data/generated/typical-sample-s42-937ab0dd
uv run onboardkit-gen check data/generated/typical-sample-s42-937ab0dd
uv run onboardkit-gen generate --preset typical --size sample --seed 42 --out data/generated/again
```

`verify` recomputes every checksum against `manifest.json`. `check` confirms the answer key is consistent with the exports and that no truth identifier leaked into them. The third command regenerates the dataset elsewhere; it gets the same dataset id and identical files.
