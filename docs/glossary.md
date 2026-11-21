# Glossary

The words onboardkit uses, and what they mean. Definitions are in plain language and describe meaning, not data structures: the common data model arrives in milestone M1.

**How to read an entry**

- **Definition**: what the term means here.
- **Also known as**: other spellings and synonyms seen in real exports and conversations.
- **Not to be confused with**: a nearby term that means something different.
- **Code name**: the identifier used in code, when one exists.

**Linking rule.** In new documents, link the first mention of a glossary term to its entry. Every entry has a stable anchor, which is its heading in lower case with spaces replaced by hyphens, for example `glossary.md#account-number`.

**Adding terms.** Keep entries in alphabetical order. Add a term when a later milestone introduces it.

Jump to: [A](#a) · [B](#b) · [C](#c) · [D](#d) · [E](#e) · [F](#f) · [G](#g) · [H](#h) · [I](#i) · [L](#l) · [M](#m) · [N](#n) · [P](#p) · [R](#r) · [S](#s) · [T](#t)

## A

### account
**Definition:** A holding of money or investments at a custodian, owned by one or more people in a household, for example a joint brokerage account or a Roth IRA.
**Also known as:** portfolio, position group, holding account.
**Not to be confused with:** a user account or login.
**Code name:** `account`, `account_id` (internal identifier).

### account number
**Definition:** The identifier the custodian gives an account. It is the main key for finding the same account in different sources.
**Also known as:** `Acct #`, `Acct No`, `Account No.`, `account_number`, `AcctNo`, `acct_num`.
**Not to be confused with:** the internal account identifier (`account_id`) used in the truth, which never appears in an export.
**Code name:** `account_number`. In M0 it is the prefix `MC` followed by six digits.

### account status
**Definition:** Whether an account is `open`, `closed`, or `restricted`.
**Also known as:** status, `Acct Status`, `OPEN` / `CLOSED` / `RESTRICTED`.
**Not to be confused with:** the review status of a mapping or match, which is a later-milestone concept.
**Code name:** `account_status`.

### account type
**Definition:** The kind of account, such as individual brokerage, joint brokerage, traditional IRA, Roth IRA, rollover IRA, or 529 education account.
**Also known as:** `Acct Type`, `Type`, short forms such as `IND`, `JNT`, `TIRA`, `ROTH`, `RIRA`, `Indiv`, `Joint`.
**Not to be confused with:** the registration title, which is the legal name on the account.
**Code name:** `account_type`.

### advisor
**Definition:** The firm's professional who looks after a household. Each household has exactly one advisor.
**Also known as:** financial advisor, planner, rep, relationship manager.
**Not to be confused with:** the reviewer, the person who checks suggestions during onboarding.
**Code name:** `advisor`.

### alias
**Definition:** A source's own identifier for something in the common data model, kept so the same thing can be found by any source's name for it, for example a CRM contact id for a client.
**Also known as:** source key, source id, external id.
**Not to be confused with:** the model's own identifier, which no source ever uses.
**Code name:** `alias`.

### answer key
**Definition:** A file that records the correct answer to one onboarding question for a particular dataset: which rows are the same entity (entity match key), what each column means (column mapping key), or which discrepancies really exist (discrepancy key). Answer keys are used to score the product.
**Also known as:** gold labels, expected results.
**Not to be confused with:** the [truth](#truth), which is the underlying clean picture of the firm. Answer keys are derived from the truth plus a record of what was done to the data.
**Code name:** `answer_keys` (package), files under `truth/`.

### archetype
**Definition:** A standard shape of household used to build the fictional firm, such as single adult, couple, or couple with dependents.
**Also known as:** household type, household shape.
**Not to be confused with:** a household role, which describes one person within a household.
**Code name:** `archetype`.

### as-of date
**Definition:** The date a value is true for. For a dataset it is the fixed reporting date (2025-12-31 for the standard datasets); for a balance it is the date of the valuation.
**Also known as:** valuation date, report date, `Value As Of`, `balance_as_of`.
**Not to be confused with:** the date a file was generated. Nothing in the generator depends on the current date.
**Code name:** `as_of_date`, `balance_as_of`.

### audit trail
**Definition:** The permanent record of who decided what, when, and why for every mapping, merge, split, and override, so any output can be traced back to its source and the decisions that shaped it.
**Also known as:** decision log, audit log.
**Not to be confused with:** lineage, which tracks where a value came from rather than who decided what.
**Code name:** not yet defined (milestone M3).

## B

### balance
**Definition:** The amount of money in an account on a given date.
**Also known as:** market value, `Market Value`, `Bal`, `Balance`, current value, account value, `total_value`.
**Not to be confused with:** a cash balance, which is only the uninvested part of an account.
**Code name:** `balance` (see also [market value](#market-value)).

### beneficiary
**Definition:** The person an account is held for or will pass to. In the fictional firm this is used for 529 education accounts, where a child is the beneficiary and an adult is the owner.
**Also known as:** designated beneficiary.
**Not to be confused with:** an owner, who controls the account.
**Code name:** `beneficiary_id`.

### book of business
**Definition:** The firm's own list of its clients and accounts, usually a hand-maintained spreadsheet. In this project, one of the three sources, and the lowest priority.
**Also known as:** BoB, client list, client tracker, `Book of Business`.
**Not to be confused with:** the custodian's account list or the CRM.
**Code name:** `book_of_business`.

## C

### client
**Definition:** A person the firm serves. A client belongs to exactly one household. People in a household who are not the account owner, such as children, are still clients of the firm for data purposes.
**Also known as:** customer, contact (in a CRM), investor, member, owner (when named on an account).
**Not to be confused with:** the household, which is the unit the firm plans for. One household has one or more clients.
**Code name:** `person`, `person_id`.

### common data model
**Definition:** The single, clean structure that all sources are converted into: firms, households, clients, accounts, balances, securities, and holdings, with consistent facts. It is described in [data-model.md](data-model.md).
**Also known as:** canonical model, target schema, unified model.
**Not to be confused with:** the truth, which is the generator's private picture of the fictional firm, or the concept catalogue, which describes source columns for scoring.
**Code name:** `onboardkit.model` (milestone M1).

### concept
**Definition:** A stable identifier for the meaning of a column, written as `entity.attribute`, for example `account.number` or `person.date_of_birth`. Different sources use different headers for the same concept.
**Also known as:** semantic type, field meaning.
**Not to be confused with:** a column header (the text a source writes) or a database column in the future common data model.
**Code name:** `concept` (ids in `concepts.yaml`).

### confidence
**Definition:** How sure the model or a rule is about a suggested mapping or match, as a number from 0 to 1. Suggestions below a firm's threshold are sent to a person.
**Also known as:** score, certainty.
**Not to be confused with:** intensity, which is a dial for how much mess is generated.
**Code name:** `confidence` (milestone M2).

### coverage
**Definition:** How much of the firm each source contains. Full coverage means every record appears; partial coverage means some are missing. Coverage is one source of discrepancies.
**Also known as:** completeness, overlap.
**Not to be confused with:** test coverage, which measures how much code the tests run.
**Code name:** `coverage`, `CoverageConfig`.

### CRM
**Definition:** Customer relationship management system. The firm's record of people, contact details, households, and advisors. In this project one of the three sources, and the default source of truth for people data.
**Also known as:** client database, contact manager. In the fictional firm: Cedarline CRM.
**Not to be confused with:** the custodian, which holds the assets.
**Code name:** `crm`.

### custodian
**Definition:** The institution that holds clients' assets and reports on them. In this project one of the three sources, and the default source of truth for balances, holdings, account status, and registration.
**Also known as:** clearing firm, broker-dealer, bank. In the fictional firm: Meridian Custody Services.
**Not to be confused with:** the advisor, who gives advice but does not hold the assets.
**Code name:** `custodian`.

### custodian export
**Definition:** The account file produced by the custodian: one row per account, with registration, type, status, open date, balance, and owner names.
**Also known as:** account master, custodian file, `custodian_accounts.csv`.
**Not to be confused with:** a statement sent to a client.
**Code name:** `custodian` (source), table `accounts`.

## D

### dataset
**Definition:** One complete generated set of data for the fictional firm: the exports, the truth, and a manifest, all produced from one configuration.
**Also known as:** generated dataset, test data set.
**Not to be confused with:** a source file, which is only one part of a dataset.
**Code name:** `dataset_id`, a folder under `data/generated/`.

### discrepancy
**Definition:** A real disagreement between sources: a record present in one but missing in another, or a value (balance, status, type, registration) that differs.
**Also known as:** break, mismatch, difference.
**Not to be confused with:** a format difference such as `03/04/1980` versus `1980-03-04`, which is the same value written differently. See also [exception](#exception).
**Code name:** `discrepancy`.

### duplicate household
**Definition:** The same real household entered more than once in a source, usually with slightly different names or identifiers.
**Also known as:** duplicate record, double entry.
**Not to be confused with:** a split household, where one household is divided across records.
**Code name:** mess subtype `duplicate`.

## E

### entity match
**Definition:** A decision that two or more rows, possibly from different sources, describe the same real person, household, or account.
**Also known as:** record linkage, deduplication, match.
**Not to be confused with:** a column mapping, which is about columns rather than rows.
**Code name:** `entity_match`.

### exception
**Definition:** A discrepancy or problem that has been raised for someone to look at and resolve, with a type and severity. Exceptions are tracked in the reconciliation milestone.
**Also known as:** break, issue, flag.
**Not to be confused with:** a software exception (an error raised in code).
**Code name:** `exception` (milestone M4).

### export
**Definition:** A file a source system or person produces for use outside it, such as a CSV or Excel file. The files onboardkit ingests are exports.
**Also known as:** extract, dump, report file, download.
**Not to be confused with:** the common data model, which is what exports are converted into.
**Code name:** files under `exports/`.

## F

### firm
**Definition:** The advisor firm whose data is being onboarded. Everything in the common data model belongs to exactly one firm, and data from different firms is never mixed.
**Also known as:** advisor firm, RIA, practice, tenant.
**Not to be confused with:** the custodian or CRM vendor, which are source systems the firm uses.
**Code name:** `firm`.

## G

### ground truth
See [truth](#truth).

## H

### holding
**Definition:** An amount of one security held in one account on a date, as reported by one source, for example 120 shares of a fund.
**Also known as:** position, `Positions`, security position, lot (a finer detail not modelled in M1).
**Not to be confused with:** a balance, which is the value of the whole account.
**Code name:** `holding`, `holding_id` (internal identifier).

### household
**Definition:** The group of people the firm plans for together, such as a couple and their children. A household has one advisor and one or more clients.
**Also known as:** family, relationship, group, client group, account family.
**Not to be confused with:** a client, who is one person.
**Code name:** `household`, `household_id`.

### household role
**Definition:** A person's place within a household: `primary` (the lead adult), `spouse`, or `dependent` (a child).
**Also known as:** relationship, member type, `Primary` / `Spouse` / `Dependent`.
**Not to be confused with:** an account owner, who is defined per account.
**Code name:** `household_role`.

## I

### intensity
**Definition:** A number from 0 to 1 saying how much of one kind of mess to generate. 0 is none; 1 is the maximum rate for that kind of mess.
**Also known as:** mess level, dial. Shorthand words: `off`, `light`, `moderate`, `heavy`, `max`.
**Not to be confused with:** confidence, which describes certainty about a suggestion.
**Code name:** `intensity`.

## L

### lineage
**Definition:** The trail from a value in the cleaned data back to the original file, sheet, and row it came from.
**Also known as:** traceability, data lineage.
**Not to be confused with:** provenance, which in this project is the generator's internal record of where each exported row landed and which truth entities it stands for.
**Code name:** not yet defined (milestone M1).

## M

### manifest
**Definition:** A small file that describes a dataset: its configuration, the generator version, and a checksum for every file, so it can be verified and regenerated.
**Also known as:** dataset descriptor, checksum list.
**Not to be confused with:** a shipping or packing manifest.
**Code name:** `manifest.json`.

### mapping
**Definition:** The decision that a column in a source file means a particular concept, for example that `AcctNo` means account number.
**Also known as:** column mapping, field mapping, schema mapping.
**Not to be confused with:** an entity match, which is about rows.
**Code name:** `column_mapping`.

### market value
**Definition:** What the assets in an account are worth on the valuation date. The custodian's term for the balance.
**Also known as:** `Market Value`, `MV`, account value.
**Not to be confused with:** cost basis, what was originally paid.
**Code name:** the concept `account.balance`.

### merge
**Definition:** Combining several records that describe the same entity into one. A merge always follows an entity match and, when confidence is low, a person's approval.
**Also known as:** consolidate, dedupe, combine.
**Not to be confused with:** a split household, which divides one household over several records.
**Code name:** `merge`.

### mess
**Definition:** Deliberate, recorded imperfections added to the generated exports so that onboarding can be tested: naming variants, duplicate or split households, mixed formats, and mismatched balances.
**Also known as:** noise, dirty data, data quality problems.
**Not to be confused with:** random noise with no explanation. Every piece of mess is logged.
**Code name:** `mess`.

### mess type
**Definition:** One kind of mess that can be switched on or off and dialed up or down, such as names, households, formats, or balances.
**Also known as:** mess family.
**Not to be confused with:** a mess subtype, a specific variation within a type (for example `nickname` within names).
**Code name:** `MessType`.

### missing household
**Definition:** A household whose records lack the household grouping, so the people appear as isolated contacts, or a household that is absent from a source altogether.
**Also known as:** orphan contacts, unassigned clients.
**Not to be confused with:** a record omitted by coverage, which can affect any record type.
**Code name:** mess subtype `missing`.

## N

### naming variant
**Definition:** A different way of writing the same person's or household's name, such as a nickname, an initial, a suffix, or a different order.
**Also known as:** name variation, alias, `J. Smith` versus `John Smith Jr.`.
**Not to be confused with:** two different people with similar names.
**Code name:** mess type `names`.

### normalization
**Definition:** Rewriting values from different formats into one consistent form, such as one date format or one account number style.
**Also known as:** standardization, cleaning, canonicalization.
**Not to be confused with:** mapping, which decides what a column means.
**Code name:** not yet defined (milestone M1).

## P

### preset
**Definition:** A named bundle of settings for generating a dataset, such as `clean`, `typical`, or `nightmare`.
**Also known as:** profile, scenario, configuration template.
**Not to be confused with:** a seed, which only controls random choices.
**Code name:** `preset`.

### provenance
**Definition:** The generator's internal record of where each exported row ended up (file, sheet, row number) and which true people, households, and accounts it refers to.
**Also known as:** row origin, source record.
**Not to be confused with:** lineage, which is the product-side trail from cleaned data back to source rows.
**Code name:** `provenance.csv`.

## R

### reconciliation
**Definition:** Comparing the sources against each other to find where they disagree, so differences can be resolved.
**Also known as:** recon, tie-out, cross-check.
**Not to be confused with:** an entity match, which decides whether records are the same thing rather than whether their values agree.
**Code name:** `reconciliation`.

### registration title
**Definition:** The legal name on an account, built from the owners and the account type, for example `JANE B SMITH ROTH IRA`.
**Also known as:** registration, account title, `Account Title`, account name.
**Not to be confused with:** the household name.
**Code name:** `registration_title`.

## S

### security
**Definition:** Something that can be held in an account, such as a stock, a bond, a fund, or cash.
**Also known as:** instrument, asset, investment, ticker (the short code).
**Not to be confused with:** security in the sense of access control or secrets.
**Code name:** `security`, `security_id` (internal identifier).

### seed
**Definition:** The number that fixes the random choices in the generator, so the same seed and settings always produce the same data.
**Also known as:** random seed.
**Not to be confused with:** a preset, which sets how much mess to create.
**Code name:** `seed`.

### severity
**Definition:** How much an exception matters, for example low, medium, or high. High-severity exceptions are the ones shown on a client-ready report.
**Also known as:** priority, materiality.
**Not to be confused with:** confidence, which describes certainty about a suggestion.
**Code name:** `severity` (milestone M4).

### sheet
**Definition:** One tab in an Excel workbook. The book of business has a sheet per advisor and an archive sheet.
**Also known as:** worksheet, tab.
**Not to be confused with:** a file.
**Code name:** `sheet`.

### source record
**Definition:** The original row of a source file that a value in the common data model came from, identified by source, file, sheet, and row, with its original text.
**Also known as:** source row, origin row.
**Not to be confused with:** provenance, the generator's own record of where each exported row landed.
**Code name:** `source_record`.

### source system
**Definition:** A system or file that holds some of the firm's data: in this project the custodian, the CRM, and the book of business.
**Also known as:** source, system of record (when it is the trusted one).
**Not to be confused with:** the target data model the sources are converted into.
**Code name:** `source`.

### source of truth
**Definition:** The source trusted when sources disagree about a kind of data. By default the custodian wins for money data (balances, status, registration) and the CRM wins for people data, and a firm can change this.
**Also known as:** system of record, golden source, authoritative source.
**Not to be confused with:** the [truth](#truth), the generator's private clean picture of the fictional firm.
**Code name:** `source_priority` (milestone M4).

### split household
**Definition:** One real household divided across several records in a source, for example a spouse recorded under a separate household.
**Also known as:** fragmented household, separated record.
**Not to be confused with:** a duplicate household, where the whole household is repeated.
**Code name:** mess subtype `split`.

### synthetic data
**Definition:** Data generated by the project that looks realistic but describes no real person, firm, or account. All data in this repository is synthetic.
**Also known as:** fake data, test data, mock data.
**Not to be confused with:** anonymized real data, which is not used here.
**Code name:** `datagen` (package).

### standardized value
**Definition:** A value after [normalization](#normalization): rewritten into the common form, and stored together with the original text it came from.
**Also known as:** clean value, normalized value.
**Not to be confused with:** a matched or merged value, which involves deciding that two records are the same.
**Code name:** not yet defined (milestone M1).

## T

### tolerance
**Definition:** The size of difference below which two values are treated as agreeing, for example a rounding difference of a few cents. Differences within tolerance are immaterial; larger ones are material.
**Also known as:** threshold, materiality threshold.
**Not to be confused with:** a confidence threshold, which decides what is applied automatically.
**Code name:** `tolerance`.

### truth
**Definition:** The complete and correct picture of the fictional firm as it was generated, before any source-specific formatting, omissions, or mess: the real people, households, and accounts and their true values. It is internal to the project and never part of an export.
**Also known as:** ground truth, the clean firm.
**Not to be confused with:** an [answer key](#answer-key), which is derived from the truth and the record of what was done to the data in order to score one specific task. The truth says what is real; an answer key says what the right answer is for a given question about a given dataset.
**Code name:** `TruthFirm`, `truth/firm.json`.
