# /home/dmitriy/PycharmProjects/PDFnik-Backend/main_app/domain/work_with_pdf/models/image_render_options.py
# repo: PDFnik-Backend

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ImageRenderOptions(BaseModel):
    """
    Settings for rendering images to PDF.

    The default values ​​are selected for a typical use case: screenshots and photos from Telegram.
    - rotate_horizontal=False: Do not rotate landscape images.
    Rotation was relevant for photos taken with cameras where the device was held sideways;
    however, screenshots are already in the correct orientation, and rotating them
    would only result in them being scaled down.
    - allow_upscale=True: Scale images up to fit the page size.
    Without this setting, small images would be displayed at their original small size,
    surrounded by large white margins.
    """

    model_config = ConfigDict(frozen=True)

    # Rotate horizontal images? (width >= height after accounting for EXIF data).
    # False — screenshots and landscape photos remain as-is.
    # True — enable this if you need to auto-rotate photos taken with the camera held sideways.
    rotate_horizontal: bool = False

    # Rotation direction (if rotate_horizontal=True).
    rotate_direction: Literal["cw", "ccw"] = "cw"

    # Image fitting mode (within the page rectangle).
    # "contain" — the image fits entirely without cropping (maintains aspect ratio).
    # "cover"   — [Future feature]: crop edges to fill the entire area.
    fit_mode: Literal["contain", "cover"] = "contain"

    # Physically downscale VERY large images (pixel resampling).
    # False — embed into the PDF as-is; True — limit to max_dpi.
    resample_large_images: bool = False

    # Maximum DPI for resampling (only applies if resample_large_images=True).
    max_dpi: int | None = 200

    # JPEG quality for re-encoding.
    jpeg_quality: int = 85

    # Stretch small images to page size (scale > 1).
    # True — the image fills the entire available page area.
    # False — small images remain small (this was the default behavior previously,
    #         resulting in large white margins around screenshots).
    allow_upscale: bool = True

    # Vertical alignment of the image on the page.
    vertical_align: Literal["center", "top", "bottom"] = "top"
