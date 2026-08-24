"""DNL chat client -- STUB pending real DNL chat integration details.

TODO(DNL-INTEGRATION): the real transport for sending a DNL chat message
(DOM interaction, REST endpoint, or WebSocket protocol) has not been
supplied. See README.md Section 23 (DNL Integration Points).

This is intentionally not a guess at an API shape -- per the project's
no-hallucination rule, send_message() raises ChatError immediately and
explicitly rather than silently no-op'ing or fabricating a request that
would appear to "work" without actually doing anything.
"""

from __future__ import annotations

from playwright.async_api import Page

from src.chat.base import ChatClient, ChatError


class DNLChatClient(ChatClient):
    """Non-functional stub. Every call raises ChatError until real DNL
    chat integration details (selector, endpoint, or protocol) are
    supplied -- see README.md Section 23.
    """

    platform_name = "dnl"

    async def send_message(self, page: Page, message: str) -> None:
        """Not implemented -- see class docstring and README.md Section 23.

        Args:
            page: The session's Page (unused by this stub).
            message: The message that would have been sent (unused by
                this stub).

        Raises:
            ChatError: always, until the real DNL chat transport is
                implemented.
        """
        raise ChatError(
            "DNLChatClient.send_message is not implemented -- the real "
            "DNL chat transport (DOM selector, REST endpoint, or "
            "WebSocket protocol) has not been supplied. See README.md "
            "Section 23 (DNL Integration Points)."
        )