# /home/dmitriy/PycharmProjects/PDFnik-Backend/main_app/domain/work_with_pdf/pdf_renderers.py
# repo: PDFnik-Backend

"""
Функции рендеринга отдельных типов PDF-блоков.

Каждая функция принимает canvas, данные блока, layout и текущую позицию y,
возвращает (drawn: bool, new_y: float).

Публичный API:
    render_paragraph(c, rt, layout, page_width, page_height, y)
    render_heading(c, rt, layout, page_height, y)
    render_list(c, lb, layout, page_width, page_height, y)
    render_price_table(c, pb, layout, page_width, page_height, y)
    estimate_image_draw_height(image_path, *, page_width, page_height, ...)
"""

from pathlib import Path

from pdfnik_contracts.pdf_content import (
    PdfListBlock,
    PdfPriceTableBlock,
    PdfRichText,
)
from PIL import Image, ImageOps
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from main_app.domain.work_with_pdf.actions.text.wrap_by_width import wrap_by_width
from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions
from main_app.domain.work_with_pdf.models.pdf_layout import PdfLayout

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_page(c: canvas.Canvas, layout: PdfLayout, page_height: float, y: float) -> float:
    """Переходит на новую страницу если курсор вышел за нижнее поле."""
    if y < layout.bottom_margin:
        c.showPage()
        c.setFont(layout.font_name, layout.font_size)
        return page_height - layout.top_margin
    return y


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_paragraph(
    c: canvas.Canvas,
    rt: PdfRichText,
    layout: PdfLayout,
    page_width: float,
    page_height: float,
    y: float | None,
) -> tuple[bool, float]:
    if y is None:
        y = page_height - layout.top_margin

    max_w = page_width - layout.left_margin - layout.right_margin
    c.setFont(layout.font_name, layout.font_size)

    drawn = False
    lines = rt.text.split("\n")
    for idx, line in enumerate(lines):
        if line.strip() == "":
            y = _ensure_page(c, layout, page_height, y)
            y -= max(layout.line_height, layout.paragraph_spacing)
            continue

        wrapped = wrap_by_width(line, max_w, layout.font_name, layout.font_size) or [""]
        for i, wline in enumerate(wrapped):
            y = _ensure_page(c, layout, page_height, y)
            c.drawString(layout.left_margin, y, wline)
            drawn = True
            if i < len(wrapped) - 1:
                y -= layout.wrap_line_height
        if idx < len(lines) - 1:
            y -= layout.line_height

    y -= layout.block_spacing
    return drawn, y


def render_heading(
    c: canvas.Canvas,
    rt: PdfRichText,
    layout: PdfLayout,
    page_height: float,
    y: float | None,
) -> tuple[bool, float]:
    # FIX: page_width убран — заголовок рисуется от left_margin,
    # ширина страницы здесь не используется.
    if y is None:
        y = page_height - layout.top_margin

    y = _ensure_page(c, layout, page_height, y)
    c.setFont(layout.font_name, layout.heading_font_size)
    c.drawString(layout.left_margin, y, rt.text.strip())
    c.setFont(layout.font_name, layout.font_size)

    y -= layout.heading_spacing
    y -= layout.block_spacing
    return True, y


def render_list(
    c: canvas.Canvas,
    lb: PdfListBlock,
    layout: PdfLayout,
    page_width: float,
    page_height: float,
    y: float | None,
) -> tuple[bool, float]:
    if y is None:
        y = page_height - layout.top_margin

    c.setFont(layout.font_name, layout.font_size)

    x_bullet = layout.left_margin + lb.indent_level * layout.list_indent_step
    x_text = x_bullet + layout.bullet_gap
    max_w = page_width - layout.right_margin - x_text

    drawn = False
    item_gap = layout.wrap_line_height if lb.tight else layout.line_height

    for item in lb.items:
        wrapped = wrap_by_width(item.text, max_w, layout.font_name, layout.font_size) or [""]

        y = _ensure_page(c, layout, page_height, y)
        c.drawString(x_bullet, y, lb.bullet)
        c.drawString(x_text, y, wrapped[0])
        drawn = True

        for wline in wrapped[1:]:
            y -= layout.wrap_line_height
            y = _ensure_page(c, layout, page_height, y)
            c.drawString(x_text, y, wline)

        y -= item_gap

    y -= layout.block_spacing
    return drawn, y


def render_price_table(
    c: canvas.Canvas,
    pb: PdfPriceTableBlock,
    layout: PdfLayout,
    page_width: float,
    page_height: float,
    y: float | None,
) -> tuple[bool, float]:
    if y is None:
        y = page_height - layout.top_margin

    c.setFont(layout.font_name, layout.font_size)

    x_left = layout.left_margin
    x_right = page_width - layout.right_margin

    drawn = False
    for row in pb.rows:
        price = row.price.text.strip()
        name = row.name.text.strip()

        y = _ensure_page(c, layout, page_height, y)

        price_w = pdfmetrics.stringWidth(price, layout.font_name, layout.font_size)
        x_price = x_right - price_w
        max_name_w = max(10.0, (x_price - layout.price_gap) - x_left)

        wrapped_name = wrap_by_width(name, max_name_w, layout.font_name, layout.font_size) or [""]

        c.drawString(x_left, y, wrapped_name[0])
        c.drawString(x_price, y, price)
        drawn = True

        for extra in wrapped_name[1:]:
            y -= layout.wrap_line_height
            y = _ensure_page(c, layout, page_height, y)
            c.drawString(x_left, y, extra)

        y -= layout.line_height

    y -= layout.block_spacing
    return drawn, y


# ---------------------------------------------------------------------------
# Image height estimation
# ---------------------------------------------------------------------------


def estimate_image_draw_height(
    image_path: Path,
    *,
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_top: float,
    margin_bottom: float,
    options: ImageRenderOptions,
) -> float:
    max_w = page_width - 2 * margin_left
    max_h = page_height - margin_top - margin_bottom

    with Image.open(image_path) as im_raw:
        img = ImageOps.exif_transpose(im_raw).convert("RGB")

    width_px, height_px = img.size
    if width_px <= 0 or height_px <= 0:
        return 0.0

    if options.rotate_horizontal and width_px >= height_px:
        img = img.rotate(-90 if options.rotate_direction == "cw" else 90, expand=True)
        width_px, height_px = img.size

    scale_w = max_w / float(width_px)
    scale_h = max_h / float(height_px)
    scale = min(scale_w, scale_h)
    if not options.allow_upscale:
        scale = min(scale, 1.0)

    return float(height_px * scale)
