# main_app/main_constants.py (PDF-СЕРВИС)

import pathlib
from typing import Final

from faststream.rabbit import RabbitBroker
from faststream.rabbit.fastapi import RabbitRouter

from main_app.settings import settings

MAIN_DIR: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[1]

RABBITMQ_URL = settings.RABBITMQ_URL

broker = RabbitBroker(RABBITMQ_URL)
router = RabbitRouter(RABBITMQ_URL)

# Корень общего файлового хранилища (тот же путь, что у бота)
FILES_ROOT: Final[pathlib.Path] = pathlib.Path("/data_files_storage")
FILES_ROOT.mkdir(exist_ok=True)

# Подпапка для PDF (не создаём родителей, только саму папку)
PDF_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "pdf"
PDF_OUTPUT_DIR.mkdir(exist_ok=True)

# Пути к шрифтам и т.п.
FONT_PATH: Final[pathlib.Path] = MAIN_DIR / "fonts" / "dejavu" / "DejaVuSans.ttf"
FONT_TYPE = "DejaVuSans"
