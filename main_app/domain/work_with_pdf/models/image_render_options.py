# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/domain/work_with_pdf/models/image_render_options.py
# repo: PDFnik-Backend

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class ImageRenderOptions(BaseModel):
    """
    Настройки рендера картинок в PDF.

    Дефолты выбраны под типичный use-case: скриншоты, фото из Telegram.
    - rotate_horizontal=False: не поворачивать landscape-изображения.
      Поворот был актуален для камерных фото снятых боком, но скриншоты
      уже в правильной ориентации и поворот только уменьшал их.
    - allow_upscale=True: растягивать до размера страницы.
      Без этого маленькие изображения отображались маленькими
      с большими белыми полями вокруг.
    """
    model_config = ConfigDict(frozen=True)

    # Поворачивать ли горизонтальные картинки (width >= height после учёта EXIF).
    # False — скриншоты и landscape-фото остаются как есть.
    # True — включить если нужно авто-поворачивать боковые камерные снимки.
    rotate_horizontal: bool = False

    # Направление поворота, если rotate_horizontal=True
    rotate_direction: Literal["cw", "ccw"] = "cw"

    # Режим влезания в прямоугольник страницы
    # "contain" — картинка полностью влезает без обрезки (сохраняет пропорции)
    # "cover"   — на будущее: обрезать края чтобы заполнить всю область
    fit_mode: Literal["contain", "cover"] = "contain"

    # Физически уменьшать ОЧЕНЬ большие картинки (ресемплинг пикселей).
    # False — кладём в PDF как есть; True — ограничиваем до max_dpi.
    resample_large_images: bool = False

    # Максимальный DPI для ресемплинга (только при resample_large_images=True).
    max_dpi: Optional[int] = 200

    # JPEG-качество при перекодировании
    jpeg_quality: int = 85

    # Растягивать маленькие картинки до размера страницы (scale > 1).
    # True — изображение заполняет всю доступную область страницы.
    # False — маленькая картинка остаётся маленькой (было по умолчанию,
    #         давало большие белые поля вокруг скриншотов).
    allow_upscale: bool = True

    # Вертикальное выравнивание изображения на странице
    vertical_align: Literal["center", "top", "bottom"] = "top"