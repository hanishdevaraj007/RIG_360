"""Chat client abstraction.

Chat is deliberately its own interface, separate from PlatformAdapter
(platforms/base.py). Per README.md Section 4/13, chat is only supported
for DNL -- YouTube has no ChatClient implementation at all, so there is
no chat-shaped method for a YouTube session to accidentally call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from playwright.async_api import Page


class ChatError(Exception):
    """Raised when a chat message cannot be sent.

    Distinct from PlatformError (platforms/base.py) so a caller can tell
    "the stream/player is broken" apart from "chat delivery failed" --
    the two can fail independently (e.g. playback fine, chat endpoint
    down), and README.md Section 18 treats a chat-only failure as
    SessionStatus.PARTIAL rather than FAILED.
    """


class ChatClient(ABC):
    """Interface every platform's chat client must implement.

    Only DNLChatClient exists as a concrete implementation (currently a
    non-functional stub -- see dnl_chat.py). There is intentionally no
    YouTubeChatClient.
    """

    #: Short identifier, matches the corresponding PlatformAdapter's
    #: platform_name. Concrete subclasses must override this.
    platform_name: str = "base"

    @abstractmethod
    async def send_message(self, page: Page, message: str) -> None:
        """Send a single chat message.

        Args:
            page: The session's Page (already navigated to the stream
                by the corresponding PlatformAdapter).
            message: The message text to send, drawn from
                chat/message_bank.py.

        Raises:
            ChatError: if the message could not be sent.
        """
        raise NotImplementedError