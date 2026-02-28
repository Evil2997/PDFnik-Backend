from reportlab.pdfgen import canvas

from main_app.domain.work_with_pdf.actions.text.wrap_by_width import wrap_by_width
from main_app.domain.work_with_pdf.models.pdf_layout import PdfLayout


def draw_text_block(
        c: canvas.Canvas,
        text: str,
        layout: PdfLayout,
        page_width: float,
        page_height: float,
        y: float | None,
        *,
        block_spacing_lines: float = 1.0,
) -> tuple[bool, float]:
    """
    Рендерит текст, начиная с координаты y (курсор).
    Возвращает:
      (drawn, new_y)

    Поведение ближе к Telegram:
    - wrap (автоперенос по ширине) => y -= layout.wrap_line_height (плотнее)
    - '\\n' (явный перенос)        => y -= layout.line_height (чуть больше)
    - пустая строка (абзац)        => y -= max(layout.line_height, layout.paragraph_spacing)
    """

    if not text:
        start_y = page_height - layout.top_margin if y is None else y
        return False, start_y

    max_text_width = page_width - layout.left_margin - layout.right_margin

    if y is None:
        y = page_height - layout.top_margin

    c.setFont(layout.font_name, layout.font_size)

    drawn_any = False

    paragraphs = text.split("\n")

    for p_idx, paragraph in enumerate(paragraphs):
        # Явный пустой абзац (пользователь отправил пустую строку)
        if paragraph == "":
            if y < layout.bottom_margin:
                c.showPage()
                c.setFont(layout.font_name, layout.font_size)
                y = page_height - layout.top_margin

            # Минимум: один line_height, иначе пустая строка "исчезнет"
            y -= max(layout.line_height, layout.paragraph_spacing)
            continue

        wrapped_lines = wrap_by_width(
            paragraph,
            max_text_width,
            layout.font_name,
            layout.font_size,
        )

        # Бывает, что wrap вернул пустой список (на всякий)
        if not wrapped_lines:
            wrapped_lines = [""]

        for i, line in enumerate(wrapped_lines):
            if y < layout.bottom_margin:
                c.showPage()
                c.setFont(layout.font_name, layout.font_size)
                y = page_height - layout.top_margin

            c.drawString(layout.left_margin, y, line)
            drawn_any = True

            # 🔥 Ключ: разный шаг для wrap и для '\n'
            if i < len(wrapped_lines) - 1:
                # авто-перенос по ширине
                y -= layout.wrap_line_height

        # Если это не последний "параграф" в split('\n'),
        # значит в исходном тексте был символ '\n' -> добавляем "почти такой же" отступ
        if p_idx < len(paragraphs) - 1:
            y -= layout.line_height

    # Отступ между блоками
    # (оставляем в "строках", но теперь допускаем дробные значения)
    y -= layout.line_height * max(0.0, block_spacing_lines)

    return drawn_any, y
