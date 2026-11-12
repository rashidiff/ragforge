from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT, Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    config = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        prompts_dir=PROJECT_ROOT / "prompts",
        frontend_dist=tmp_path / "dist",
    )
    with TestClient(create_app(config), base_url="http://127.0.0.1:8000") as connection:
        yield connection


def test_health_and_chat_crud_round_trip(client):
    assert client.get("/api/health").json()["storage_ready"] is True
    response = client.post("/api/chats", json={"title": "فارسی"})
    assert response.status_code == 201
    chat = response.json()
    assert client.get("/api/chats").json()["chats"][0]["title"] == "فارسی"
    assert (
        client.patch(f"/api/chats/{chat['chat_id']}", json={"title": "français"}).status_code == 200
    )
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").json() == {"messages": []}
    assert client.delete(f"/api/chats/{chat['chat_id']}").status_code == 204
    assert client.get(f"/api/chats/{chat['chat_id']}/messages").status_code == 404


def test_validation_never_echoes_input(client):
    secret = "sk-" + "a" * 30
    response = client.post("/api/chats", json={"title": " ", "api_key": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert client.get("/api/chats").json() == {"chats": []}


def test_unknown_chat_and_cross_origin_mutation(client):
    assert client.delete(f"/api/chats/{uuid4()}").status_code == 404
    response = client.post("/api/chats", json={}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert client.get("/api/chats").json() == {"chats": []}


def test_chat_exports_preserve_unicode_and_label_incomplete_messages(client):
    chat = client.post("/api/chats", json={"title": "گفت‌وگو"}).json()
    runtime = client.app.state.runtime
    runtime.chats.append_message(
        chat["chat_id"], str(uuid4()), "user", "سؤال\n```\n<script>alert(1)</script>"
    )
    runtime.chats.append_message(
        chat["chat_id"], str(uuid4()), "assistant", "Réponse interrompue", completed=False
    )

    markdown = client.get(f"/api/chats/{chat['chat_id']}/export?format=markdown")
    assert markdown.status_code == 200
    assert "گفت‌وگو" in markdown.text and "سؤال" in markdown.text
    assert (
        "````" in markdown.text and "Assistant" in markdown.text and "incomplete" in markdown.text
    )
    assert markdown.headers["content-disposition"].endswith(f'chat-{chat["chat_id"]}.md"')

    exported = client.get(f"/api/chats/{chat['chat_id']}/export?format=json").json()
    assert exported["chat"]["title"] == "گفت‌وگو"
    assert exported["messages"][0]["content"].startswith("سؤال\n")
    assert exported["messages"][1]["completed"] is False
    assert "api_key" not in exported


def test_history_backup_is_a_locked_raw_snapshot(client):
    chat = client.post("/api/chats", json={}).json()
    runtime = client.app.state.runtime
    runtime.chats.append_message(chat["chat_id"], str(uuid4()), "user", "Exact فارسی\ncontent")
    expected = runtime.history.path.read_bytes()

    response = client.get("/api/history/backup")
    assert response.status_code == 200
    assert response.content == expected
    assert response.headers["content-disposition"] == 'attachment; filename="chat-history.jsonl"'
    assert "sensitive text" in response.headers["x-content-warning"]


def test_export_rejects_unknown_formats_and_deleted_chat_ids(client):
    chat = client.post("/api/chats", json={}).json()
    assert client.get(f"/api/chats/{chat['chat_id']}/export?format=html").status_code == 422
    assert client.delete(f"/api/chats/{chat['chat_id']}").status_code == 204
    assert client.get(f"/api/chats/{chat['chat_id']}/export?format=json").status_code == 404


def test_frontend_missing_and_unknown_api_are_explicit(client):
    assert client.get("/").status_code == 503
    assert client.get("/api/unknown").status_code == 404


def test_static_files_cannot_escape_dist(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<main>Local</main>")
    (tmp_path / "secret.txt").write_text("private")
    config = Settings(_env_file=None, data_dir=tmp_path / "data", frontend_dist=dist)
    with TestClient(create_app(config), base_url="http://127.0.0.1:8000") as connection:
        assert connection.get("/").status_code == 200
        assert "private" not in connection.get("/..%2Fsecret.txt").text
