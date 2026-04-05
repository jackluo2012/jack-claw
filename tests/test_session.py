"""Session 测试"""

import pytest
from jackclaw.session.models import Session, MessageEntry, MessageRole


def test_message_entry():
    entry = MessageEntry(role=MessageRole.USER, content="Hello", ts=1234567890)
    data = entry.to_dict()
    assert data["role"] == "user"
    restored = MessageEntry.from_dict(data)
    assert restored.role == MessageRole.USER


def test_session():
    session = Session(id="s-test", routing_key="p2p:ou_test", created_at=1234567890, updated_at=1234567890)
    assert session.message_count == 0
    session.messages.append(MessageEntry(role=MessageRole.USER, content="Hi", ts=1234567891))
    assert session.message_count == 1
