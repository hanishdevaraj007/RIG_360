"""Seeded random number generation for workload variation.

Every randomized aspect of a session (start delay, watch duration, chat
message count/timing) should go through a Randomizer instance rather than
calling the `random` module directly, so that:
  - a run with `random_seed` set in config is reproducible end-to-end,
  - it's obvious, by grep, everywhere randomization happens.

Per README.md Section 12 / the master prompt's Section 12: this exists to
generate varied synthetic *workload* for load testing. It does not make
automated browser sessions "human" and is not a detection-avoidance
mechanism of any kind.
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence, TypeVar

T = TypeVar("T")


class Randomizer:
    """Thin wrapper around `random.Random`, seedable for reproducibility."""

    def __init__(self, seed: Optional[int] = None) -> None:
        """
        Args:
            seed: If provided, all randomization from this instance is
                reproducible across runs given the same seed and the
                same sequence of calls. If None, uses OS entropy (not
                reproducible), matching Python's default `random`
                behavior.
        """
        self.seed = seed
        self._rng = random.Random(seed)

    def uniform_float(self, minimum: float, maximum: float) -> float:
        """Return a random float in [minimum, maximum].

        Args:
            minimum: Lower bound (inclusive).
            maximum: Upper bound (inclusive).

        Returns:
            A random float. If minimum == maximum, always returns that
            value.

        Raises:
            ValueError: if maximum < minimum.
        """
        if maximum < minimum:
            raise ValueError(
                f"maximum ({maximum}) must be >= minimum ({minimum})"
            )
        if maximum == minimum:
            return minimum
        return self._rng.uniform(minimum, maximum)

    def uniform_int(self, minimum: int, maximum: int) -> int:
        """Return a random integer in [minimum, maximum].

        Args:
            minimum: Lower bound (inclusive).
            maximum: Upper bound (inclusive).

        Returns:
            A random integer.

        Raises:
            ValueError: if maximum < minimum.
        """
        if maximum < minimum:
            raise ValueError(
                f"maximum ({maximum}) must be >= minimum ({minimum})"
            )
        return self._rng.randint(minimum, maximum)

    def choice(self, sequence: Sequence[T]) -> T:
        """Return a random element from a non-empty sequence.

        Args:
            sequence: Sequence to choose from.

        Returns:
            One element of `sequence`.

        Raises:
            ValueError: if sequence is empty.
        """
        if not sequence:
            raise ValueError("Cannot choose from an empty sequence")
        return self._rng.choice(sequence)

    def shuffled(self, sequence: Sequence[T]) -> List[T]:
        """Return a new list containing sequence's elements in random order.

        Does not mutate the input sequence.

        Args:
            sequence: Sequence to shuffle.

        Returns:
            A new, shuffled list.
        """
        items = list(sequence)
        self._rng.shuffle(items)
        return items

    def child(self) -> "Randomizer":
        """Create a new, independently-seeded Randomizer derived from this one.

        Useful for giving each concurrent session its own Randomizer so
        sessions don't share RNG state (which would make concurrent
        randomization order-dependent), while still being fully
        reproducible: calling child() N times in the same order, from a
        Randomizer with the same seed, always produces the same N
        derived seeds.

        Returns:
            A new Randomizer seeded deterministically from this
            instance's RNG state (if this instance has a seed) or from
            OS entropy (if it does not).
        """
        derived_seed = self._rng.getrandbits(32) if self.seed is not None else None
        return Randomizer(seed=derived_seed)