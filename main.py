# main_app/main.py (PDF-СЕРВИС)
import asyncio
import pathlib

import uvicorn
from fastapi import FastAPI

from main_app.contracts import PdfOrder, TextItem, ImageItem, BotDocument
from main_app.work_with_pdf.actions.generate_pdf_path import generate_pdf_path
from main_app.work_with_pdf.create_pdf import create_pdf
from main_app.main_constants import router, FILES_ROOT

app = FastAPI()


@router.subscriber("orders")
async def process(data: dict):
    # 1. Валидация входящих данных
    order = PdfOrder.model_validate(data)

    chat_id = order.chat_id

    # 2. Разделяем элементы по типам
    text_parts = [item.text for item in order.items if isinstance(item, TextItem)]
    image_items = [item for item in order.items if isinstance(item, ImageItem)]

    user_text = "\n\n".join(text_parts) if text_parts else None

    # 3. Строим пути к картинкам из storage_key
    image_paths: list[pathlib.Path] = [
        FILES_ROOT / img.storage_key for img in image_items
    ]

    pdf_path: pathlib.Path = generate_pdf_path(chat_id)

    # 5. Запускаем генерацию PDF в отдельном треде
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        create_pdf,
        user_text,
        image_paths,
        pdf_path,
    )

    # 6. storage_key для PDF — относительный путь от FILES_ROOT
    pdf_storage_key = pdf_path.relative_to(FILES_ROOT).as_posix()

    doc = BotDocument(
        chat_id=chat_id,
        filename=pdf_path.name,
        storage_key=pdf_storage_key,
    )

    # 7. Отправляем только метаданные в очередь bot_documents
    await router.broker.publish(
        message=doc.model_dump(),
        queue="bot_documents",
    )

    # 8. НИЧЕГО не удаляем — файлы чистит отдельный cleaner


@router.post("/order")
async def make_order(name: str):
    await router.broker.publish(
        message=f"Order {name}",
        queue="orders_http",
    )
    return {"data": "OK"}


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
