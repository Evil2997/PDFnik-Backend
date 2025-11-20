from reportlab.pdfgen import canvas

from main_app.work_with_pdf.actions.text.wrap_by_width import wrap_by_width
from main_app.work_with_pdf.models.pdf_layout import PdfLayout


def draw_text_block(
        c: canvas.Canvas,
        text: str,
        layout: PdfLayout,
        page_width: float,
        page_height: float,
) -> bool:
    """
    Рендерит текстовый блок (многострочный текст) на PDF-страницах,
    выполняя перенос по ширине и автоматический переход на новую страницу.

    Возвращает True, если что-то было нарисовано (есть текст),
    иначе False.
    """
    if not text:
        return False

    max_text_width = page_width - 2 * layout.left_margin
    all_lines: list[str] = []

    # Разбиваем на абзацы по \n
    for paragraph in text.split("\n"):
        wrapped_lines = wrap_by_width(
            paragraph,
            max_text_width,
            layout.font_name,
            layout.font_size,
        )
        all_lines.extend(wrapped_lines)
        # Пустая строка между абзацами
        all_lines.append("")

    # Начинаем рисовать сверху
    y = page_height - layout.top_margin

    c.setFont(layout.font_name, layout.font_size)

    for line in all_lines:
        # если уходим ниже нижнего поля — новая страница
        if y < layout.bottom_margin:
            c.showPage()
            c.setFont(layout.font_name, layout.font_size)
            y = page_height - layout.top_margin

        # Печатаем строку
        c.drawString(layout.left_margin, y, line)
        y -= layout.line_height

    return True
