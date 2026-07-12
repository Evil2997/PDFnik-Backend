from pydantic import BaseModel, ConfigDict


class DrawSize(BaseModel):
    """Rendered dimensions of an image on a PDF page, in points."""

    model_config = ConfigDict(frozen=True)

    draw_w: float
    draw_h: float
