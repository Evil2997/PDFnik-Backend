# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/rabbitmq/pdf_orders.py
# repo: PDFnik-Backend

from faststream.rabbit.fastapi import RabbitRouter
from pdfnik_contracts.pdf_content import PdfOrder

from main_app.core.logger import logger
from main_app.domain.work_with_pdf.pdf_service import generate_pdf_for_order


def register_pdf_consumers(router: RabbitRouter) -> None:
    @router.subscriber("pdf.generate")
    async def handle_pdf_generate(data: dict) -> None:
        logger.info("event=pdf_generate_received chat_id=%s", data.get("chat_id"))

        try:
            order = PdfOrder.model_validate(data)
            doc = await generate_pdf_for_order(order)

            await router.broker.publish(
                message=doc.model_dump(),
                queue="pdf.send",
            )
            logger.info(
                "event=pdf_generate_ok chat_id=%s storage_key=%s",
                order.chat_id,
                doc.storage_key,
            )

        except Exception as e:
            logger.error(
                "event=pdf_generate_failed chat_id=%s error=%s",
                data.get("chat_id"),
                e,
            )
            # Route to DLQ — message will not be retried.
            # Logged by dead_letter.py handle_pdf_dead consumer.
            await router.broker.publish(
                message=data,
                queue="pdf.dead",
            )
