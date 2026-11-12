"""Read editable Markdown at use time; versions identify exact UTF-8 prompt bytes."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal


class PromptError(RuntimeError):
    pass


@dataclass(frozen=True)
class Prompt:
    text: str
    version: str


class PromptLoader:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def load(self, name: Literal["system", "compaction"]) -> Prompt:
        if name not in {"system", "compaction"}:
            raise PromptError("Only system and compaction prompts may be loaded")
        path = self.directory / f"{name}.md"
        if not path.resolve().is_relative_to(self.directory):
            raise PromptError(f"The {name} prompt must remain inside the prompts directory")
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise PromptError(
                f"Cannot read the {name} UTF-8 Markdown prompt. Restore it in prompts/."
            ) from exc
        if not text.strip():
            raise PromptError(f"The {name} prompt is empty. Restore its Markdown instructions.")
        return Prompt(text=text, version=sha256(content).hexdigest())

    def validate(self) -> None:
        self.load("system")
        self.load("compaction")
