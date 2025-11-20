import logging
from pathlib import Path
from typing import Iterable, Sequence, Optional

from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from main_app.work_with_pdf.models.image_render_options import ImageRenderOptions
from main_app.work_with_pdf.models.pdf_layout import PdfLayout


def draw_images(
        c: canvas.Canvas,
        image_paths: Iterable[Path],
        layout: PdfLayout,
        page_width: float,
        page_height: float,
        start_new_page: bool = True,
        options: Optional[ImageRenderOptions] = None,
        logger: Optional[logging.Logger] = None,
) -> bool:
    """
    Рендерит изображения в PDF.

    Поведение:
    - учитывает EXIF-ориентацию (через ImageOps.exif_transpose),
    - если картинка "горизонтальная" (width >= height) → по умолчанию поворачивает на 90°,
    - масштабирует картинку так, чтобы она полностью влезла в поля (режим contain),
    - каждое изображение — на отдельной странице (при start_new_page=True).

    Возвращает:
        True  — если хотя бы одна картинка успешно отрисована,
        False — если список пуст или всё упало/пропущено.
    """
    options = options or ImageRenderOptions()
    paths: Sequence[Path] = list(image_paths or [])
    if not paths:
        return False

    max_w = page_width - 2 * layout.left_margin
    max_h = page_height - 2 * layout.bottom_margin

    any_drawn = False

    def _log_error(msg: str, exc: Optional[BaseException] = None) -> None:
        nonlocal logger
        if logger is not None:
            logger.error(msg, exc_info=exc is not None)
        else:
            # запасной вариант: можно заменить на print, если логгер не используется
            if exc:
                print(f"[draw_images] ERROR: {msg}: {exc}")
            else:
                print(f"[draw_images] ERROR: {msg}")

    for idx, img_path in enumerate(paths):
        try:
            img_path = Path(img_path)

            # Открываем картинку через Pillow
            with Image.open(img_path) as im_raw:
                # Учитываем EXIF-ориентацию
                img = ImageOps.exif_transpose(im_raw)
                img = img.convert("RGB")  # Для совместимости с PDF/JPEG

            width_px, height_px = img.size

            # Определяем горизонтальная/вертикальная картинка
            is_horizontal = width_px >= height_px

            # Поворачиваем горизонтальные (если так настроено)
            if options.rotate_horizontal and is_horizontal:
                if options.rotate_direction == "cw":
                    # Pillow: угол > 0 — поворот против часовой.
                    # Значит, по часовой — это -90.
                    img = img.rotate(-90, expand=True)
                else:  # "ccw"
                    img = img.rotate(90, expand=True)

                width_px, height_px = img.size
                # после поворота горизонтальная станет вертикальной — это ок

            # Рассчитываем размеры для отрисовки (режим 'contain')
            draw_w, draw_h = _compute_draw_size_contain(
                width_px=width_px,
                height_px=height_px,
                max_w=max_w,
                max_h=max_h,
                allow_upscale=options.allow_upscale,
            )

            # (Опционально) ресемплим очень большие картинки до разумного DPI.
            # По умолчанию resample_large_images=False → этот блок будет пропущен.
            if options.resample_large_images and options.max_dpi:
                img, width_px, height_px, draw_w, draw_h = _maybe_resample_to_dpi(
                    img=img,
                    width_px=width_px,
                    height_px=height_px,
                    draw_w=draw_w,
                    draw_h=draw_h,
                    max_dpi=options.max_dpi,
                    allow_upscale=options.allow_upscale,
                )

            # Вычисляем координаты (горизонтальное центрирование)
            x = (page_width - draw_w) / 2

            # Вертикальное выравнивание
            if options.vertical_align == "top":
                y = page_height - layout.top_margin - draw_h
            elif options.vertical_align == "bottom":
                y = layout.bottom_margin
            else:  # "center"
                y = (page_height - draw_h) / 2

            # Новая страница для первой/каждой картинки
            if start_new_page or idx > 0:
                c.showPage()

            # Рисуем картинку
            img_reader = ImageReader(img)
            c.drawImage(img_reader, x, y, draw_w, draw_h)

            any_drawn = True

        except Exception as exc:  # noqa: BLE001
            _log_error(f"Не удалось обработать изображение: {img_path}", exc)
            continue

    return any_drawn


def _compute_draw_size_contain(
        width_px: int,
        height_px: int,
        max_w: float,
        max_h: float,
        allow_upscale: bool,
) -> tuple[float, float]:
    """
    Считает размеры для режима 'contain':
    картинка уменьшится так, чтобы целиком влезть в (max_w, max_h),
    сохраняя пропорции.
    """
    if width_px <= 0 or height_px <= 0:
        return 0.0, 0.0

    scale_w = max_w / float(width_px)
    scale_h = max_h / float(height_px)
    scale = min(scale_w, scale_h)

    if not allow_upscale:
        scale = min(scale, 1.0)

    draw_w = width_px * scale
    draw_h = height_px * scale
    return draw_w, draw_h


def _maybe_resample_to_dpi(
        img: Image.Image,
        width_px: int,
        height_px: int,
        draw_w: float,
        draw_h: float,
        max_dpi: int,
        allow_upscale: bool,
) -> tuple[Image.Image, int, int, float, float]:
    """
    При необходимости уменьшает картинку до разумного DPI, чтобы не раздувать PDF слишком сильно.

    - draw_w, draw_h — размеры на странице в поинтах.
    - max_dpi       — максимум DPI, выше которого нет смысла держать пиксели.

    Возвращает:
        (новый_img, новый_width_px, новый_height_px, новый_draw_w, новый_draw_h)

    По умолчанию в коде выше эта функция не будет вызвана,
    т.к. options.resample_large_images=False.
    """
    # Переводим размеры на странице (поинты) в "нужное" количество пикселей
    # 1 pt = 1/72 inch
    target_px_w = int(draw_w / 72.0 * max_dpi)
    target_px_h = int(draw_h / 72.0 * max_dpi)

    # Если исходное изображение и так <= целевого размера — ничего не делаем
    if width_px <= 0 or height_px <= 0:
        return img, width_px, height_px, draw_w, draw_h

    if width_px <= target_px_w and height_px <= target_px_h:
        return img, width_px, height_px, draw_w, draw_h

    # Считаем коэффициент уменьшения
    scale_w = target_px_w / float(width_px)
    scale_h = target_px_h / float(height_px)
    scale = min(scale_w, scale_h)

    if scale >= 1.0 and not allow_upscale:
        # Нечего уменьшать/увеличивать
        return img, width_px, height_px, draw_w, draw_h

    new_w = max(1, int(width_px * scale))
    new_h = max(1, int(height_px * scale))

    # Ресемплинг
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Пересчитываем физические размеры для отрисовки:
    # Теперь картинка сама по себе меньше, но логика 'contain' остаётся такой же.
    new_draw_w, new_draw_h = _compute_draw_size_contain(
        width_px=new_w,
        height_px=new_h,
        max_w=draw_w if allow_upscale else draw_w,  # тут можно было бы оставить max_w/max_h,
        max_h=draw_h if allow_upscale else draw_h,  # но упрощённо используем те же draw_*.
        allow_upscale=allow_upscale,
    )

    return img_resized, new_w, new_h, new_draw_w, new_draw_h
