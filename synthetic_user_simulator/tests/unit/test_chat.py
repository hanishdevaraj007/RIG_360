"""Unit tests for src/chat/*."""

import pytest

from src.chat.base import ChatClient, ChatError
from src.chat.dnl_chat import DNLChatClient
from src.chat.message_bank import DEFAULT_MESSAGES, MessageBank
from src.utils.randomization import Randomizer


# --- ChatClient ABC ---------------------------------------------------------

def test_chat_client_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ChatClient()


# --- MessageBank -------------------------------------------------------------

def test_message_bank_default_messages_used_when_none_given():
    bank = MessageBank()
    assert bank.messages == DEFAULT_MESSAGES


def test_message_bank_accepts_custom_messages():
    bank = MessageBank(messages=["custom test message"])
    assert bank.messages == ["custom test message"]


def test_message_bank_empty_custom_list_raises():
    with pytest.raises(ValueError, match="at least one message"):
        MessageBank(messages=[])


def test_message_bank_random_message_returns_one_from_the_list():
    bank = MessageBank(messages=["a", "b", "c"])
    randomizer = Randomizer(seed=1)
    for _ in range(10):
        assert bank.random_message(randomizer) in ("a", "b", "c")


def test_message_bank_reproducible_with_same_seed():
    bank = MessageBank()
    msg1 = bank.random_message(Randomizer(seed=7))
    msg2 = bank.random_message(Randomizer(seed=7))
    assert msg1 == msg2


# --- DNLChatClient (stub) ----------------------------------------------------

@pytest.mark.asyncio
async def test_dnl_chat_client_send_message_raises_chat_error():
    client = DNLChatClient()
    assert client.platform_name == "dnl"
    with pytest.raises(ChatError, match="not implemented"):
        await client.send_message(page=object(), message="test message")


@pytest.mark.asyncio
async def test_dnl_chat_client_error_references_readme_section():
    client = DNLChatClient()
    with pytest.raises(ChatError, match="README.md Section 23"):
        await client.send_message(page=object(), message="test message")