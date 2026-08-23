"""Unit tests for src/utils/randomization.py."""

import pytest

from src.utils.randomization import Randomizer


def test_same_seed_produces_same_sequence():
    r1 = Randomizer(seed=42)
    r2 = Randomizer(seed=42)

    seq1 = [r1.uniform_float(0, 100) for _ in range(5)]
    seq2 = [r2.uniform_float(0, 100) for _ in range(5)]

    assert seq1 == seq2


def test_different_seeds_produce_different_sequences():
    r1 = Randomizer(seed=1)
    r2 = Randomizer(seed=2)

    seq1 = [r1.uniform_float(0, 100) for _ in range(5)]
    seq2 = [r2.uniform_float(0, 100) for _ in range(5)]

    assert seq1 != seq2


def test_uniform_float_respects_bounds():
    r = Randomizer(seed=1)
    for _ in range(50):
        value = r.uniform_float(10.0, 20.0)
        assert 10.0 <= value <= 20.0


def test_uniform_float_equal_bounds_returns_that_value():
    r = Randomizer(seed=1)
    assert r.uniform_float(5.0, 5.0) == 5.0


def test_uniform_float_rejects_max_less_than_min():
    r = Randomizer(seed=1)
    with pytest.raises(ValueError, match="must be >= minimum"):
        r.uniform_float(10.0, 5.0)


def test_uniform_int_respects_bounds():
    r = Randomizer(seed=1)
    for _ in range(50):
        value = r.uniform_int(1, 3)
        assert value in (1, 2, 3)


def test_choice_returns_element_from_sequence():
    r = Randomizer(seed=1)
    options = ["a", "b", "c"]
    for _ in range(10):
        assert r.choice(options) in options


def test_choice_empty_sequence_raises():
    r = Randomizer(seed=1)
    with pytest.raises(ValueError, match="empty sequence"):
        r.choice([])


def test_shuffled_does_not_mutate_input():
    r = Randomizer(seed=1)
    original = [1, 2, 3, 4, 5]
    original_copy = list(original)
    r.shuffled(original)
    assert original == original_copy


def test_shuffled_contains_same_elements():
    r = Randomizer(seed=1)
    original = [1, 2, 3, 4, 5]
    shuffled = r.shuffled(original)
    assert sorted(shuffled) == sorted(original)


def test_child_with_seed_is_deterministic():
    r1 = Randomizer(seed=99)
    r2 = Randomizer(seed=99)

    child1 = r1.child()
    child2 = r2.child()

    assert child1.uniform_float(0, 1) == child2.uniform_float(0, 1)


def test_child_without_seed_has_no_fixed_seed():
    r = Randomizer(seed=None)
    child = r.child()
    assert child.seed is None