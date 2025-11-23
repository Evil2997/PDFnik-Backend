# main_app/domain/service.py

import asyncio
import pathlib

from main_app.domain.contracts import PdfOrder, TextItem, ImageItem, BotDocument
from main_app.core.constants import FILES_ROOT
from main_app.domain.work_with_pdf.actions.generate_pdf_path import generate_pdf_path
from main_app.domain.work_with_pdf.create_pdf import create_pdf


async def generate_pdf_for_order(order: PdfOrder) -> BotDocument:
    """
    Бизнес-сценарий: по заказу PdfOrder создать PDF и вернуть BotDocument.
    Здесь НЕТ RabbitMQ и HTTP — только доменная логика.
    """

    chat_id = order.chat_id

    # 1. Собираем текст и картинки из заказа
    text_parts = [item.text for item in order.items if isinstance(item, TextItem)]
    image_items = [item for item in order.items if isinstance(item, ImageItem)]

    user_text = "\n\n".join(text_parts) if text_parts else None

    image_paths: list[pathlib.Path] = [
        FILES_ROOT / img.storage_key for img in image_items
    ]

    # 2. Генерим путь для PDF
    pdf_path: pathlib.Path = generate_pdf_path(chat_id)

    # 3. Генерация PDF (блокирующую create_pdf — в executor)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        create_pdf,
        user_text,
        image_paths,
        pdf_path,
    )

    # 4. Формируем метаданные для бота
    pdf_storage_key = pdf_path.relative_to(FILES_ROOT).as_posix()

    return BotDocument(
        chat_id=chat_id,
        filename=pdf_path.name,
        storage_key=pdf_storage_key,
    )
