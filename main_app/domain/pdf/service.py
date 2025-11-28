import asyncio
import pathlib

from pdfnik_contracts.pdf_content import PdfOrder, BotDocument, PdfTextItem, PdfImageItem

from main_app.core.constants import FILES_ROOT
from main_app.core.logger import logger
from main_app.domain.work_with_pdf.actions.generate_pdf_path import generate_pdf_path
from main_app.domain.work_with_pdf.create_pdf import create_pdf


async def generate_pdf_for_order(order: PdfOrder) -> BotDocument:
    chat_id = order.chat_id
    logger.info(f"Start generate_pdf_for_order chat_id={chat_id}")

    text_parts = [item.text for item in order.items if isinstance(item, PdfTextItem)]
    image_items = [item for item in order.items if isinstance(item, PdfImageItem)]

    logger.info(
        f"Order content for chat_id={chat_id}: "
        f"{len(text_parts)} text blocks, {len(image_items)} images"
    )

    user_text = "\n\n".join(text_parts) if text_parts else None
    image_paths: list[pathlib.Path] = [
        FILES_ROOT / img.storage_key for img in image_items
    ]

    pdf_path: pathlib.Path = generate_pdf_path(chat_id)
    logger.info(f"PDF path for chat_id={chat_id}: {pdf_path}")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        create_pdf,
        user_text,
        image_paths,
        pdf_path,
    )

    pdf_storage_key = pdf_path.relative_to(FILES_ROOT).as_posix()
    logger.info(
        f"PDF generated for chat_id={chat_id}, storage_key={pdf_storage_key}"
    )

    return BotDocument(
        chat_id=chat_id,
        filename=pdf_path.name,
        storage_key=pdf_storage_key,
    )
