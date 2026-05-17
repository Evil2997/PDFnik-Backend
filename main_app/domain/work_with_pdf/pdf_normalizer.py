# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/domain/work_with_pdf/pdf_normalizer.py
# repo: PDFnik-Backend

"""
Normalization and classification of PDF blocks.

Accepts PdfTextBlock objects → returns structured blocks:
paragraph / heading / list / price_table.

Public API:
normalize_document_blocks(blocks) -> list[PdfBlock]
"""

import re

from pdfnik_contracts.pdf_content import (
    PdfBlock,
    PdfHeadingBlock,
    PdfListBlock,
    PdfParagraphBlock,
    PdfPriceRow,
    PdfPriceTableBlock,
    PdfRichText,
    PdfTextBlock,
    PdfTextEntity,
)

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(
    r"(?i)(?:€|eur|euro)?\s*\d{1,3}(?:[ .]\d{3})*(?:[.,]\d{2})?\s*(?:€|eur|euro)?"
)
_SEP_RE = re.compile(r"\s*(?:—|–|-|:)\s+")  # noqa: RUF001
_BULLET_RE = re.compile(r"^\s*(?:[•\-\*\u2013\u2014]|(?:\d+[\.\)]))\s+")

_SIGNATURE_MARKERS = (
    "mit freundlichen grüßen",
    "freundliche grüße",
    "mit freundlichem gruß",
    "hochachtungsvoll",
    "unterschrift",
)


# ---------------------------------------------------------------------------
# RichText utilities
# ---------------------------------------------------------------------------


def _normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    return s


def _slice_richtext(rt: PdfRichText, start: int, end: int) -> PdfRichText:
    """Safe PdfRichText slice: preserve entities, recalculate offset/length."""
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
    text = rt.text
    if text == "":
        return [PdfRichText(text="", entities=[])]

    lines: list[PdfRichText] = []
    line_start = 0
    for i, ch in enumerate(text):
        if ch == "\n":
            lines.append(_slice_richtext(rt, line_start, i))
            line_start = i + 1
    lines.append(_slice_richtext(rt, line_start, len(text)))
    return lines


def _join_richtext_lines(lines: list[PdfRichText]) -> PdfRichText:
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


# ---------------------------------------------------------------------------
# Classifier heuristics
# ---------------------------------------------------------------------------


def _is_heading(segment: PdfRichText) -> bool:
    t = segment.text.strip()
    if not t:
        return False
    if len(t) <= 60 and not t.endswith(".") and (t.endswith(":") or t.isupper()):
        return True
    return False


def _looks_like_field_line(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    colon = t.find(":")
    if colon == -1:
        return False
    if colon == len(t) - 1:
        return True
    return colon <= 25


def _is_signature_segment(seg: PdfRichText) -> bool:
    t = seg.text.strip().lower()
    if not t:
        return False
    if any(m in t for m in _SIGNATURE_MARKERS):
        return True
    lines = [x.strip() for x in seg.text.split("\n") if x.strip()]
    if 2 <= len(lines) <= 4 and any(re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", ln) for ln in lines):
        return True
    return False


def _try_split_price_line(line: str) -> tuple[str, str] | None:
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


def _classify_segment(seg: PdfRichText) -> str:
    """Returns: 'heading' | 'price_table' | 'list' | 'paragraph'"""
    if _is_signature_segment(seg):
        return "paragraph"

    raw_lines = seg.text.split("\n")
    lines = [ln for ln in raw_lines if ln.strip() != ""]

    if len(lines) == 1:
        if _is_heading(seg):
            return "heading"
        return "paragraph"

    field_hits = sum(1 for ln in lines if _looks_like_field_line(ln))
    if field_hits >= max(2, int(0.6 * len(lines))):
        return "paragraph"

    price_hits = sum(1 for ln in lines if _try_split_price_line(ln) is not None)
    if price_hits >= max(2, int(0.6 * len(lines))):
        return "price_table"

    list_hits = 0
    explicit_bullets = 0
    for ln in lines:
        if _BULLET_RE.match(ln):
            list_hits += 1
            explicit_bullets += 1
            continue
        s = ln.strip()
        if _looks_like_field_line(s):
            continue
        if len(s) <= 120 and not s.endswith("."):
            list_hits += 1

    if explicit_bullets == 0:
        if list_hits >= 3 and list_hits >= int(0.7 * len(lines)):
            return "list"
    else:
        if list_hits >= max(2, int(0.7 * len(lines))):
            return "list"

    return "paragraph"


# ---------------------------------------------------------------------------
# Segmenter
# ---------------------------------------------------------------------------


def _segment_by_blank_lines(rt: PdfRichText) -> list[PdfRichText]:
    """
    Split into segments only at 2 or more consecutive empty lines.
    A single empty line remains within the segment.
    """
    lines = _split_richtext_lines(rt)

    segments: list[list[PdfRichText]] = []
    current: list[PdfRichText] = []
    blank_run = 0

    for ln in lines:
        is_blank = ln.text.strip() == ""
        if is_blank:
            blank_run += 1
            current.append(ln)
            if blank_run >= 2:
                while current and current[-1].text.strip() == "":
                    current.pop()
                if current:
                    segments.append(current)
                current = []
                blank_run = 0
            continue

        blank_run = 0
        current.append(ln)

    while current and current[-1].text.strip() == "":
        current.pop()
    if current:
        segments.append(current)

    return [_join_richtext_lines(seg) for seg in segments]


# ---------------------------------------------------------------------------
# Block builder
# ---------------------------------------------------------------------------


def _build_blocks_from_segment(seg: PdfRichText) -> list[PdfBlock]:
    kind = _classify_segment(seg)

    if kind == "heading":
        return [PdfHeadingBlock(content=PdfRichText(text=seg.text.strip(), entities=seg.entities))]

    if kind == "price_table":
        rows: list[PdfPriceRow] = []
        line_rts = _split_richtext_lines(seg)
        for ln_rt in line_rts:
            raw = ln_rt.text
            split = _try_split_price_line(raw)
            if split is None:
                return [PdfParagraphBlock(content=seg)]
            name_s, price_s = split

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

        leading_spaces = []
        for ln in line_rts:
            m = re.match(r"^(\s+)", ln.text)
            leading_spaces.append(len(m.group(1)) if m else 0)
        base_indent = min(leading_spaces) if leading_spaces else 0
        indent_level = int(base_indent / 2) if base_indent >= 2 else 0

        for ln_rt in line_rts:
            t = ln_rt.text
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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
    Leave PdfImageBlock as is.
    Transform PdfTextBlock into paragraph / list / price_table / heading.
    Skip blocks that are already structural.
    """
    out: list[PdfBlock] = []
    for b in blocks:
        if isinstance(b, PdfTextBlock):
            out.extend(_normalize_text_block(b))
        else:
            out.append(b)
    return out
