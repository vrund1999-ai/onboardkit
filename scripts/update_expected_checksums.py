"""Regenerate the standard datasets and record their checksums for the current generator version.

Run this only after output changed on purpose, the generator version was bumped, and the
changelog was updated. Usage: python scripts/update_expected_checksums.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from onboardkit.datagen import GENERATOR_VERSION
from onboardkit.datagen.pipeline import generate_dataset
from onboardkit.datagen.standard import STANDARD_DATASETS, file_checksums, standard_config

EXPECTED = Path(__file__).resolve().parents[1] / "tests/datagen/expected/standard_datasets.json"


def main() -> None:
    recorded = json.loads(EXPECTED.read_text(encoding="utf-8")) if EXPECTED.exists() else {}
    entry: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in STANDARD_DATASETS:
            result = generate_dataset(standard_config(name), Path(tmp))
            entry[name] = file_checksums(result.path)
            print(f"{name}: {result.dataset_id} ({len(entry[name])} files)")
    recorded[GENERATOR_VERSION] = entry
    EXPECTED.write_text(
        json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"recorded checksums for generator version {GENERATOR_VERSION} in {EXPECTED.name}")


if __name__ == "__main__":
    main()
