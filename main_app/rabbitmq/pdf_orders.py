# main_app/rabbitmq/pdf_orders.py
from faststream.rabbit.fastapi import RabbitRouter
from pdfnik_contracts.pdf_content import PdfOrder
from main_app.domain.pdf.service import generate_pdf_for_order


def register_pdf_consumers(router: RabbitRouter) -> None:
    """
    Регистрируем всех подписчиков из этого модуля на переданном router'е.
    """

    @router.subscriber("pdf.generate")
    async def handle_pdf_generate(data: dict):
        order = PdfOrder.model_validate(data)
        doc = await generate_pdf_for_order(order)

        await router.broker.publish(
            message=doc.model_dump(),
            queue="pdf.send",
        )
