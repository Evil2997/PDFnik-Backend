from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PdfLayout(BaseModel):
    model_config = ConfigDict(frozen=True)

    # --- Typography ---
    font_name: str = Field(default="DejaVuSans")
    font_size: int = Field(default=11, ge=6, le=48)

    line_height_multiplier: float = Field(default=1.40, ge=0.90, le=2.00)
    wrap_line_height_multiplier: float = Field(default=1.40, ge=1.00, le=1.50)

    paragraph_spacing_multiplier: float = Field(default=0.4, ge=0.0, le=4.0)
    block_spacing_multiplier: float = Field(default=1.0, ge=0.0, le=6.0)

    # --- Page margins ---
    left_margin: float = Field(default=60, ge=0)
    right_margin: float = Field(default=60, ge=0)
    top_margin: float = Field(default=80, ge=0)
    bottom_margin: float = Field(default=60, ge=0)

    # ✅ --- List / table geometry ---
    list_indent_step: float = Field(default=18, ge=0)  # один уровень вложенности
    bullet_gap: float = Field(default=10, ge=0)  # расстояние от маркера до текста
    price_gap: float = Field(default=12, ge=0)  # зазор между колонками name|price

    heading_font_size_delta: int = Field(default=2, ge=0, le=10)
    heading_spacing_multiplier: float = Field(default=0.6, ge=0.0, le=4.0)

    @computed_field
    @property
    def line_height(self) -> float:
        return self.font_size * self.line_height_multiplier

    @computed_field
    @property
    def wrap_line_height(self) -> float:
        return self.font_size * self.wrap_line_height_multiplier

    @computed_field
    @property
    def paragraph_spacing(self) -> float:
        return self.line_height * self.paragraph_spacing_multiplier

    @computed_field
    @property
    def block_spacing(self) -> float:
        return self.line_height * self.block_spacing_multiplier

    @computed_field
    @property
    def heading_font_size(self) -> int:
        return int(self.font_size + self.heading_font_size_delta)

    @computed_field
    @property
    def heading_spacing(self) -> float:
        return self.line_height * self.heading_spacing_multiplier
