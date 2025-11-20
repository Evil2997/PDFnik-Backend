import asyncio
import base64
import pathlib

import uvicorn
from fastapi import FastAPI

from main_app.work_with_pdf.actions.generate_pdf_path import generate_pdf_path
from main_app.contracts import PdfOrder, TextItem, ImageItem
from main_app.work_with_pdf.create_pdf import create_pdf
from main_app.main_constants import router, IMAGES_DIR

app = FastAPI()


@router.subscriber("orders")
async def process(data: dict):
    # 1. Валидируем вход через Pydantic
    order = PdfOrder.model_validate(data)

    chat_id = order.chat_id

    # 2. Разделяем элементы по типам
    text_parts = [item.text for item in order.items if isinstance(item, TextItem)]
    image_items = [item for item in order.items if isinstance(item, ImageItem)]

    # Склеиваем все тексты в одну “простыню”.
    # При желании потом можно сделать более умно: текст между картинками и т.д.
    user_text = "\n\n".join(text_parts) if text_parts else None

    image_paths: list[pathlib.Path] = []
    pdf_path: pathlib.Path | None = None

    try:
        # 3. Декодируем и сохраняем все картинки
        for img in image_items:
            img_bytes = base64.b64decode(img.content_b64)
            path = IMAGES_DIR / img.filename
            path.write_bytes(img_bytes)
            image_paths.append(path)

        # 4. Генерим PDF
        pdf_path = generate_pdf_path(chat_id)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            create_pdf,
            user_text,
            image_paths,
            pdf_path,
        )

        # 5. Читаем PDF, кодируем и шлём обратно в bot_documents
        pdf_bytes = pdf_path.read_bytes()
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        await router.broker.publish(
            message={
                "chat_id": chat_id,
                "filename": pdf_path.name,
                "pdf_b64": pdf_b64,
            },
            queue="bot_documents",
        )

    finally:
        # Очищаем все файлы, что мигрировали между микросервисами
        for p in image_paths:
            p.unlink(missing_ok=True)
        if pdf_path is not None:
            pdf_path.unlink(missing_ok=True)


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
