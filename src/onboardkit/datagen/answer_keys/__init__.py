"""Answer keys: the internal truth written next to every dataset (see ``truth/README.txt``).

``DEFAULT_WRITERS`` is what ``generate_dataset`` runs unless it is given its own list. Order does
not matter for the files, but the summary is last because it reads everything the others read.
"""

from __future__ import annotations

from onboardkit.datagen.answer_keys.column_mappings import write_column_mappings
from onboardkit.datagen.answer_keys.discrepancies import write_discrepancies
from onboardkit.datagen.answer_keys.entity_matches import write_entity_matches
from onboardkit.datagen.answer_keys.provenance import write_provenance
from onboardkit.datagen.answer_keys.summary import write_summary
from onboardkit.datagen.answer_keys.truth_files import write_events, write_firm, write_readme
from onboardkit.datagen.pipeline import AnswerKeyWriter

DEFAULT_WRITERS: tuple[AnswerKeyWriter, ...] = (
    write_readme,
    write_firm,
    write_events,
    write_provenance,
    write_entity_matches,
    write_column_mappings,
    write_discrepancies,
    write_summary,
)
