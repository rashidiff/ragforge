from unittest.mock import patch

import pytest

from app.services.chat_store import ChatNotFoundError, ChatStore
from app.services.history_store import HistoryStore
from app.services.state_store import JsonState, StateCorruptionError


def make_store(tmp_path):
    return ChatStore(tmp_path, HistoryStore(tmp_path / "chat_history.jsonl"))


def test_create_rename_restart_and_verbatim_messages(tmp_path):
    store = make_store(tmp_path)
    first = store.create()
    second = store.create("French")
    text = "  متن فارسی\nfrançais\tEnglish "
    store.append_message(first["chat_id"], "request", "user", text)
    store.rename(second["chat_id"], "Renamed")
    reopened = make_store(tmp_path)
    assert reopened.get(second["chat_id"])["title"] == "Renamed"
    assert reopened.get(first["chat_id"])["title"] != "New chat"
    assert reopened.messages(first["chat_id"])[0]["content"] == text


def test_delete_preserves_other_chat_bytes_and_backups(tmp_path):
    store = make_store(tmp_path)
    one, two = store.create(), store.create()
    store.append_message(one["chat_id"], "a", "user", "delete me")
    store.append_message(two["chat_id"], "b", "user", "keep\nفارسی")
    before = store.history.path.read_bytes().splitlines(keepends=True)[1]
    store.delete(one["chat_id"])
    assert store.history.path.read_bytes() == before
    assert len(list(tmp_path.glob("*.before-delete-*.bak"))) == 1
    with pytest.raises(ChatNotFoundError):
        store.append_message(one["chat_id"], "r", "assistant", "late")
    assert store.list()[0]["chat_id"] == two["chat_id"]


def test_deletion_resumes_after_crash_between_tombstone_and_gc(tmp_path):
    store = make_store(tmp_path)
    chat = store.create()
    store.append_message(chat["chat_id"], "r", "user", "private")
    with patch.object(store, "_collect", side_effect=OSError("disk unavailable")):
        with pytest.raises(OSError):
            store.delete(chat["chat_id"])
    assert store.list() == []
    reopened = make_store(tmp_path)
    reopened.resume_deletions()
    assert reopened.history.records() == []


def test_failed_atomic_publication_keeps_previous_state(tmp_path):
    state = JsonState(tmp_path / "snapshot.json", {"schema_version": 1, "value": 1})
    state.update(lambda data: data.update(value=2))
    with patch("app.services.state_store.os.replace", side_effect=OSError("disk")):
        with pytest.raises(OSError):
            state.update(lambda data: data.update(value=3))
    assert state.read()["value"] == 2


def test_corrupt_snapshot_fails_without_silent_restore(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(StateCorruptionError):
        JsonState(path, {"schema_version": 1}).read()
    assert path.read_text() == "broken"
