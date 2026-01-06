import re
from pathlib import Path

from PIL import Image, ImageOps
from pdfnik_contracts.pdf_content import (
    PdfBlock,
    PdfTextBlock,
    PdfRichText,
    PdfTextEntity,
    PdfParagraphBlock,
    PdfHeadingBlock,
    PdfListBlock,
    PdfPriceRow,
    PdfPriceTableBlock, PdfBlockType, PdfImageBlock,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase import pdfmetrics as rl_pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from main_app.core.constants import FONT_TYPE, FONT_PATH, FILES_ROOT
from main_app.core.logger import logger
from main_app.domain.work_with_pdf.actions.images.draw_images import draw_images
from main_app.domain.work_with_pdf.actions.text.wrap_by_width import wrap_by_width
from main_app.domain.work_with_pdf.models.image_render_options import ImageRenderOptions
from main_app.domain.work_with_pdf.models.pdf_layout import PdfLayout

pdfmetrics.registerFont(TTFont(FONT_TYPE, FONT_PATH))


def create_pdf_from_blocks(
        blocks: list[PdfBlock],
        output_path: Path,
) -> None:
    logger.info(f"create_pdf: start, output={output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    page_width, page_height = A4

    layout = PdfLayout()
    c.setFont(layout.font_name, layout.font_size)

    # ✅ КЛЮЧ: превращаем сырой TEXT в структурные блоки
    blocks = normalize_document_blocks(blocks)

    has_content = False
    current_y: float | None = None

    try:
        for block in blocks:
            # -------- TEXT-LIKE (structured) --------
            if getattr(block, "type", None) == PdfBlockType.PARAGRAPH:
                logger.info("Rendering paragraph block")
                drawn, current_y = _draw_paragraph(
                    c=c, rt=block.content, layout=layout,
                    page_width=page_width, page_height=page_height, y=current_y
                )
                has_content = has_content or drawn

            elif getattr(block, "type", None) == PdfBlockType.HEADING:
                logger.info("Rendering heading block")
                drawn, current_y = _draw_heading(
                    c=c, rt=block.content, layout=layout,
                    page_width=page_width, page_height=page_height, y=current_y
                )
                has_content = has_content or drawn

            elif getattr(block, "type", None) == PdfBlockType.LIST:
                logger.info("Rendering list block")
                drawn, current_y = _draw_list(
                    c=c, lb=block, layout=layout,
                    page_width=page_width, page_height=page_height, y=current_y
                )
                has_content = has_content or drawn

            elif getattr(block, "type", None) == PdfBlockType.PRICE_TABLE:
                logger.info("Rendering price table block")
                drawn, current_y = _draw_price_table(
                    c=c, pb=block, layout=layout,
                    page_width=page_width, page_height=page_height, y=current_y
                )
                has_content = has_content or drawn

            # -------- BACKWARD COMPAT: raw TEXT (если вдруг прилетит) --------
            elif isinstance(block, PdfTextBlock):
                logger.info("Rendering raw text block (fallback)")
                drawn, current_y = _draw_paragraph(
                    c=c, rt=block.content, layout=layout,
                    page_width=page_width, page_height=page_height, y=current_y
                )
                has_content = has_content or drawn

            # -------- IMAGE --------
            elif isinstance(block, PdfImageBlock):
                logger.info("Rendering image block")
                image_path = FILES_ROOT / block.image.storage_key

                options = ImageRenderOptions(vertical_align="top", rotate_horizontal=False)
                draw_h = _estimate_image_draw_height(
                    image_path,
                    page_width=page_width,
                    page_height=page_height,
                    margin_left=layout.left_margin,
                    margin_top=layout.top_margin,
                    margin_bottom=layout.bottom_margin,
                    options=options,
                )

                drawn = draw_images(
                    c=c,
                    image_paths=[image_path],
                    page_width=page_width,
                    page_height=page_height,
                    margin_left=layout.left_margin,
                    margin_top=layout.top_margin,
                    margin_bottom=layout.bottom_margin,
                    start_new_page=has_content,
                    options=options,
                )
                has_content = has_content or drawn

                spacing = layout.line_height
                current_y = (page_height - layout.top_margin - draw_h) - spacing

                if block.caption:
                    drawn2, current_y = _draw_paragraph(
                        c=c, rt=block.caption, layout=layout,
                        page_width=page_width, page_height=page_height, y=current_y
                    )
                    has_content = has_content or drawn2

            else:
                logger.warning(f"Unknown block type: {getattr(block, 'type', None)}")

        if not has_content:
            c.drawString(layout.left_margin, page_height - layout.top_margin, "Пустой PDF (нет содержимого)")

        c.save()
        logger.info(f"create_pdf: saved PDF to {output_path}")

    except Exception as e:
        logger.error(f"create_pdf: error while generating PDF: {e}")
        raise


# ----------------------------
# RichText utilities (safe slicing)
# ----------------------------

def _normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # убираем хвостовые пробелы в строках (стабильный ввод для парсера)
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    return s


def _slice_richtext(rt: PdfRichText, start: int, end: int) -> PdfRichText:
    """
    Безопасный слайс PdfRichText: сохраняем entities, пересчитываем offset/length.
    Обрезаем entity по пересечению.
    """
    start = max(0, start)
    end = max(start, end)
    sub_text = rt.text[start:end]
    new_entities: list[PdfTextEntity] = []

    for e in rt.entities:
        e_start = e.offset
        e_end = e.offset + e.length
        inter_start = max(start, e_start)
        inter_end = min(end, e_end)
        if inter_end <= inter_start:
            continue

        new_entities.append(
            PdfTextEntity(
                type=e.type,
                offset=inter_start - start,
                length=inter_end - inter_start,
                url=e.url,
            )
        )

    return PdfRichText(text=sub_text, entities=new_entities)


def _split_richtext_lines(rt: PdfRichText) -> list[PdfRichText]:
    """
    Split по '\n' с сохранением entities.
    Возвращает строки БЕЗ '\n' в конце.
    """
    text = rt.text
    if text == "":
        return [PdfRichText(text="", entities=[])]

    lines: list[PdfRichText] = []
    line_start = 0
    for i, ch in enumerate(text):
        if ch == "\n":
            lines.append(_slice_richtext(rt, line_start, i))
            line_start = i + 1
    # tail
    lines.append(_slice_richtext(rt, line_start, len(text)))
    return lines


def _join_richtext_lines(lines: list[PdfRichText]) -> PdfRichText:
    """
    Склеивает lines через '\n'. Entities сдвигаются.
    """
    out_text_parts: list[str] = []
    out_entities: list[PdfTextEntity] = []
    offset = 0
    for idx, line in enumerate(lines):
        out_text_parts.append(line.text)
        for e in line.entities:
            out_entities.append(
                PdfTextEntity(
                    type=e.type,
                    offset=e.offset + offset,
                    length=e.length,
                    url=e.url,
                )
            )
        offset += len(line.text)
        if idx < len(lines) - 1:
            out_text_parts.append("\n")
            offset += 1
    return PdfRichText(text="".join(out_text_parts), entities=out_entities)


# ----------------------------
# Segmenter / Classifier / Builder
# ----------------------------

_PRICE_RE = re.compile(
    r"(?i)(?:€|eur|euro)?\s*\d{1,3}(?:[ .]\d{3})*(?:[.,]\d{2})?\s*(?:€|eur|euro)?"
)

_SEP_RE = re.compile(r"\s+(?:—|–|-|:)\s+")  # "name — price", "name - price", "name: price"

_BULLET_RE = re.compile(r"^\s*(?:[•\-\*\u2013\u2014]|(?:\d+[\.\)]))\s+")


def _is_heading(segment: PdfRichText) -> bool:
    t = segment.text.strip()
    if not t:
        return False
    # коротко, без точки, часто заканчивается ":" и перед "структурой"
    if len(t) <= 60 and not t.endswith(".") and (t.endswith(":") or t.isupper()):
        return True
    return False


def _try_split_price_line(line: str) -> tuple[str, str] | None:
    """
    Возвращает (name, price) или None
    """
    if not _PRICE_RE.search(line):
        return None
    parts = _SEP_RE.split(line, maxsplit=1)
    if len(parts) != 2:
        return None
    name, price = parts[0].strip(), parts[1].strip()
    if not name or not price:
        return None
    if not _PRICE_RE.search(price):
        return None
    return name, price


def _segment_by_blank_lines(rt: PdfRichText) -> list[PdfRichText]:
    lines = _split_richtext_lines(rt)
    segments: list[list[PdfRichText]] = []
    current: list[PdfRichText] = []

    for ln in lines:
        if ln.text.strip() == "":
            if current:
                segments.append(current)
                current = []
            else:
                # последовательные пустые строки — просто пропускаем
                continue
        else:
            current.append(ln)

    if current:
        segments.append(current)

    return [_join_richtext_lines(seg) for seg in segments]


def _classify_segment(seg: PdfRichText) -> str:
    """
    returns: "heading" | "price_table" | "list" | "paragraph"
    """
    lines = seg.text.split("\n")
    if len(lines) == 1:
        if _is_heading(seg):
            return "heading"
        return "paragraph"

    # price_table: большинство строк похоже на "name — price"
    price_hits = 0
    for ln in lines:
        if _try_split_price_line(ln) is not None:
            price_hits += 1
    if price_hits >= max(2, int(0.6 * len(lines))):
        return "price_table"

    # list: большинство строк “короткие” или с буллетом/нумерацией
    list_hits = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if _BULLET_RE.match(ln):
            list_hits += 1
            continue
        # эвристика “пункт списка”: короткая строка без точки в конце
        if len(s) <= 120 and not s.endswith("."):
            list_hits += 1

    if list_hits >= max(2, int(0.7 * len(lines))):
        return "list"

    return "paragraph"


def _build_blocks_from_segment(seg: PdfRichText) -> list[PdfBlock]:
    kind = _classify_segment(seg)

    if kind == "heading":
        return [PdfHeadingBlock(content=PdfRichText(text=seg.text.strip(), entities=seg.entities))]

    if kind == "price_table":
        rows: list[PdfPriceRow] = []
        # rebuild rows line-by-line as richtext parts (важно для future entities)
        line_rts = _split_richtext_lines(seg)
        for ln_rt in line_rts:
            raw = ln_rt.text
            split = _try_split_price_line(raw)
            if split is None:
                # деградация: если строка “не распарсилась” — кидаем в paragraph
                return [PdfParagraphBlock(content=seg)]
            name_s, price_s = split

            # находим границы name/price в оригинальной строке
            # (упрощённо: ищем first occurrence of price_s)
            idx = raw.find(price_s)
            if idx <= 0:
                return [PdfParagraphBlock(content=seg)]

            name_rt = _slice_richtext(ln_rt, 0, idx)
            price_rt = _slice_richtext(ln_rt, idx, len(raw))

            rows.append(
                PdfPriceRow(
                    name=PdfRichText(text=name_rt.text.strip(), entities=name_rt.entities),
                    price=PdfRichText(text=price_rt.text.strip(), entities=price_rt.entities),
                )
            )
        return [PdfPriceTableBlock(rows=rows)]

    if kind == "list":
        items: list[PdfRichText] = []
        line_rts = _split_richtext_lines(seg)

        # indent_level (по leading spaces) — грубо, но реально работает на “скопированном” тексте
        leading_spaces = []
        for ln in line_rts:
            m = re.match(r"^(\s+)", ln.text)
            leading_spaces.append(len(m.group(1)) if m else 0)
        base_indent = min(leading_spaces) if leading_spaces else 0
        indent_level = int(base_indent / 2) if base_indent >= 2 else 0

        for ln_rt in line_rts:
            t = ln_rt.text
            # убираем маркеры/нумерацию
            m = _BULLET_RE.match(t)
            cut = m.end() if m else 0
            item_rt = _slice_richtext(ln_rt, cut, len(t))
            item_text = item_rt.text.strip()
            if item_text:
                items.append(PdfRichText(text=item_text, entities=item_rt.entities))

        if len(items) >= 2:
            return [PdfListBlock(items=items, indent_level=indent_level, tight=True)]
        return [PdfParagraphBlock(content=seg)]

    return [PdfParagraphBlock(content=seg)]


def _normalize_text_block(tb: PdfTextBlock) -> list[PdfBlock]:
    normalized = _normalize_text(tb.content.text)
    rt = PdfRichText(text=normalized, entities=tb.content.entities)

    segments = _segment_by_blank_lines(rt)

    out: list[PdfBlock] = []
    for seg in segments:
        out.extend(_build_blocks_from_segment(seg))
    return out


def normalize_document_blocks(blocks: list[PdfBlock]) -> list[PdfBlock]:
    """
    PdfImageBlock оставляем как есть.
    PdfTextBlock превращаем в paragraph/list/price_table/heading.
    Уже структурные блоки — пропускаем.
    """
    out: list[PdfBlock] = []
    for b in blocks:
        if isinstance(b, PdfTextBlock):
            out.extend(_normalize_text_block(b))
        else:
            out.append(b)
    return out


# ----------------------------
# Rendering helpers (by type)
# ----------------------------

def _ensure_page(c: canvas.Canvas, layout: PdfLayout, page_height: float, y: float) -> float:
    if y < layout.bottom_margin:
        c.showPage()
        c.setFont(layout.font_name, layout.font_size)
        return page_height - layout.top_margin
    return y


def _draw_paragraph(
        c: canvas.Canvas,
        rt: PdfRichText,
        layout: PdfLayout,
        page_width: float,
        page_height: float,
        y: float | None,
) -> tuple[bool, float]:
    # используем текущую логику как “paragraph renderer”, но без split по абзацам внутри
    if y is None:
        y = page_height - layout.top_margin

    max_w = page_width - layout.left_margin - layout.right_margin
    c.setFont(layout.font_name, layout.font_size)

    drawn = False
    # paragraph — это один сегмент, в нём могут быть \n (например адрес/реквизиты)
    for idx, line in enumerate(rt.text.split("\n")):
        if line.strip() == "":
            y = _ensure_page(c, layout, page_height, y)
            y -= max(layout.line_height, layout.paragraph_spacing)
            continue

        wrapped = wrap_by_width(line, max_w, layout.font_name, layout.font_size) or [""]
        for i, wline in enumerate(wrapped):
            y = _ensure_page(c, layout, page_height, y)
            c.drawString(layout.left_margin, y, wline)
            drawn = True
            if i < len(wrapped) - 1:
                y -= layout.wrap_line_height
        if idx < len(rt.text.split("\n")) - 1:
            y -= layout.line_height

    y -= layout.block_spacing
    return drawn, y


def _draw_heading(
        c: canvas.Canvas,
        rt: PdfRichText,
        layout: PdfLayout,
        page_width: float,
        page_height: float,
        y: float | None,
) -> tuple[bool, float]:
    if y is None:
        y = page_height - layout.top_margin

    y = _ensure_page(c, layout, page_height, y)
    c.setFont(layout.font_name, layout.heading_font_size)
    c.drawString(layout.left_margin, y, rt.text.strip())
    c.setFont(layout.font_name, layout.font_size)

    y -= layout.heading_spacing
    y -= layout.block_spacing
    return True, y


def _draw_list(
        c: canvas.Canvas,
        lb: PdfListBlock,
        layout: PdfLayout,
        page_width: float,
        page_height: float,
        y: float | None,
) -> tuple[bool, float]:
    if y is None:
        y = page_height - layout.top_margin

    c.setFont(layout.font_name, layout.font_size)

    x_bullet = layout.left_margin + lb.indent_level * layout.list_indent_step
    x_text = x_bullet + layout.bullet_gap
    max_w = page_width - layout.right_margin - x_text

    drawn = False
    item_gap = layout.wrap_line_height if lb.tight else layout.line_height

    for item in lb.items:
        # bullet on first line
        wrapped = wrap_by_width(item.text, max_w, layout.font_name, layout.font_size) or [""]

        # first line
        y = _ensure_page(c, layout, page_height, y)
        c.drawString(x_bullet, y, lb.bullet)
        c.drawString(x_text, y, wrapped[0])
        drawn = True

        # hanging lines
        for wline in wrapped[1:]:
            y -= layout.wrap_line_height
            y = _ensure_page(c, layout, page_height, y)
            c.drawString(x_text, y, wline)

        y -= item_gap

    y -= layout.block_spacing
    return drawn, y


def _draw_price_table(
        c: canvas.Canvas,
        pb: PdfPriceTableBlock,
        layout: PdfLayout,
        page_width: float,
        page_height: float,
        y: float | None,
) -> tuple[bool, float]:
    if y is None:
        y = page_height - layout.top_margin

    c.setFont(layout.font_name, layout.font_size)

    x_left = layout.left_margin
    x_right = page_width - layout.right_margin

    drawn = False
    for row in pb.rows:
        price = row.price.text.strip()
        name = row.name.text.strip()

        y = _ensure_page(c, layout, page_height, y)

        price_w = rl_pdfmetrics.stringWidth(price, layout.font_name, layout.font_size)
        x_price = x_right - price_w
        max_name_w = max(10.0, (x_price - layout.price_gap) - x_left)

        wrapped_name = wrap_by_width(name, max_name_w, layout.font_name, layout.font_size) or [""]

        # первая строка: name + price
        c.drawString(x_left, y, wrapped_name[0])
        c.drawString(x_price, y, price)
        drawn = True

        # доп строки: только name
        for extra in wrapped_name[1:]:
            y -= layout.wrap_line_height
            y = _ensure_page(c, layout, page_height, y)
            c.drawString(x_left, y, extra)

        y -= layout.line_height

    y -= layout.block_spacing
    return drawn, y


# ----------------------------
# Existing image estimate helper stays unchanged
# ----------------------------

def _estimate_image_draw_height(
        image_path: Path,
        *,
        page_width: float,
        page_height: float,
        margin_left: float,
        margin_top: float,
        margin_bottom: float,
        options: ImageRenderOptions,
) -> float:
    """
    Оценивает высоту, на которую draw_images нарисует картинку (режим contain),
    чтобы мы могли поставить курсор текста ПОД изображением и не накладывать текст поверх.

    Важно: это оценка по тем же правилам (EXIF transpose + rotate horizontal + contain).
    """
    max_w = page_width - 2 * margin_left
    max_h = page_height - margin_top - margin_bottom

    with Image.open(image_path) as im_raw:
        img = ImageOps.exif_transpose(im_raw).convert("RGB")

    width_px, height_px = img.size
    if width_px <= 0 or height_px <= 0:
        return 0.0

    # повторяем логику rotate_horizontal
    is_horizontal = width_px >= height_px
    if options.rotate_horizontal and is_horizontal:
        # cw = -90, ccw = +90
        if options.rotate_direction == "cw":
            img = img.rotate(-90, expand=True)
        else:
            img = img.rotate(90, expand=True)
        width_px, height_px = img.size

    # contain
    scale_w = max_w / float(width_px)
    scale_h = max_h / float(height_px)
    scale = min(scale_w, scale_h)
    if not options.allow_upscale:
        scale = min(scale, 1.0)

    draw_h = height_px * scale
    return float(draw_h)
