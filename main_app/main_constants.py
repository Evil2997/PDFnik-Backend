# -*- coding: utf-8 -*-
import pathlib
from typing import Final

from faststream.rabbit import RabbitBroker
from faststream.rabbit.fastapi import RabbitRouter

from main_app.settings import settings

BASE_DIR: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[1]

OUTPUT_DIR: Final[pathlib.Path] = BASE_DIR / "output_dir"
OUTPUT_DIR.mkdir(exist_ok=True)

IMAGES_DIR: Final[pathlib.Path] = BASE_DIR / "images_backend"
IMAGES_DIR.mkdir(exist_ok=True)

RABBITMQ_URL = settings.RABBITMQ_URL
broker = RabbitBroker(RABBITMQ_URL)

router = RabbitRouter(RABBITMQ_URL)

FONT_PATH: Final[pathlib.Path] = BASE_DIR / "fonts" / "dejavu" / "DejaVuSans.ttf"
FONT_TYPE = "DejaVuSans"
