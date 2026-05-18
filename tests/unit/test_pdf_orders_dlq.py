# /home/dmitriy/PycharmProjects/FastAPI-Learning/tests/unit/test_pdf_orders_dlq.py
# repo: PDFnik-Backend

"""
Tests for DLQ routing in pdf_orders.py.

Verifies that:
- successful PDF generation publishes to pdf.send
- failed PDF generation publishes to pdf.dead (not lost)
- invalid payload publishes to pdf.dead
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_router(broker: MagicMock) -> MagicMock:
    router = MagicMock()
    router.broker = broker
    return router


def _make_broker() -> MagicMock:
    broker = MagicMock()
    broker.publish = AsyncMock()
    return broker


def _valid_pdf_payload() -> dict:
    return {
        "chat_id": 12345,
        "items": [
            {
                "type": "paragraph",
                "content": {"text": "Hello world", "entities": []},
            }
        ],
    }


# ---------------------------------------------------------------------------
# Extract handler from register_pdf_consumers
# ---------------------------------------------------------------------------


def _get_handler(broker: MagicMock):
    from main_app.rabbitmq.pdf_orders import register_pdf_consumers

    handlers = {}

    def fake_subscriber(queue_name):
        def decorator(fn):
            handlers[queue_name] = fn
            return fn

        return decorator

    router = _make_router(broker)
    router.subscriber = fake_subscriber
    register_pdf_consumers(router)
    return handlers.get("pdf.generate")


# ---------------------------------------------------------------------------
# Successful generation → pdf.send
# ---------------------------------------------------------------------------


class TestPdfOrdersSuccess:
    @pytest.mark.asyncio
    async def test_publishes_to_pdf_send_on_success(self):
        broker = _make_broker()
        handler = _get_handler(broker)

        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {
            "chat_id": 12345,
            "filename": "out.pdf",
            "storage_key": "pdfs/out.pdf",
        }

        with (
            patch(
                "main_app.rabbitmq.pdf_orders.generate_pdf_for_order",
                AsyncMock(return_value=mock_doc),
            ),
            patch("main_app.rabbitmq.pdf_orders.PdfOrder") as MockOrder,
        ):
            MockOrder.model_validate.return_value = MagicMock(chat_id=12345)
            await handler(_valid_pdf_payload())

        calls = [str(c) for c in broker.publish.call_args_list]
        assert any("pdf.send" in c for c in calls)

    @pytest.mark.asyncio
    async def test_does_not_publish_to_dlq_on_success(self):
        broker = _make_broker()
        handler = _get_handler(broker)

        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {"chat_id": 12345}

        with (
            patch(
                "main_app.rabbitmq.pdf_orders.generate_pdf_for_order",
                AsyncMock(return_value=mock_doc),
            ),
            patch("main_app.rabbitmq.pdf_orders.PdfOrder") as MockOrder,
        ):
            MockOrder.model_validate.return_value = MagicMock(chat_id=12345)
            await handler(_valid_pdf_payload())

        calls = [str(c) for c in broker.publish.call_args_list]
        assert not any("pdf.dead" in c for c in calls)


# ---------------------------------------------------------------------------
# Failed generation → pdf.dead
# ---------------------------------------------------------------------------


class TestPdfOrdersDlqRouting:
    @pytest.mark.asyncio
    async def test_publishes_to_pdf_dead_on_generation_error(self):
        broker = _make_broker()
        handler = _get_handler(broker)

        with (
            patch(
                "main_app.rabbitmq.pdf_orders.generate_pdf_for_order",
                AsyncMock(side_effect=RuntimeError("reportlab crash")),
            ),
            patch("main_app.rabbitmq.pdf_orders.PdfOrder") as MockOrder,
        ):
            MockOrder.model_validate.return_value = MagicMock(chat_id=12345)
            await handler(_valid_pdf_payload())

        calls = [str(c) for c in broker.publish.call_args_list]
        assert any("pdf.dead" in c for c in calls)

    @pytest.mark.asyncio
    async def test_does_not_raise_on_generation_error(self):
        broker = _make_broker()
        handler = _get_handler(broker)

        with (
            patch(
                "main_app.rabbitmq.pdf_orders.generate_pdf_for_order",
                AsyncMock(side_effect=Exception("unexpected")),
            ),
            patch("main_app.rabbitmq.pdf_orders.PdfOrder") as MockOrder,
        ):
            MockOrder.model_validate.return_value = MagicMock(chat_id=12345)
            # Must not raise — exception is handled and routed to DLQ
            await handler(_valid_pdf_payload())

    @pytest.mark.asyncio
    async def test_publishes_to_pdf_dead_on_invalid_payload(self):
        broker = _make_broker()
        handler = _get_handler(broker)

        with patch("main_app.rabbitmq.pdf_orders.PdfOrder") as MockOrder:
            MockOrder.model_validate.side_effect = ValueError("invalid payload")
            await handler({"bad": "data"})

        calls = [str(c) for c in broker.publish.call_args_list]
        assert any("pdf.dead" in c for c in calls)

    @pytest.mark.asyncio
    async def test_original_payload_sent_to_dlq(self):
        broker = _make_broker()
        handler = _get_handler(broker)
        payload = _valid_pdf_payload()

        with (
            patch(
                "main_app.rabbitmq.pdf_orders.generate_pdf_for_order",
                AsyncMock(side_effect=RuntimeError("crash")),
            ),
            patch("main_app.rabbitmq.pdf_orders.PdfOrder") as MockOrder,
        ):
            MockOrder.model_validate.return_value = MagicMock(chat_id=12345)
            await handler(payload)

        dlq_call = next(c for c in broker.publish.call_args_list if "pdf.dead" in str(c))
        assert dlq_call.kwargs.get("message") == payload or payload in dlq_call.args
