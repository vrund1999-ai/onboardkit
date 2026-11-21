"""Deterministic random streams.

Every generator component asks for its own named stream, so adding a new consumer never changes
the output of existing ones. Python's built-in ``hash()`` is salted per process and is never used.
"""

from __future__ import annotations

import hashlib
import random

from faker import Faker


def derive_seed(root_seed: int, *labels: str) -> int:
    """Return a stable 64-bit seed for ``root_seed`` and a path of labels."""
    key = f"{root_seed}:" + ":".join(labels)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def derive_rng(root_seed: int, *labels: str) -> random.Random:
    """Return an independent ``random.Random`` stream named by ``labels``."""
    return random.Random(derive_seed(root_seed, *labels))


def faker_for(root_seed: int, *labels: str) -> Faker:
    """Return a ``Faker("en_US")`` instance seeded from the named stream."""
    fake = Faker("en_US")
    reseed_faker(fake, root_seed, *labels)
    return fake


def reseed_faker(fake: Faker, root_seed: int, *labels: str) -> None:
    """Reset an existing Faker instance to the named stream (cheaper than creating a new one)."""
    fake.seed_instance(derive_seed(root_seed, *labels))
