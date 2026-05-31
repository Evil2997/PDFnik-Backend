# /home/dmitriy/PycharmProjects/PDFnik-Backend/main.py
# repo: PDFnik-Backend

import uvicorn
from fastapi import FastAPI

from main_app.api.routes.health import health_router
from main_app.api.routes.orders import router as orders_router
from main_app.core.constants import FILES_ROOT, PDF_OUTPUT_DIR, TXT_OUTPUT_DIR
from main_app.core.logger import logger
from main_app.infrastructure.rabbit_connector import router, setup_rabbit_subscribers
from main_app.rabbitmq.dead_letter import register_dlq_consumers

app = FastAPI(
    title="PDFnik Backend",
    description="PDF generation and audio transcription service.",
    version="0.2.0",
)

# Create storage directories at startup, not at import time.
# Importing at module level would cause PermissionError in test environments
# where the Docker volume is not mounted.
FILES_ROOT.mkdir(parents=True, exist_ok=True)
PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TXT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger.info("Backend starting...")
setup_rabbit_subscribers()
register_dlq_consumers(router)
logger.info("Rabbit subscribers registered (including DLQ)")

app.include_router(orders_router)
app.include_router(health_router)
app.include_router(router)
logger.info("Routers included")

if __name__ == "__main__":
    logger.info("Running uvicorn on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
