from pydantic import BaseModel, ConfigDict


class PdfLayout(BaseModel):
    """
    Конфигурация внешнего вида PDF:
    поля, шрифт, высота строки и т.д.
    """
    model_config = ConfigDict(frozen=True)  # делаем объект неизменяемым

    left_margin: float = 50
    top_margin: float = 50
    bottom_margin: float = 50
    font_name: str = "DejaVuSans"
    font_size: int = 12
    line_height: float = 16
