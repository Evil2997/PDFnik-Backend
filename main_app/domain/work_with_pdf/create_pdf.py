# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/domain/work_with_pdf/create_pdf.py
# repo: PDFnik-Backend

"""
Точка входа для генерации PDF.

Содержит только оркестрацию:
  1. нормализация блоков  → pdf_normalizer.py
  2. рендеринг блоков     → pdf_renderers.py
"""

from pathlib import Path

from pdfnik_contracts.pdf_content import (
    PdfBlock,
    PdfBlockType,
    PdfImageBlock,
    PdfTextBlock,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from main_app.core.constants import FILES_ROOT, FONT_PATH, FONT_TYPE
from main_app.core.logger import logger
from main_app.domain.work_with_pdf.actions.images.draw_images import draw_images
from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions
from main_app.domain.work_with_pdf.models.pdf_layout import PdfLayout
from main_app.domain.work_with_pdf.pdf_normalizer import normalize_document_blocks
from main_app.domain.work_with_pdf.pdf_renderers import (
    estimate_image_draw_height,
    render_heading,
    render_list,
    render_paragraph,
    render_price_table,
)

pdfmetrics.registerFont(TTFont(FONT_TYPE, FONT_PATH))


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

    blocks = normalize_document_blocks(blocks)

    has_content = False
    current_y: float | None = None

    try:
        for block in blocks:
            # ── Paragraph ──────────────────────────────────────────────────
            if getattr(block, "type", None) == PdfBlockType.PARAGRAPH:
                drawn, current_y = render_paragraph(
                    c=c,
                    rt=block.content,
                    layout=layout,
                    page_width=page_width,
                    page_height=page_height,
                    y=current_y,
                )
                has_content = has_content or drawn

            # ── Heading ────────────────────────────────────────────────────
            elif getattr(block, "type", None) == PdfBlockType.HEADING:
                drawn, current_y = render_heading(
                    c=c,
                    rt=block.content,
                    layout=layout,
                    page_height=page_height,
                    y=current_y,
                )
                has_content = has_content or drawn

            # ── List ───────────────────────────────────────────────────────
            elif getattr(block, "type", None) == PdfBlockType.LIST:
                drawn, current_y = render_list(
                    c=c,
                    lb=block,
                    layout=layout,
                    page_width=page_width,
                    page_height=page_height,
                    y=current_y,
                )
                has_content = has_content or drawn

            # ── Price table ────────────────────────────────────────────────
            elif getattr(block, "type", None) == PdfBlockType.PRICE_TABLE:
                drawn, current_y = render_price_table(
                    c=c,
                    pb=block,
                    layout=layout,
                    page_width=page_width,
                    page_height=page_height,
                    y=current_y,
                )
                has_content = has_content or drawn

            # ── Backward compat: raw PdfTextBlock ──────────────────────────
            elif isinstance(block, PdfTextBlock):
                drawn, current_y = render_paragraph(
                    c=c,
                    rt=block.content,
                    layout=layout,
                    page_width=page_width,
                    page_height=page_height,
                    y=current_y,
                )
                has_content = has_content or drawn

            # ── Image ──────────────────────────────────────────────────────
            elif isinstance(block, PdfImageBlock):
                image_path = FILES_ROOT / block.image.storage_key
                options = ImageRenderOptions(
                    vertical_align="top",
                    rotate_horizontal=False,
                    allow_upscale=True,
                )

                draw_h = estimate_image_draw_height(
                    image_path,
                    page_width=page_width,
                    page_height=page_height,
                    margin_left=layout.left_margin,
                    margin_top=layout.top_margin,
                    margin_bottom=layout.bottom_margin,
                    options=options,
                )

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

                current_y = (page_height - layout.top_margin - draw_h) - layout.line_height

                if block.caption:
                    drawn2, current_y = render_paragraph(
                        c=c,
                        rt=block.caption,
                        layout=layout,
                        page_width=page_width,
                        page_height=page_height,
                        y=current_y,
                    )
                    has_content = has_content or drawn2

            else:
                logger.warning(f"Unknown block type: {getattr(block, 'type', None)}")

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
