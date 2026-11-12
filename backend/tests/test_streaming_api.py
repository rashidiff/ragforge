import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(
        create_app(Settings(_env_file=None, data_dir=tmp_path)), base_url="http://127.0.0.1:8000"
    ) as connection:
        yield connection


def decode_frames(text):
    parsed = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        event, data = None, []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if event and data:
            parsed.append((event, json.loads("\n".join(data))))
    return parsed


def test_post_stream_persists_user_and_emits_local_grounded_terminal_events(client):
    chat = client.post("/api/chats", json={}).json()
    client_id = str(uuid4())
    response = client.post(
        f"/api/chats/{chat['chat_id']}/messages/stream",
        json={"content": "What does this library say?", "client_message_id": client_id},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = decode_frames(response.text)
    assert events[0][0] == "status" and events[0][1]["stage"] == "validating"
    assert any(name == "retrieval" for name, _ in events)
    assert any(name == "token" and "Library is empty" in data["delta"] for name, data in events)
    done = next(data for name, data in events if name == "done")
    assert done["complete"] is True
    assert events[-1][0] == "done"
    history = client.get(f"/api/chats/{chat['chat_id']}/messages").json()["messages"]
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert history[0]["content"] == "What does this library say?"
    assert history[1]["content"] == next(data["delta"] for name, data in events if name == "token")


def test_stream_rejects_empty_question_before_creating_a_history_record(client):
    chat = client.post("/api/chats", json={}).json()
    response = client.post(
        f"/api/chats/{chat['chat_id']}/messages/stream",
        json={"content": "  ", "client_message_id": str(uuid4())},
    )
    assert response.status_code == 422
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json() == {"messages": []}


def test_stream_requires_an_existing_chat(client):
    response = client.post(
        f"/api/chats/{uuid4()}/messages/stream",
        json={"content": "question", "client_message_id": str(uuid4())},
    )
    assert response.status_code == 404


def test_stream_rejects_a_second_active_generation_for_the_same_chat(client):
    chat = client.post("/api/chats", json={}).json()
    lease = client.app.state.runtime.generations.acquire(chat["chat_id"])
    try:
        response = client.post(
            f"/api/chats/{chat['chat_id']}/messages/stream",
            json={"content": "Question", "client_message_id": str(uuid4())},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "generation_conflict"
    finally:
        client.app.state.runtime.generations.release(lease)
