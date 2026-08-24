"""Safe, generic test chat messages for synthetic load-testing sessions.

Per README.md Section 13: messages here are deliberately generic, plainly
labeled as test traffic, and not designed to look like organic human
chat, evade spam/moderation systems, or impersonate any real person or
persona. If you need different wording for your test environment, edit
DEFAULT_MESSAGES or pass a custom list to MessageBank -- but keep the
same "obviously synthetic test traffic" intent.
"""

from __future__ import annotations

from typing import List, Optional

from src.utils.randomization import Randomizer

DEFAULT_MESSAGES: List[str] = [
    "synthetic load test message - please disregard",
    "automated QA session in progress",
    "internal load test checkpoint",
    "test traffic from synthetic user simulator",
    "QA automation - not a real viewer",
]


class MessageBank:
    """Holds a set of safe test messages and picks one at random."""

    def __init__(self, messages: Optional[List[str]] = None) -> None:
        """
        Args:
            messages: Custom message list. Defaults to DEFAULT_MESSAGES
                if not given.

        Raises:
            ValueError: if an explicitly-provided messages list is empty.
        """
        self.messages = list(messages) if messages is not None else list(DEFAULT_MESSAGES)
        if not self.messages:
            raise ValueError("MessageBank requires at least one message")

    def random_message(self, randomizer: Randomizer) -> str:
        """Return one message chosen at random.

        Args:
            randomizer: Source of randomization (this session's
                Randomizer, so choices are reproducible with a seed).

        Returns:
            One message string from this bank.
        """
        return randomizer.choice(self.messages)