# /home/dmitriy/PycharmProjects/FastAPI-Learning/tests/conftest.py
# repo: PDFnik-Backend

"""
Shared pytest fixtures and module stubs.

Run all tests:
    uv run pytest tests/ -v

Run a single group:
    uv run pytest tests/unit/test_run_logic.py -v
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Module stubs for heavy dependencies not available in the test environment.
# (pdfnik_contracts, reportlab, PIL are only needed in integration tests)
# ---------------------------------------------------------------------------


def _make_stub(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_stubs() -> None:
    """
    Creates minimal stub modules so that imports in tested code do not
    fail with ImportError when heavy dependencies are absent.

    pdfnik_contracts.pdf_content is ALWAYS replaced — the package may be
    installed as a real dependency but with a different version that is
    missing attributes required by the tests (e.g. PdfOrder).
    """
    optional_stubs = [
        "faster_whisper",
        "reportlab",
        "reportlab.lib",
        "reportlab.lib.pagesizes",
        "reportlab.lib.utils",
        "reportlab.pdfbase",
        "reportlab.pdfbase.pdfmetrics",
        "reportlab.pdfbase.ttfonts",
        "reportlab.pdfgen",
        "reportlab.pdfgen.canvas",
        "PIL",
        "PIL.Image",
        "PIL.ImageOps",
    ]
    for name in optional_stubs:
        if name not in sys.modules:
            _make_stub(name)

    # reportlab.lib.pagesizes needs A4 tuple
    sys.modules["reportlab.lib.pagesizes"].A4 = (595.27, 841.89)

    # reportlab.lib.utils needs ImageReader
    sys.modules["reportlab.lib.utils"].ImageReader = MagicMock

    # reportlab.pdfbase.ttfonts needs TTFont
    sys.modules["reportlab.pdfbase.ttfonts"].TTFont = MagicMock

    # reportlab.pdfbase.pdfmetrics needs registerFont and stringWidth
    sys.modules["reportlab.pdfbase.pdfmetrics"].registerFont = MagicMock()
    sys.modules["reportlab.pdfbase.pdfmetrics"].stringWidth = MagicMock(return_value=100.0)

    # reportlab.pdfgen.canvas needs Canvas
    sys.modules["reportlab.pdfgen.canvas"].Canvas = MagicMock
    sys.modules["reportlab.pdfgen"].canvas = sys.modules["reportlab.pdfgen.canvas"]

    # PIL.Image and PIL.ImageOps need open and exif_transpose
    sys.modules["PIL.Image"].open = MagicMock()
    sys.modules["PIL.ImageOps"].exif_transpose = MagicMock()
    sys.modules["PIL"].Image = sys.modules["PIL.Image"]
    sys.modules["PIL"].ImageOps = sys.modules["PIL.ImageOps"]

    # faster_whisper.WhisperModel stub
    sys.modules["faster_whisper"].WhisperModel = MagicMock

    # pdfnik_contracts is always replaced regardless of whether the real
    # package is installed — the installed version may be incomplete or
    # have a different public API than what tests expect.
    pc_root = _make_stub("pdfnik_contracts")
    pc = _make_stub("pdfnik_contracts.pdf_content")
    pc_root.pdf_content = pc

    pc.PdfOrder = MagicMock()
    pc.BotDocument = MagicMock()
    pc.PdfBlock = object
    pc.PdfTextBlock = MagicMock()
    pc.PdfImageBlock = MagicMock()
    pc.PdfHeadingBlock = MagicMock()
    pc.PdfParagraphBlock = MagicMock()
    pc.PdfListBlock = MagicMock()
    pc.PdfPriceTableBlock = MagicMock()
    pc.PdfRichText = MagicMock()
    pc.PdfTextEntity = MagicMock()
    pc.PdfImageRef = MagicMock()
    pc.PdfPriceRow = MagicMock()
    pc.TextEntityType = MagicMock()
    pc.PdfBlockType = MagicMock()


_ensure_stubs()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Path to a temporary SQLite DB. File does not exist until ensure_schema is called."""
    return tmp_path / "runs.db"


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Empty temporary directory."""
    return tmp_path
