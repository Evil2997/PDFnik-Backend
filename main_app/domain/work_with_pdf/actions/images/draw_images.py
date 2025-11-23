import logging
from pathlib import Path
from typing import Iterable, Sequence, Optional

from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions


def draw_images(
        c: canvas.Canvas,
        image_paths: Iterable[Path],
        page_width: float,
        page_height: float,
        margin_left: float,
        margin_top: float,
        margin_bottom: float,
        start_new_page: bool = True,
        options: Optional[ImageRenderOptions] = None,
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

    max_w = page_width - 2 * margin_left
    max_h = page_height - margin_top - margin_bottom

    any_drawn = False

    for idx, img_path in enumerate(paths):
        try:
            img_path = Path(img_path)

            # Открываем картинку через Pillow
            with Image.open(img_path) as im_raw:
                # Учитываем EXIF-ориентацию
                img = ImageOps.exif_transpose(im_raw)
                img = img.convert("RGB")  # для совместимости с PDF/JPEG

            width_px, height_px = img.size

            # Определяем горизонтальная/вертикальная
            is_horizontal = width_px >= height_px

            # Поворачиваем горизонтальные (если так настроено)
            if options.rotate_horizontal and is_horizontal:
                if options.rotate_direction == "cw":
                    # Pillow: угол > 0 — против часовой, по часовой — -90
                    img = img.rotate(-90, expand=True)
                else:  # "ccw"
                    img = img.rotate(90, expand=True)
                width_px, height_px = img.size

            # Рассчитываем размеры для отрисовки (режим 'contain')
            draw_w, draw_h = _compute_draw_size_contain(
                width_px=width_px,
                height_px=height_px,
                max_w=max_w,
                max_h=max_h,
                allow_upscale=options.allow_upscale,
            )

            # (Опционально) ресемплим большие картинки до разумного DPI.
            # По умолчанию resample_large_images=False → этот блок пропускается.
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

            # Координаты (горизонтальное центрирование)
            x = (page_width - draw_w) / 2

            # Вертикальное выравнивание
            if options.vertical_align == "top":
                y = page_height - margin_top - draw_h
            elif options.vertical_align == "bottom":
                y = margin_bottom
            else:  # "center"
                top_area = page_height - margin_top
                bottom_area = margin_bottom
                available_h = top_area - bottom_area
                y = bottom_area + (available_h - draw_h) / 2

            # Новая страница
            if start_new_page or idx > 0:
                c.showPage()

            img_reader = ImageReader(img)
            c.drawImage(img_reader, x, y, draw_w, draw_h)

            any_drawn = True

        except Exception as exc:  # noqa: BLE001
            print(f"Не удалось обработать изображение: {img_path}", exc)
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
        img,
        width_px: int,
        height_px: int,
        draw_w: float,
        draw_h: float,
        max_dpi: int,
        allow_upscale: bool,
):
    """
    При необходимости уменьшает картинку до разумного DPI,
    чтобы не раздувать PDF слишком сильно.
    """
    if width_px <= 0 or height_px <= 0:
        return img, width_px, height_px, draw_w, draw_h

    target_px_w = int(draw_w / 72.0 * max_dpi)
    target_px_h = int(draw_h / 72.0 * max_dpi)

    if target_px_w <= 0 or target_px_h <= 0:
        return img, width_px, height_px, draw_w, draw_h

    if width_px <= target_px_w and height_px <= target_px_h:
        return img, width_px, height_px, draw_w, draw_h

    scale_w = target_px_w / float(width_px)
    scale_h = target_px_h / float(height_px)
    scale = min(scale_w, scale_h)

    if scale >= 1.0 and not allow_upscale:
        return img, width_px, height_px, draw_w, draw_h

    new_w = max(1, int(width_px * scale))
    new_h = max(1, int(height_px * scale))

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # draw_w/draw_h оставляем прежними — на странице размер тот же
    return img_resized, new_w, new_h, draw_w, draw_h
