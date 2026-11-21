# E3-S3: Name mess

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../epics/m0-foundation-epics.md#e3-controllable-mess) |
| **Size** | M |
| **Depends on** | E3-S1, E3-S2 |
| **Blocks** | E3-S7 |

## User story

As a contributor, I want realistic naming variants of the same person across and within sources, so that entity matching can be tested on cases such as `J. Smith` versus `John Smith Jr.`.

## Context

The README names this problem directly. The same client appears with nicknames, initials, suffixes, different ordering, and typos. Variants must remain resolvable by a careful human, and each event records how hard the match is so later evaluation can report accuracy by difficulty.

## Scope

**In scope**
- A `names` mess type with several subtypes.
- A bundled nickname table and suffix list.
- Ambiguity labelling on each event.

**Out of scope**
- Household name mess (E3-S4).
- Transliteration, non-Latin scripts.

## Technical design

### Mess type

`name = "names"`, `touches = {"person.first_name", "person.last_name", "person.suffix", "account.owner_names", "account.registration", "household.name"}`, `structural = False`, `max_rate = 0.35`.

Eligible rows: any row containing a touched concept. A row is selected with probability `rate`; one subtype is then chosen by weight.

### Subtypes

| Subtype | Example | Weight | Ambiguity |
|---|---|---|---|
| `nickname` | Robert Smith to Bob Smith | 0.25 | low |
| `initial_only` | John Smith to J. Smith | 0.20 | medium |
| `suffix_change` | John Smith to John Smith Jr., or drop `Jr.` | 0.10 | medium |
| `order_swap` | John Smith to Smith, John (in a source that normally writes First Last) | 0.15 | low |
| `case_change` | JOHN SMITH to John Smith, or all lower | 0.10 | low |
| `typo` | Smith to Smyth, Smtih; single edit | 0.10 | medium |
| `hyphen_or_maiden` | Jane Brown to Jane Brown-Smith | 0.05 | high |
| `whitespace_punct` | extra spaces, trailing period, `John  Smith` | 0.05 | low |

Rules:
- A value never changes in two ways in one pass.
- `typo` uses a single insertion, deletion, substitution, or adjacent transposition, and never alters the first letter of a surname (keeps it human-recoverable).
- `nickname` uses a bundled table (`nicknames.yaml`) of about 60 common mappings; if a name has none, fall back to `initial_only`.
- For `account.owner_names`, which is a list, mutate one element.
- The variant must differ from the original; otherwise skip silently.
- Name parts and full names stay consistent within a row: if `first_name` changes, `full_name` in the same row is updated too, and both appear in the event (one event per concept changed).

### Events

`effect = "entity_variant"`, `refs` carries the person ids, `ambiguity` as in the table. Where a variant makes two *different* people look alike (for example `J. Smith` in a household with `John Smith` and `Jane Smith`), set `ambiguity = "high"`.

## Files to create or change

- `src/onboardkit/datagen/mess/names.py`
- `src/onboardkit/datagen/mess/data/nicknames.yaml`
- `tests/datagen/mess/test_names.py`

## Acceptance criteria

- [x] At intensity 0 the type changes nothing and emits no events.
- [x] At the configured rate, the share of affected eligible rows is within 5 percentage points of `intensity * max_rate` on the 300-household dataset.
- [x] Every subtype in the table is producible and appears in a test dataset at high intensity.
- [x] No variant equals the original value.
- [x] `typo` never changes the first letter of a surname.
- [x] Only concepts in `touches` change (enforced by the engine).
- [x] Each event includes the before and after text and an ambiguity label.
- [x] README example pair `J. Smith` and `John Smith Jr.` can be produced.

## Test plan

- Unit tests per subtype with fixed random streams.
- Statistical test for rates.
- Test that name-part and full-name consistency holds in a mutated row.
- Test that `high` ambiguity is assigned when a household contains two same-initial members.

## Risks and notes

- Nickname data must be generic and not derived from any real person's records.
- Over-aggressive typos make matching impossible rather than hard; the rule above keeps most variants recoverable.

## Notes

- The catalogue no longer has `person.full_name` (retired in E2-S2), so the "keep the full name in step" rule has nothing to update. Name parts that sit in one row stay consistent through `order_swap`, which changes `first_name` and `last_name` together and emits one event for each.
- How subtypes are chosen: each selected row tries the subtypes in a weighted random order (weights from the table) until one applies, so `initial_only` is somewhat more common than its weight because a missing nickname falls back to it, as the story asks. Fallback events report `initial_only` as their subtype.
- Case changes are not made to `account.owner_names` or `account.registration`: the custodian upper-cases those when it writes, so a change would never be visible. The documented consequence is that case variants only appear in the CRM name parts and the spreadsheet's household name.
- `suffix_change` adds `Jr.` when there is no suffix and drops it otherwise. `hyphen_or_maiden` applies to surnames only, using a generic surname list in `data/nicknames.yaml` (together with 67 nickname entries).
- Names inside free text (`account.registration`, `household.name`) are found by matching the words of the people the row and its household refer to. `ambiguity = high` is set when an initial could also be another member of the same household with the same surname, as well as for every hyphenated or maiden-name variant.
- `typo` keeps the first letter of every word it edits, not only surnames.
- The type registers itself in the default registry when `onboardkit.datagen.mess.names` is imported; the pipeline (E4-S2) imports each type explicitly.

