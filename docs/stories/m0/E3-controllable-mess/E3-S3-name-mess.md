# E3-S3: Name mess

| | |
|---|---|
| **Epic** | [E3: Controllable mess](../../../m0-foundation-epics.md#e3-controllable-mess) |
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

`name = "names"`, `touches = {"person.full_name", "person.first_name", "person.last_name", "person.suffix", "account.owner_names", "account.registration", "household.name"}`, `structural = False`, `max_rate = 0.35`.

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

- [ ] At intensity 0 the type changes nothing and emits no events.
- [ ] At the configured rate, the share of affected eligible rows is within 5 percentage points of `intensity * max_rate` on the 300-household dataset.
- [ ] Every subtype in the table is producible and appears in a test dataset at high intensity.
- [ ] No variant equals the original value.
- [ ] `typo` never changes the first letter of a surname.
- [ ] Only concepts in `touches` change (enforced by the engine).
- [ ] Each event includes the before and after text and an ambiguity label.
- [ ] README example pair `J. Smith` and `John Smith Jr.` can be produced.

## Test plan

- Unit tests per subtype with fixed random streams.
- Statistical test for rates.
- Test that name-part and full-name consistency holds in a mutated row.
- Test that `high` ambiguity is assigned when a household contains two same-initial members.

## Risks and notes

- Nickname data must be generic and not derived from any real person's records.
- Over-aggressive typos make matching impossible rather than hard; the rule above keeps most variants recoverable.
