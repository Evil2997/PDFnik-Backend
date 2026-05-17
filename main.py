# /home/dmitriy/PycharmProjects/FastAPI-Learning/main.py
# repo: PDFnik-Backend

import uvicorn
from fastapi import FastAPI

from main_app.api.routes.orders import router as orders_router
from main_app.core.constants import FILES_ROOT, PDF_OUTPUT_DIR, TXT_OUTPUT_DIR
from main_app.core.logger import logger
from main_app.infrastructure.rabbit_connector import router, setup_rabbit_subscribers

app = FastAPI()

# Создаём директории при старте сервиса, не при импорте констант.
# Это позволяет импортировать модули в тестах без PermissionError.
FILES_ROOT.mkdir(parents=True, exist_ok=True)
PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TXT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger.info("Backend starting...")
setup_rabbit_subscribers()
logger.info("Rabbit subscribers registered")

app.include_router(orders_router)
app.include_router(router)
logger.info("Routers included")

if __name__ == "__main__":
    logger.info("Running uvicorn on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)