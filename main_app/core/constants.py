import pathlib
from typing import Final

from main_app.core.settings import settings

MAIN_DIR: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[2]

RABBITMQ_URL: Final[str] = settings.RABBITMQ_URL

FILES_ROOT: Final[pathlib.Path] = pathlib.Path("/data_files_storage")
FILES_ROOT.mkdir(exist_ok=True)

PDF_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "pdf_output"
PDF_OUTPUT_DIR.mkdir(exist_ok=True)

TXT_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "txt_output"
TXT_OUTPUT_DIR.mkdir(exist_ok=True)

RUNS_DB_PATH: Final[pathlib.Path] = pathlib.Path(settings.SQLITE_PATH)

FONT_PATH: Final[pathlib.Path] = MAIN_DIR / "fonts" / "dejavu" / "DejaVuSans.ttf"
FONT_TYPE: Final[str] = "DejaVuSans"
