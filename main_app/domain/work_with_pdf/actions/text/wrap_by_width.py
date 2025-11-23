from reportlab.pdfbase import pdfmetrics


def wrap_by_width(
        text: str,
        max_width: float,
        font_name: str,
        font_size: int,
) -> list[str]:
    """
    Переносит текст по фактической ширине в пунктах, а не по количеству символов.

    Разбивает по словам и подбирает максимально возможное количество
    слов в строке, чтобы их ширина не превышала max_width.
    """
    # Пустая строка — отдельный случай: возвращаем список с "".
    if not text.strip():
        return [""]

    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        candidate = word if not current_line else f"{current_line} {word}"
        width = pdfmetrics.stringWidth(candidate, font_name, font_size)

        if width <= max_width:
            current_line = candidate
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    if not lines:
        lines.append("")

    return lines
