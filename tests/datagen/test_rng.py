from onboardkit.datagen.rng import derive_rng, derive_seed, faker_for


def test_seed_is_stable_across_processes() -> None:
    # Pinned: Python's salted hash() would change this between runs.
    assert derive_seed(42, "people") == 10115379042809293495


def test_same_labels_give_same_stream() -> None:
    a = [derive_rng(7, "x", "1").random() for _ in range(3)]
    b = [derive_rng(7, "x", "1").random() for _ in range(3)]
    assert a == b


def test_labels_and_seed_make_streams_independent() -> None:
    first = derive_rng(7, "people").random()
    assert derive_rng(7, "accounts").random() != first
    assert derive_rng(8, "people").random() != first
    assert derive_rng(7, "people", "1").random() != first


def test_faker_is_deterministic() -> None:
    assert faker_for(1, "a").name() == faker_for(1, "a").name()
    assert faker_for(1, "a").name() != faker_for(2, "a").name()
