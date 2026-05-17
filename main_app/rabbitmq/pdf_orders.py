# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/rabbitmq/pdf_orders.py
# repo: PDFnik-Backend

from faststream.rabbit.fastapi import RabbitRouter
from pdfnik_contracts.pdf_content import PdfOrder

from main_app.core.logger import logger
from main_app.domain.work_with_pdf.pdf_service import generate_pdf_for_order


def register_pdf_consumers(router: RabbitRouter) -> None:
    @router.subscriber("pdf.generate")
    async def handle_pdf_generate(data: dict):
        logger.info("Received pdf.generate message")

        try:
            order = PdfOrder.model_validate(data)
            logger.info(f"Generating PDF for chat_id={order.chat_id}")

            doc = await generate_pdf_for_order(order)

            await router.broker.publish(
                message=doc.model_dump(),
                queue="pdf.send",
            )
            logger.info(f"PDF generated for chat_id={order.chat_id}, " f"sent to queue=pdf.send")
        except Exception as e:
            logger.error(f"Error while handling pdf.generate: {e}")
