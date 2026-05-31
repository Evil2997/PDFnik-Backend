# /home/dmitriy/PycharmProjects/PDFnik-Backend/main_app/rabbitmq/dead_letter.py
# repo: PDFnik-Backend

"""
Dead Letter Queue consumer.

Messages land here when:
- txt.transcribe job failed all retry attempts (max_attempts exhausted)
- pdf.generate job raised an unhandled exception

DLQ does not retry. It logs the failure with full payload for manual inspection
or future alerting (Sentry, Telegram alert bot, etc.)
"""

import json
from typing import Any

from faststream.rabbit.fastapi import RabbitRouter

from main_app.core.logger import logger


def register_dlq_consumers(router: RabbitRouter) -> None:
    @router.subscriber("txt.dead")
    async def handle_txt_dead(data: dict[str, Any]) -> None:
        """
        Receives transcription jobs that exhausted all retry attempts.
        Logs job_id, chat_id, error for manual review.
        """
        job_id = data.get("job_id", "unknown")
        chat_id = data.get("reply", {}).get("chat_id") or data.get("chat_id", "unknown")
        error = data.get("error", "no error field")
        attempt = data.get("attempt", "unknown")

        logger.error(
            "event=dlq_txt_received job_id=%s chat_id=%s attempt=%s error=%s payload=%s",
            job_id,
            chat_id,
            attempt,
            error,
            json.dumps(data, ensure_ascii=False, default=str)[:500],
        )

    @router.subscriber("pdf.dead")
    async def handle_pdf_dead(data: dict[str, Any]) -> None:
        """
        Receives PDF generation jobs that failed with an unhandled exception.
        Logs chat_id and payload for manual review.
        """
        chat_id = data.get("chat_id", "unknown")

        logger.error(
            "event=dlq_pdf_received chat_id=%s payload=%s",
            chat_id,
            json.dumps(data, ensure_ascii=False, default=str)[:500],
        )
