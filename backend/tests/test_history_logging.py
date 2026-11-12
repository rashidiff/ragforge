from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from app.services.history_store import HistoryStore, HistoryCorruptionError
from app.services.activity_logger import ActivityLogger

def test_verbatim_unicode_and_incomplete_records(tmp_path):
    store = HistoryStore(tmp_path / "history.jsonl")
    text = "  فارسی\nfrançais \tEnglish\r\n"
    store.append_message("chat", "req", "user", text, message_id="user")
    store.append_message("chat", "req", "assistant", "partial", completed=False)
    assert HistoryStore(store.path).records("chat")[0]["content"] == text
    assert store.records()[1]["completed"] is False
    store.append_message("chat", "req", "user", text, message_id="user")
    assert len(store.records()) == 2

def test_concurrent_append_order(tmp_path):
    store = HistoryStore(tmp_path / "history.jsonl")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: store.append_message("c", str(n), "user", str(n)), range(64)))
    assert [r["metadata"]["sequence"] for r in store.records()] == list(range(1,65))

def test_partial_tail_quarantined(tmp_path):
    store = HistoryStore(tmp_path / "history.jsonl")
    store.append_message("c", "r", "user", "intact")
    with store.path.open("ab") as f:
        f.write(b'{"partial":')
    recovered = HistoryStore(store.path)
    assert len(recovered.records()) == 1
    assert next(tmp_path.glob("*.partial-*")).read_bytes() == b'{"partial":'

def test_corrupt_complete_record_not_silently_discarded(tmp_path):
    path = tmp_path / "history.jsonl"
    path.write_bytes(b'broken\n')
    with pytest.raises(HistoryCorruptionError):
        HistoryStore(path)
    assert path.read_bytes() == b'broken\n'

def test_redaction_separate_from_raw(tmp_path):
    secret = "sk-" + "a" * 32
    logger = ActivityLogger(tmp_path / "system.log.jsonl")
    logger.emit("provider_start", query=secret, headers={"Authorization": secret}, nested=[{"api_key": secret}])
    assert secret not in logger.store.path.read_text()
    event = logger.store.records()[0]
    assert event["timestamp"].endswith("+00:00")
    assert event["event_type"] == "provider_start"
