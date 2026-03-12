"""Tests for the Apple Messages adapter."""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.adapters.apple_messages import AppleMessagesAdapter


@pytest.fixture
def tmp_chat_db(tmp_path):
    """Create a temporary chat.db with test data."""
    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE message (
        ROWID INTEGER PRIMARY KEY,
        text TEXT,
        date INTEGER,
        is_from_me INTEGER DEFAULT 0,
        handle_id INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE chat (
        ROWID INTEGER PRIMARY KEY,
        chat_identifier TEXT
    )""")
    conn.execute("""CREATE TABLE chat_message_join (
        chat_id INTEGER,
        message_id INTEGER
    )""")

    # Insert test messages
    conn.execute(
        "INSERT INTO message (ROWID, text, date, is_from_me, handle_id) VALUES (?, ?, ?, ?, ?)",
        (1, "Hello there!", 700000000000000000, 0, 1)
    )
    conn.execute(
        "INSERT INTO message (ROWID, text, date, is_from_me, handle_id) VALUES (?, ?, ?, ?, ?)",
        (2, "Hi! How are you?", 700001000000000000, 1, 1)
    )
    conn.execute(
        "INSERT INTO message (ROWID, text, date, is_from_me, handle_id) VALUES (?, ?, ?, ?, ?)",
        (3, "Meeting tomorrow at 3pm", 700002000000000000, 0, 2)
    )
    conn.execute("INSERT INTO chat (ROWID, chat_identifier) VALUES (1, '+15550100')")
    conn.execute("INSERT INTO chat (ROWID, chat_identifier) VALUES (2, '+15550200')")
    conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 1)")
    conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 2)")
    conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (2, 3)")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def adapter(tmp_chat_db):
    return AppleMessagesAdapter(db_path=tmp_chat_db)


@pytest.fixture
def missing_adapter(tmp_path):
    return AppleMessagesAdapter(db_path=tmp_path / "nonexistent.db")


# --- Health check ---

class TestHealthCheck:
    def test_healthy(self, adapter):
        assert adapter.health_check() is True

    def test_unhealthy(self, missing_adapter):
        assert missing_adapter.health_check() is False


# --- Node builder ---

class TestNodeBuilder:
    def test_message_to_node_inbound(self, adapter):
        data = {
            "ROWID": 1,
            "text": "Hello there!",
            "date": 700000000000000000,
            "is_from_me": 0,
            "handle_id": 1,
            "chat_identifier": "+15550100",
        }
        node = adapter._message_to_node(data)
        assert node["type"] == "message"
        assert node["adapter"] == "apple-messages"
        assert node["native_id"] == "1"
        assert node["register"] == "log"
        assert node["attributes"]["direction"] == "inbound"
        assert node["attributes"]["channel"] == "imessage"
        assert node["attributes"]["subject"] == "Hello there!"
        assert node["attributes"]["thread_id"] == "+15550100"
        assert node["body"] == "Hello there!"

    def test_message_to_node_outbound(self, adapter):
        data = {"ROWID": 2, "text": "Reply", "date": 0, "is_from_me": 1}
        node = adapter._message_to_node(data)
        assert node["attributes"]["direction"] == "outbound"

    def test_message_empty_text(self, adapter):
        data = {"ROWID": 3, "text": None, "date": 0, "is_from_me": 0}
        node = adapter._message_to_node(data)
        assert node["body"] == ""
        assert node["attributes"]["subject"] == ""


# --- Resolve ---

class TestResolve:
    def test_resolve_found(self, adapter):
        node = adapter.resolve("1")
        assert node is not None
        assert node["body"] == "Hello there!"

    def test_resolve_not_found(self, adapter):
        node = adapter.resolve("999")
        assert node is None

    def test_resolve_unavailable(self, missing_adapter):
        node = missing_adapter.resolve("1")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://message/apple-messages/123")
        assert result == "123"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://message/himalaya/123")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://message/apple-messages")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    def test_enumerate_messages(self, adapter):
        nodes = adapter.enumerate("message")
        assert len(nodes) == 3
        assert all(n["type"] == "message" for n in nodes)
        assert all(n["register"] == "log" for n in nodes)

    def test_enumerate_wrong_type(self, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []

    def test_enumerate_with_limit(self, adapter):
        nodes = adapter.enumerate("message", limit=2)
        assert len(nodes) == 2

    def test_enumerate_with_offset(self, adapter):
        nodes = adapter.enumerate("message", offset=1, limit=10)
        assert len(nodes) == 2

    def test_enumerate_unavailable(self, missing_adapter):
        nodes = missing_adapter.enumerate("message")
        assert nodes == []


# --- Create (read-only) ---

class TestCreate:
    def test_create_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="read-only"):
            adapter.create_node("message", {"subject": "Test"})


# --- Query ---

class TestQuery:
    def test_query_all(self, adapter):
        nodes = adapter.query_nodes("message")
        assert len(nodes) == 3

    def test_query_wrong_type(self, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []

    def test_query_text_search(self, adapter):
        nodes = adapter.query_nodes("message", {"text_search": "Hello"})
        assert len(nodes) == 1
        assert nodes[0]["body"] == "Hello there!"

    def test_query_text_search_case_insensitive(self, adapter):
        nodes = adapter.query_nodes("message", {"text_search": "meeting"})
        assert len(nodes) == 1

    def test_query_with_limit(self, adapter):
        nodes = adapter.query_nodes("message", {"limit": 1})
        assert len(nodes) == 1

    def test_query_with_attribute_filter(self, adapter):
        nodes = adapter.query_nodes("message", {
            "attributes": {"direction": "outbound"}
        })
        assert len(nodes) == 1
        assert nodes[0]["attributes"]["direction"] == "outbound"

    def test_query_unavailable(self, missing_adapter):
        nodes = missing_adapter.query_nodes("message")
        assert nodes == []


# --- Update (read-only) ---

class TestUpdate:
    def test_update_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="read-only"):
            adapter.update_node("1", {"attributes": {"subject": "New"}})


# --- Close (read-only) ---

class TestClose:
    def test_close_raises(self, adapter):
        with pytest.raises(NotImplementedError, match="read-only"):
            adapter.close_node("1", "delete")


# --- Sync ---

class TestSync:
    def test_sync_returns_messages(self, adapter):
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 3

    def test_sync_unavailable(self, missing_adapter):
        result = missing_adapter.sync()
        assert result["changed_nodes"] == []


# --- Fetch body ---

class TestFetchBody:
    def test_fetch_body(self, adapter):
        body = adapter.fetch_body("1")
        assert body == "Hello there!"

    def test_fetch_body_not_found(self, adapter):
        body = adapter.fetch_body("999")
        assert body is None
