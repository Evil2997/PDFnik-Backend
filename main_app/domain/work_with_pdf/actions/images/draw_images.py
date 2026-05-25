from collections.abc import Iterable, Sequence
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from main_app.core.logger import logger
from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions


def draw_images(
    c: canvas.Canvas,
    image_paths: Iterable[Path],
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_top: float,
    margin_bottom: float,
    start_new_page: bool = True,
    options: ImageRenderOptions | None = None,
) -> bool:
    """
    Renders images to PDF.

    Behavior:
    - respects EXIF ​​orientation (via ImageOps.exif_transpose),
    - if an image is "horizontal" (width >= height) → rotates it by 90° by default,
    - scales the image to fit entirely within the margins (contain mode),
    - places each image on a separate page (when start_new_page=True).

    Returns:
    True  — if at least one image was successfully rendered,
    False — if the list is empty or if all images failed/were skipped.
    """
    options = options or ImageRenderOptions()
    paths: Sequence[Path] = list(image_paths or [])
    if not paths:
        return False

    max_w = page_width - 2 * margin_left
    max_h = page_height - margin_top - margin_bottom

    any_drawn = False

    for idx, img_path in enumerate(paths):
        try:
            img_path = Path(img_path)

            with Image.open(img_path) as im_raw:
                img = ImageOps.exif_transpose(im_raw)
                img = img.convert("RGB")  # for PDF/JPEG compatibility

            width_px, height_px = img.size

            is_horizontal = width_px >= height_px

            if options.rotate_horizontal and is_horizontal:
                if options.rotate_direction == "cw":
                    img = img.rotate(-90, expand=True)
                else:  # "ccw"
                    img = img.rotate(90, expand=True)
                width_px, height_px = img.size

            draw_w, draw_h = _compute_draw_size_contain(
                width_px=width_px,
                height_px=height_px,
                max_w=max_w,
                max_h=max_h,
                allow_upscale=options.allow_upscale,
            )

            # (Optional) Resample large images to a reasonable DPI.
            # By default, resample_large_images=False → this block is skipped.
            if options.resample_large_images and options.max_dpi:
                img, width_px, height_px, draw_w, draw_h = _maybe_resample_to_dpi(
                    img=img,
                    width_px=width_px,
                    height_px=height_px,
                    draw_w=draw_w,
                    draw_h=draw_h,
                    max_dpi=options.max_dpi,
                    allow_upscale=options.allow_upscale,
                )

            x = (page_width - draw_w) / 2

            if options.vertical_align == "top":
                y = page_height - margin_top - draw_h
            elif options.vertical_align == "bottom":
                y = margin_bottom
            else:  # "center"
                top_area = page_height - margin_top
                bottom_area = margin_bottom
                available_h = top_area - bottom_area
                y = bottom_area + (available_h - draw_h) / 2

            # New Page
            if start_new_page or idx > 0:
                c.showPage()

            img_reader = ImageReader(img)
            c.drawImage(img_reader, x, y, draw_w, draw_h)

            any_drawn = True

        except Exception as exc:
            logger.error(f"Failed to process image: {img_path}", exc)
            continue

    return any_drawn


def _compute_draw_size_contain(
    width_px: int,
    height_px: int,
    max_w: float,
    max_h: float,
    allow_upscale: bool,
) -> tuple[float, float]:
    """
    Calculates dimensions for the 'contain' mode:
    the image is scaled down to fit entirely within (max_w, max_h),
    while preserving its aspect ratio.
    """
    if width_px <= 0 or height_px <= 0:
        return 0.0, 0.0

    scale_w = max_w / float(width_px)
    scale_h = max_h / float(height_px)
    scale = min(scale_w, scale_h)

    if not allow_upscale:
        scale = min(scale, 1.0)

    draw_w = width_px * scale
    draw_h = height_px * scale
    return draw_w, draw_h


def _is_landscape(image_path: Path) -> bool:
    """Returns True if the image is wider than tall after EXIF orientation."""
    try:
        with Image.open(image_path) as im_raw:
            img = ImageOps.exif_transpose(im_raw)
            w, h = img.size
            return w > h
    except Exception:
        return False


def draw_image_pair(
    c: canvas.Canvas,
    image_path_1: Path,
    image_path_2: Path,
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_top: float,
    margin_bottom: float,
    start_new_page: bool = True,
    options: ImageRenderOptions | None = None,
    gap: float = 8.0,
) -> bool:
    """Renders two landscape images stacked vertically on one page."""
    options = options or ImageRenderOptions()
    if start_new_page:
        c.showPage()
    max_w = page_width - 2 * margin_left
    half_h = (page_height - margin_top - margin_bottom - gap) / 2
    slot_tops = [
        page_height - margin_top,
        page_height - margin_top - half_h - gap,
    ]
    any_drawn = False
    for idx, img_path in enumerate((Path(image_path_1), Path(image_path_2))):
        try:
            with Image.open(img_path) as im_raw:
                img = ImageOps.exif_transpose(im_raw).convert("RGB")
            width_px, height_px = img.size
            draw_w, draw_h = _compute_draw_size_contain(
                width_px=width_px,
                height_px=height_px,
                max_w=max_w,
                max_h=half_h,
                allow_upscale=options.allow_upscale,
            )
            x = (page_width - draw_w) / 2
            y = slot_tops[idx] - draw_h
            img_reader = ImageReader(img)
            c.drawImage(img_reader, x, y, draw_w, draw_h)
            any_drawn = True
        except Exception as exc:
            logger.error(
                "Failed to process image in pair idx=%s path=%s err=%s", idx, img_path, exc
            )
    return any_drawn


def _maybe_resample_to_dpi(
    img,
    width_px: int,
    height_px: int,
    draw_w: float,
    draw_h: float,
    max_dpi: int,
    allow_upscale: bool,
):
    """
    If necessary, reduces the image to a reasonable DPI
    to avoid bloating the PDF excessively.
    """
    if width_px <= 0 or height_px <= 0:
        return img, width_px, height_px, draw_w, draw_h

    target_px_w = int(draw_w / 72.0 * max_dpi)
    target_px_h = int(draw_h / 72.0 * max_dpi)

    if target_px_w <= 0 or target_px_h <= 0:
        return img, width_px, height_px, draw_w, draw_h

    if width_px <= target_px_w and height_px <= target_px_h:
        return img, width_px, height_px, draw_w, draw_h

    scale_w = target_px_w / float(width_px)
    scale_h = target_px_h / float(height_px)
    scale = min(scale_w, scale_h)

    if scale >= 1.0 and not allow_upscale:
        return img, width_px, height_px, draw_w, draw_h

    new_w = max(1, int(width_px * scale))
    new_h = max(1, int(height_px * scale))

    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Keep draw_w and draw_h unchanged — the size on the page remains the same.
    return img_resized, new_w, new_h, draw_w, draw_h
