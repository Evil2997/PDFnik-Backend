from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PdfLayout(BaseModel):
    """
    Настройки типографики и полей страницы для рендеринга PDF.

    Эта модель описывает *как именно* текст и блоки располагаются на странице:
    - какой шрифт и размер используются;
    - насколько “плотно” идут строки (межстрочный интервал);
    - какие поля страницы (margins);
    - сколько “воздуха” добавлять между абзацами и между блоками.

    Дополнительно (важно для “как в Telegram”):
    - мы различаем шаг по вертикали для:
        1) автоматического переноса по ширине (wrap)
        2) явного переноса строки по '\\n'
      Это позволяет сделать wrap плотным, но чтобы строки не соприкасались,
      а '\\n' — почти таким же, но чуть “свободнее”.
    """

    model_config = ConfigDict(frozen=True)

    # --- Typography ---
    font_name: str = Field(
        default="DejaVuSans",
        description="Имя шрифта, зарегистрированного в ReportLab (pdfmetrics.registerFont).",
        examples=["Inter", "DejaVuSans"],
    )
    font_size: int = Field(
        default=11,
        ge=6,
        le=48,
        description="Размер шрифта (pt). Влияет на читаемость и на расчёт переносов по ширине.",
        examples=[10, 11, 12],
    )

    # Явный перенос строки '\n' (и “обычный” шаг для текста)
    line_height_multiplier: float = Field(
        default=1.40,
        ge=0.90,
        le=2.00,
        description=(
            "Множитель межстрочного интервала для обычного шага по строкам "
            "(в т.ч. когда в тексте встречается '\\n'). "
            "Итоговый line_height = font_size * line_height_multiplier."
        ),
        examples=[1.05, 1.10, 1.20],
    )

    # Автоматический перенос по ширине (wrap) — обычно чуть плотнее
    wrap_line_height_multiplier: float = Field(
        default=1.40,
        ge=1.00,
        le=1.50,
        description=(
            "Множитель вертикального шага для автоматического переноса строки (wrap). "
            "Используется, когда строка переносится по ширине, а не по '\\n'. "
            "Позволяет сделать строки плотными, но не соприкасающимися."
        ),
        examples=[1.02, 1.03, 1.06],
    )

    paragraph_spacing_multiplier: float = Field(
        default=0.4,
        ge=0.0,
        le=4.0,
        description=(
            "Дополнительный вертикальный отступ для пустой строки/абзаца "
            "в единицах line_height. 0 = без дополнительного отступа."
        ),
        examples=[0.0, 0.35, 0.5, 1.0],
    )

    block_spacing_multiplier: float = Field(
        default=1.0,
        ge=0.0,
        le=6.0,
        description=(
            "Отступ между блоками (например, между картинкой и следующим текстом) "
            "в единицах line_height. 0 = без отступа."
        ),
        examples=[0.0, 0.5, 1.0],
    )

    # --- Page margins ---
    left_margin: float = Field(default=40, ge=0, description="Левое поле страницы (pt).")
    right_margin: float = Field(default=40, ge=0, description="Правое поле страницы (pt).")
    top_margin: float = Field(default=60, ge=0, description="Верхнее поле страницы (pt).")
    bottom_margin: float = Field(default=40, ge=0, description="Нижнее поле страницы (pt).")

    # --- Computed ---
    @computed_field
    @property
    def line_height(self) -> float:
        """Шаг по вертикали для обычной строки / '\\n' (pt)."""
        return self.font_size * self.line_height_multiplier

    @computed_field
    @property
    def wrap_line_height(self) -> float:
        """Шаг по вертикали для автопереноса по ширине (wrap) (pt)."""
        return self.font_size * self.wrap_line_height_multiplier

    @computed_field
    @property
    def paragraph_spacing(self) -> float:
        """Отступ для пустой строки/абзаца (pt)."""
        return self.line_height * self.paragraph_spacing_multiplier

    @computed_field
    @property
    def block_spacing(self) -> float:
        """Отступ между блоками (pt)."""
        return self.line_height * self.block_spacing_multiplier
