import pytest
from pydantic import ValidationError

from app.config import Settings


def settings(**values):
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "values",
    [
        {"host": "0.0.0.0"},
        {"port": 0},
        {"max_upload_bytes": -1},
        {"chunk_tokens": 80, "chunk_overlap": 80},
        {"max_tool_rounds": 3},
        {"context_tokens": 1024, "output_tokens": 900, "summary_tokens": 200},
        {"dev_origin": "https://example.com"},
        {"dev_origin": "http://127.0.0.1:5173/foreign"},
    ],
)
def test_invalid_configuration_rejected(values):
    with pytest.raises(ValidationError):
        settings(**values)


def test_paths_created_only_on_explicit_initialization(tmp_path):
    root = tmp_path / "runtime"
    config = settings(data_dir=root)
    assert not root.exists()
    config.initialize_directories()
    assert (root / "library/pdfs").is_dir()
    assert (root / "state").is_dir()
    assert not hasattr(config, "api_key")
