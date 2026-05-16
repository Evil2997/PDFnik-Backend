"""
Общие фикстуры pytest.

Запуск всего набора:
    uv run pytest tests/ -v

Запуск одной группы:
    uv run pytest tests/unit/test_run_logic.py -v
"""
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub-модули для зависимостей, которых нет в тестовой среде
# (pdfnik_contracts, reportlab, PIL и т.д. нужны только в интеграционных тестах)
# ---------------------------------------------------------------------------

def _make_stub(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_stubs() -> None:
    """
    Создаёт минимальные stub-модули так, чтобы импорты в тестируемом коде
    не падали с ImportError при отсутствии тяжёлых зависимостей.
    """
    stubs = [
        "faster_whisper",
        "reportlab",
        "reportlab.lib",
        "reportlab.lib.pagesizes",
        "reportlab.pdfbase",
        "reportlab.pdfbase.pdfmetrics",
        "reportlab.pdfbase.ttfonts",
        "reportlab.pdfgen",
        "reportlab.pdfgen.canvas",
        "PIL",
        "PIL.Image",
        "PIL.ImageOps",
        "pdfnik_contracts",
        "pdfnik_contracts.pdf_content",
    ]
    for name in stubs:
        if name not in sys.modules:
            _make_stub(name)

    # reportlab.lib.pagesizes нужен A4
    sys.modules["reportlab.lib.pagesizes"].A4 = (595.27, 841.89)

    # faster_whisper.WhisperModel — заглушка
    sys.modules["faster_whisper"].WhisperModel = MagicMock


_ensure_stubs()


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Путь к временной SQLite БД. Файл не существует до вызова ensure_schema."""
    return tmp_path / "runs.db"


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Пустая временная директория."""
    return tmp_path