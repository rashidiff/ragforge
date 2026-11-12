"""Optional local Tesseract OCR with explicit executable/language validation."""
from dataclasses import dataclass
import re
import shutil
import subprocess


@dataclass(frozen=True)
class OcrAvailability:
    available: bool
    executable: str | None
    languages: tuple[str, ...]
    missing_languages: tuple[str, ...] = ()
    warning: str | None = None


class OcrProcessingError(RuntimeError):
    pass


class LocalTesseract:
    def __init__(self, *, check_timeout: float = 10, page_timeout: float = 120):
        self.check_timeout, self.page_timeout = check_timeout, page_timeout
        self._availability: dict[str, OcrAvailability] = {}

    @staticmethod
    def _requested_languages(value: str) -> tuple[str, ...] | None:
        parts = tuple(part.strip() for part in value.split("+") if part.strip())
        if not parts or any(not re.fullmatch(r"[A-Za-z0-9_]+", part) for part in parts):
            return None
        return tuple(dict.fromkeys(parts))

    def check_availability(self, language_setting: str) -> OcrAvailability:
        if language_setting in self._availability:
            return self._availability[language_setting]
        requested = self._requested_languages(language_setting)
        if requested is None:
            result = OcrAvailability(False, None, (), warning="OCR language configuration is invalid.")
        else:
            executable = shutil.which("tesseract")
            if not executable:
                result = OcrAvailability(False, None, requested,
                    warning="Local OCR is enabled, but the Tesseract executable was not found on PATH.")
            else:
                try:
                    response = subprocess.run([executable, "--list-langs"], capture_output=True,
                        text=True, timeout=self.check_timeout, check=False, shell=False)
                except (OSError, subprocess.TimeoutExpired):
                    result = OcrAvailability(False, executable, requested,
                        warning="Tesseract could not report its installed language packs.")
                else:
                    installed = set(response.stdout.splitlines()[1:]) if response.returncode == 0 else set()
                    missing = tuple(language for language in requested if language not in installed)
                    if response.returncode != 0:
                        result = OcrAvailability(False, executable, requested,
                            warning="Tesseract language-pack inspection failed; OCR was skipped.")
                    elif missing:
                        result = OcrAvailability(False, executable, requested, missing,
                            warning="Local OCR language packs are missing: " + ", ".join(missing) + ".")
                    else:
                        result = OcrAvailability(True, executable, requested)
        self._availability[language_setting] = result
        return result

    def recognize_page(self, page, language_setting: str, availability: OcrAvailability) -> str:
        if not availability.available or not availability.executable:
            raise OcrProcessingError("Tesseract or a requested language pack is unavailable")
        try:
            import pymupdf
            image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes("png")
            response = subprocess.run([availability.executable, "stdin", "stdout", "-l",
                "+".join(availability.languages)], input=image, capture_output=True,
                timeout=self.page_timeout, check=False, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise OcrProcessingError("Local OCR exceeded its page timeout") from exc
        except OSError as exc:
            raise OcrProcessingError("Local OCR could not start Tesseract") from exc
        except (RuntimeError, ValueError) as exc:
            raise OcrProcessingError("The local PDF renderer could not prepare this page for OCR") from exc
        if response.returncode != 0:
            raise OcrProcessingError("Tesseract could not recognize this page")
        return response.stdout.decode("utf-8", errors="replace").strip()
