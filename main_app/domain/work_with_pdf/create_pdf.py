from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from pdfnik_contracts.pdf_content import (
    PdfBlock,
    PdfTextBlock,
    PdfImageBlock,
)

from main_app.core.constants import FONT_TYPE, FONT_PATH, FILES_ROOT
from main_app.core.logger import logger
from main_app.domain.work_with_pdf.actions.images.draw_images import draw_images
from main_app.domain.work_with_pdf.actions.text.draw_text_block import draw_text_block
from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions
from main_app.domain.work_with_pdf.models.pdf_layout import PdfLayout

pdfmetrics.registerFont(TTFont(FONT_TYPE, FONT_PATH))


def _estimate_image_draw_height(
    image_path: Path,
    *,
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_top: float,
    margin_bottom: float,
    options: ImageRenderOptions,
) -> float:
    """
    Оценивает высоту, на которую draw_images нарисует картинку (режим contain),
    чтобы мы могли поставить курсор текста ПОД изображением и не накладывать текст поверх.

    Важно: это оценка по тем же правилам (EXIF transpose + rotate horizontal + contain).
    """
    max_w = page_width - 2 * margin_left
    max_h = page_height - margin_top - margin_bottom

    with Image.open(image_path) as im_raw:
        img = ImageOps.exif_transpose(im_raw).convert("RGB")

    width_px, height_px = img.size
    if width_px <= 0 or height_px <= 0:
        return 0.0

    # повторяем логику rotate_horizontal
    is_horizontal = width_px >= height_px
    if options.rotate_horizontal and is_horizontal:
        # cw = -90, ccw = +90
        if options.rotate_direction == "cw":
            img = img.rotate(-90, expand=True)
        else:
            img = img.rotate(90, expand=True)
        width_px, height_px = img.size

    # contain
    scale_w = max_w / float(width_px)
    scale_h = max_h / float(height_px)
    scale = min(scale_w, scale_h)
    if not options.allow_upscale:
        scale = min(scale, 1.0)

    draw_h = height_px * scale
    return float(draw_h)


def create_pdf_from_blocks(
    blocks: list[PdfBlock],
    output_path: Path,
) -> None:
    logger.info(f"create_pdf: start, output={output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    page_width, page_height = A4

    layout = PdfLayout()
    c.setFont(layout.font_name, layout.font_size)

    has_content = False
    current_y: float | None = None  # курсор для текста

    try:
        for block in blocks:
            # TEXT BLOCK
            if isinstance(block, PdfTextBlock):
                logger.info("Rendering text block")
                drawn, current_y = draw_text_block(
                    c=c,
                    text=block.content.text,
                    layout=layout,
                    page_width=page_width,
                    page_height=page_height,
                    y=current_y,
                    block_spacing_lines=1,
                )
                has_content = has_content or drawn

            # IMAGE BLOCK
            elif isinstance(block, PdfImageBlock):
                logger.info("Rendering image block")

                # Всегда рисуем картинку с корректным абсолютным путём
                image_path = FILES_ROOT / block.image.storage_key

                # Настраиваем так, чтобы картинка рисовалась ВВЕРХУ страницы,
                # а не по центру (чтобы под ней оставалось место для подписи/текста).
                options = ImageRenderOptions(vertical_align="top", rotate_horizontal=False)
                # (ты ранее говорил "не переворачивать" — это отдельно можно выключить)

                # Оценим высоту картинки на странице (чтобы поставить курсор под неё)
                draw_h = _estimate_image_draw_height(
                    image_path,
                    page_width=page_width,
                    page_height=page_height,
                    margin_left=layout.left_margin,
                    margin_top=layout.top_margin,
                    margin_bottom=layout.bottom_margin,
                    options=options,
                )

                # Рисуем картинку. start_new_page=has_content оставляем, чтобы если уже был текст —
                # картинка пошла с новой страницы.
                drawn = draw_images(
                    c=c,
                    image_paths=[image_path],
                    page_width=page_width,
                    page_height=page_height,
                    margin_left=layout.left_margin,
                    margin_top=layout.top_margin,
                    margin_bottom=layout.bottom_margin,
                    start_new_page=has_content,
                    options=options,
                )
                has_content = has_content or drawn

                # КЛЮЧЕВОЕ: ставим курсор текста ПОД картинку на этой же странице,
                # чтобы подпись/следующий текст не накладывались поверх изображения.
                # Картинка при vertical_align="top" начинается от (page_height - top_margin - draw_h).
                # Значит текст надо начинать ниже:
                spacing = layout.line_height  # 1 строка отступа
                current_y = (page_height - layout.top_margin - draw_h) - spacing

                # CAPTION (если есть) — рисуем прямо под картинкой
                if block.caption:
                    drawn2, current_y = draw_text_block(
                        c=c,
                        text=block.caption.text,
                        layout=layout,
                        page_width=page_width,
                        page_height=page_height,
                        y=current_y,
                        block_spacing_lines=1,
                    )
                    has_content = has_content or drawn2

        if not has_content:
            c.drawString(
                layout.left_margin,
                page_height - layout.top_margin,
                "Пустой PDF (нет содержимого)",
            )

        c.save()
        logger.info(f"create_pdf: saved PDF to {output_path}")

    except Exception as e:
        logger.error(f"create_pdf: error while generating PDF: {e}")
        raise
