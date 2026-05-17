# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/core/constants.py
# repo: PDFnik-Backend

import pathlib
from typing import Final

from main_app.core.settings import settings

RABBITMQ_URL: Final[str] = settings.RABBITMQ_URL

FILES_ROOT: Final[pathlib.Path] = pathlib.Path(settings.FILES_ROOT)
PDF_OUTPUT_DIR: Final[pathlib.Path] = pathlib.Path(settings.PDF_OUTPUT_DIR)
TXT_OUTPUT_DIR: Final[pathlib.Path] = pathlib.Path(settings.TXT_OUTPUT_DIR)
RUNS_DB_PATH: Final[pathlib.Path] = pathlib.Path(settings.RUNS_DB_PATH)

FONT_TYPE: Final[str] = settings.FONT_TYPE
FONT_PATH: Final[str] = settings.FONT_PATH

# mkdir вынесен в main.py — не должен выполняться при импорте модуля,
# иначе тесты падают с PermissionError на /data_files_storage.