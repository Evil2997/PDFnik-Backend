from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class ImageRenderOptions(BaseModel):
    """
    Настройки рендера картинок в PDF.

    По умолчанию:
    - НЕ уменьшаем качество / разрешение (resample_large_images=False),
    - поворачиваем горизонтальные картинки на 90° по часовой.
    """
    model_config = ConfigDict(frozen=True)

    # Поворачивать ли горизонтальные картинки (width >= height после учёта EXIF)
    rotate_horizontal: bool = True
    # Направление поворота, если rotate_horizontal=True:
    # "cw"  — по часовой, "ccw" — против часовой
    rotate_direction: Literal["cw", "ccw"] = "cw"

    # Режим влезания в прямоугольник
    # "contain" — картинка полностью влезает, без обрезки
    # "cover"  — (на будущее) можно обрезать края, чтобы заполнить всю область
    fit_mode: Literal["contain", "cover"] = "contain"

    # Нужно ли физически уменьшать ОЧЕНЬ большие картинки (ресемплинг)
    # Если False — всю картинку кладём в PDF как есть (PDF может "раздуваться").
    resample_large_images: bool = False

    # Максимальный DPI для ресемплинга.
    # Если None — ограничение по DPI не используется.
    max_dpi: Optional[int] = 200

    # JPEG-качество при сжатии (если дойдём до перекодирования).
    jpeg_quality: int = 85

    # Разрешать ли "увеличивать" маленькие картинки (скейл > 1)
    allow_upscale: bool = False

    # Вертикальное выравнивание изображения внутри страницы
    vertical_align: Literal["center", "top", "bottom"] = "center"
