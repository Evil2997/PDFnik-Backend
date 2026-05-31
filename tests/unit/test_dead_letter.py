# /home/dmitriy/PycharmProjects/PDFnik-Backend/tests/unit/test_dead_letter.py
# repo: PDFnik-Backend

"""
Tests for the Dead Letter Queue consumers in dead_letter.py.

Both consumers are pure log sinks — they receive a dict and log it.
Tests verify that:
- consumers do not raise on valid payloads
- consumers do not raise on malformed / empty payloads
- logging is called with expected severity
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import consumers directly (bypassing RabbitRouter registration)
# ---------------------------------------------------------------------------
from main_app.rabbitmq.dead_letter import register_dlq_consumers


def _extract_consumers(router: MagicMock) -> tuple:
    """
    register_dlq_consumers calls router.subscriber() twice.
    Extract the decorated functions to call them directly in tests.
    """
    handlers = {}

    def fake_subscriber(queue_name):
        def decorator(fn):
            handlers[queue_name] = fn
            return fn

        return decorator

    router.subscriber = fake_subscriber
    register_dlq_consumers(router)
    return handlers.get("txt.dead"), handlers.get("pdf.dead")


@pytest.fixture()
def consumers():
    router = MagicMock()
    txt_dead, pdf_dead = _extract_consumers(router)
    return txt_dead, pdf_dead


# ---------------------------------------------------------------------------
# txt.dead consumer
# ---------------------------------------------------------------------------


class TestTxtDeadConsumer:
    @pytest.mark.asyncio
    async def test_does_not_raise_on_full_payload(self, consumers):
        txt_dead, _ = consumers
        payload = {
            "job_id": "abc-123",
            "reply": {"chat_id": 12345},
            "error": "Whisper OOM",
            "attempt": 3,
        }
        await txt_dead(payload)  # must not raise

    @pytest.mark.asyncio
    async def test_does_not_raise_on_empty_payload(self, consumers):
        txt_dead, _ = consumers
        await txt_dead({})

    @pytest.mark.asyncio
    async def test_does_not_raise_on_missing_fields(self, consumers):
        txt_dead, _ = consumers
        await txt_dead({"job_id": "xyz"})

    @pytest.mark.asyncio
    async def test_logs_at_error_level(self, consumers):
        txt_dead, _ = consumers
        with patch("main_app.rabbitmq.dead_letter.logger") as mock_logger:
            await txt_dead({"job_id": "j1", "error": "timeout"})
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_contains_job_id(self, consumers):
        txt_dead, _ = consumers
        with patch("main_app.rabbitmq.dead_letter.logger") as mock_logger:
            await txt_dead({"job_id": "job-xyz-999"})
        call_args = str(mock_logger.error.call_args)
        assert "job-xyz-999" in call_args

    @pytest.mark.asyncio
    async def test_handles_nested_reply(self, consumers):
        txt_dead, _ = consumers
        payload = {
            "job_id": "j2",
            "reply": {"chat_id": 99999, "reply_to_message_id": 1},
            "error": "ffmpeg failed",
            "attempt": 2,
        }
        await txt_dead(payload)


# ---------------------------------------------------------------------------
# pdf.dead consumer
# ---------------------------------------------------------------------------


class TestPdfDeadConsumer:
    @pytest.mark.asyncio
    async def test_does_not_raise_on_full_payload(self, consumers):
        _, pdf_dead = consumers
        payload = {
            "chat_id": 12345,
            "items": [{"type": "paragraph", "content": {"text": "hello"}}],
        }
        await pdf_dead(payload)

    @pytest.mark.asyncio
    async def test_does_not_raise_on_empty_payload(self, consumers):
        _, pdf_dead = consumers
        await pdf_dead({})

    @pytest.mark.asyncio
    async def test_logs_at_error_level(self, consumers):
        _, pdf_dead = consumers
        with patch("main_app.rabbitmq.dead_letter.logger") as mock_logger:
            await pdf_dead({"chat_id": 42})
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_contains_chat_id(self, consumers):
        _, pdf_dead = consumers
        with patch("main_app.rabbitmq.dead_letter.logger") as mock_logger:
            await pdf_dead({"chat_id": 77777})
        call_args = str(mock_logger.error.call_args)
        assert "77777" in call_args

    @pytest.mark.asyncio
    async def test_does_not_raise_on_large_payload(self, consumers):
        _, pdf_dead = consumers
        large_payload = {
            "chat_id": 1,
            "items": [{"text": "x" * 1000}] * 50,
        }
        await pdf_dead(large_payload)
