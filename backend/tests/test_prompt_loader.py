import pytest

from app.services.prompt_loader import PromptError, PromptLoader


def test_edits_reload_without_code_change_and_version_matches_bytes(tmp_path):
    path = tmp_path / "system.md"
    path.write_bytes("# فارسی\r\nEvidence only".encode())
    loader = PromptLoader(tmp_path)
    first = loader.load("system")
    assert "\r\n" in first.text
    path.write_text("# Français\nUpdated", encoding="utf-8")
    second = loader.load("system")
    assert first.version != second.version
    assert second.text == "# Français\nUpdated"


@pytest.mark.parametrize("content", [None, b"", b"  \n", b"\xff"])
def test_missing_empty_and_invalid_prompts_fail_clearly(tmp_path, content):
    if content is not None:
        (tmp_path / "system.md").write_bytes(content)
    with pytest.raises(PromptError, match="system"):
        PromptLoader(tmp_path).load("system")


def test_unknown_prompt_cannot_read_arbitrary_files(tmp_path):
    with pytest.raises(PromptError):
        PromptLoader(tmp_path).load("../agent")
