from reportlab.pdfbase import pdfmetrics


def wrap_by_width(
    text: str,
    max_width: float,
    font_name: str,
    font_size: int,
) -> list[str]:
    """
    Wraps text based on its actual width in points, rather than by character count.

    It splits the text into words and selects the maximum possible number
    of words per line such that their combined width does not exceed max_width.
    """
    # An empty string is a special case: return a list containing "".
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
