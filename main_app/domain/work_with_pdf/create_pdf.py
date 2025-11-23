from pathlib import Path
from typing import Iterable, Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from main_app.core.constants import FONT_TYPE, FONT_PATH
from main_app.domain.work_with_pdf.actions.images.draw_images import draw_images
from main_app.domain.work_with_pdf.actions.text.draw_text_block import draw_text_block
from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions
from main_app.domain.work_with_pdf.models.pdf_layout import PdfLayout

pdfmetrics.registerFont(TTFont(FONT_TYPE, FONT_PATH))


def create_pdf(
        text: Optional[str],
        image_paths: Optional[Iterable[Path]],
        output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    page_width, page_height = A4

    layout = PdfLayout()  # используем единый layout и для текста, и для картинок

    c.setFont(layout.font_name, layout.font_size)

    image_paths = list(image_paths or [])
    has_content = False  # рисовали ли что-нибудь уже на текущих страницах

    # ---------- ТЕКСТ ----------
    if text:
        has_content = draw_text_block(
            c=c,
            text=text,
            layout=layout,
            page_width=page_width,
            page_height=page_height,
        )

    # ---------- КАРТИНКИ ----------
    if image_paths:
        # по умолчанию: поворачиваем горизонтальные, EXIF учитываем,
        # качество/разрешение не режем (resample_large_images=False)
        options = ImageRenderOptions()

        images_drawn = draw_images(
            c=c,
            image_paths=image_paths,
            page_width=page_width,
            page_height=page_height,
            margin_left=layout.left_margin,
            margin_top=layout.top_margin,
            margin_bottom=layout.bottom_margin,
            start_new_page=has_content,
            options=options,
        )
        has_content = has_content or images_drawn

    # ---------- если вообще ничего не передали ----------
    if not has_content:
        c.drawString(
            layout.left_margin,
            page_height - layout.top_margin,
            "Пустой PDF (нет текста и изображений)",
        )

    c.save()