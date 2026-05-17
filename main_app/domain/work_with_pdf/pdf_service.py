# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/domain/work_with_pdf/pdf_service.py
# repo: PDFnik-Backend

import asyncio
import pathlib

from pdfnik_contracts.pdf_content import BotDocument, PdfBlock, PdfOrder

from main_app.core.constants import FILES_ROOT
from main_app.core.logger import logger
from main_app.domain.work_with_pdf.actions.generate_pdf_path import generate_pdf_path
from main_app.domain.work_with_pdf.create_pdf import create_pdf_from_blocks


async def generate_pdf_for_order(order: PdfOrder) -> BotDocument:
    chat_id = order.chat_id
    logger.info(f"Start generate_pdf_for_order chat_id={chat_id}")

    blocks: list[PdfBlock] = order.items

    logger.info(f"Order content for chat_id={chat_id}: " f"{len(blocks)} blocks")

    pdf_path: pathlib.Path = generate_pdf_path(chat_id)
    logger.info(f"PDF path for chat_id={chat_id}: {pdf_path}")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        create_pdf_from_blocks,
        blocks,
        pdf_path,
    )

    pdf_storage_key = pdf_path.relative_to(FILES_ROOT).as_posix()
    logger.info(f"PDF generated for chat_id={chat_id}, storage_key={pdf_storage_key}")

    return BotDocument(
        chat_id=chat_id,
        filename=pdf_path.name,
        storage_key=pdf_storage_key,
    )
