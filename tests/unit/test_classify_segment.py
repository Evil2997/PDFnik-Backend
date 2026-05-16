"""
Тесты для _classify_segment и вспомогательных эвристик в create_pdf.py.

Намеренно не тестируем рендеринг (canvas) — только pure-Python логику
сегментации и классификации текста.
"""
import sys
from types import SimpleNamespace

import pytest

# Stub pdfnik_contracts.pdf_content с минимально необходимыми классами
_contracts = sys.modules.get("pdfnik_contracts.pdf_content")
if _contracts is None:
    import types
    _contracts = types.ModuleType("pdfnik_contracts.pdf_content")
    sys.modules["pdfnik_contracts"] = types.ModuleType("pdfnik_contracts")
    sys.modules["pdfnik_contracts.pdf_content"] = _contracts


class _PdfTextEntity:
    def __init__(self, *, type, offset, length, url=None):
        self.type = type
        self.offset = offset
        self.length = length
        self.url = url


class _PdfRichText:
    def __init__(self, *, text: str, entities=None):
        self.text = text
        self.entities = entities or []


# Монтируем в stub-модуль
_contracts.PdfRichText = _PdfRichText
_contracts.PdfTextEntity = _PdfTextEntity
_contracts.PdfBlock = object
_contracts.PdfTextBlock = object
_contracts.PdfParagraphBlock = SimpleNamespace
_contracts.PdfHeadingBlock = SimpleNamespace
_contracts.PdfListBlock = SimpleNamespace
_contracts.PdfPriceRow = SimpleNamespace
_contracts.PdfPriceTableBlock = SimpleNamespace
_contracts.PdfBlockType = SimpleNamespace(PARAGRAPH="paragraph", HEADING="heading", LIST="list", PRICE_TABLE="price_table")
_contracts.PdfImageBlock = object

# Теперь можно импортировать
from main_app.domain.work_with_pdf.create_pdf import (
    _classify_segment,
    _is_heading,
    _looks_like_field_line,
    _is_signature_segment,
    _try_split_price_line,
    _segment_by_blank_lines,
    _normalize_text,
)


def rt(text: str) -> _PdfRichText:
    return _PdfRichText(text=text)


# ---------------------------------------------------------------------------
# _is_heading
# ---------------------------------------------------------------------------

class TestIsHeading:
    def test_uppercase_short(self):
        assert _is_heading(rt("MENU")) is True

    def test_ends_with_colon(self):
        assert _is_heading(rt("Zutaten:")) is True

    def test_long_line_not_heading(self):
        long = "This is a very long line that definitely should not be treated as heading at all"
        assert _is_heading(rt(long)) is False

    def test_ends_with_dot_not_heading(self):
        assert _is_heading(rt("SHORT.")) is False

    def test_empty_not_heading(self):
        assert _is_heading(rt("")) is False

    def test_normal_sentence_not_heading(self):
        assert _is_heading(rt("Please review the following items")) is False


# ---------------------------------------------------------------------------
# _looks_like_field_line
# ---------------------------------------------------------------------------

class TestLooksLikeFieldLine:
    def test_kundennummer(self):
        assert _looks_like_field_line("Kundennummer: 12345") is True

    def test_betreff(self):
        assert _looks_like_field_line("Betreff: Rechnung") is True

    def test_colon_at_end(self):
        assert _looks_like_field_line("Zu Punkt 1:") is True

    def test_colon_too_far(self):
        # двоеточие далеко от начала — не поле
        assert _looks_like_field_line("Lorem ipsum dolor sit amet: value") is False

    def test_no_colon(self):
        assert _looks_like_field_line("Just a sentence") is False

    def test_empty(self):
        assert _looks_like_field_line("") is False


# ---------------------------------------------------------------------------
# _is_signature_segment
# ---------------------------------------------------------------------------

class TestIsSignatureSegment:
    def test_german_greeting(self):
        assert _is_signature_segment(rt("Mit freundlichen Grüßen\nMax Mustermann")) is True

    def test_hochachtungsvoll(self):
        assert _is_signature_segment(rt("Hochachtungsvoll")) is True

    def test_date_in_short_block(self):
        seg = rt("Berlin, 12.03.2024\nMax Mustermann")
        assert _is_signature_segment(seg) is True

    def test_regular_paragraph(self):
        assert _is_signature_segment(rt("This is just a regular paragraph.")) is False

    def test_empty(self):
        assert _is_signature_segment(rt("")) is False


# ---------------------------------------------------------------------------
# _try_split_price_line
# ---------------------------------------------------------------------------

class TestTrySplitPriceLine:
    def test_euro_dash(self):
        result = _try_split_price_line("Espresso — 2,50 €")
        assert result is not None
        name, price = result
        assert "Espresso" in name
        assert "2,50" in price

    def test_colon_separator(self):
        result = _try_split_price_line("Latte Macchiato: 3.90 EUR")
        assert result is not None

    def test_no_price(self):
        assert _try_split_price_line("Just a regular line") is None

    def test_price_only_no_name(self):
        # нет имени до разделителя
        assert _try_split_price_line("— 5,00 €") is None

    def test_integer_price(self):
        result = _try_split_price_line("Wasser — 1 €")
        assert result is not None


# ---------------------------------------------------------------------------
# _classify_segment — центральный классификатор
# ---------------------------------------------------------------------------

class TestClassifySegment:
    def test_heading_uppercase(self):
        assert _classify_segment(rt("SPEISEKARTE")) == "heading"

    def test_heading_colon(self):
        assert _classify_segment(rt("Vorspeisen:")) == "heading"

    def test_paragraph_single_line(self):
        assert _classify_segment(rt("This is a regular sentence.")) == "paragraph"

    def test_price_table(self):
        text = "Espresso — 2,50 €\nLatte — 3,90 €\nKapuziner — 3,50 €"
        assert _classify_segment(rt(text)) == "price_table"

    def test_list_with_explicit_bullets(self):
        text = "• Tomaten\n• Gurken\n• Paprika"
        assert _classify_segment(rt(text)) == "list"

    def test_list_with_dashes(self):
        text = "- Tomaten\n- Gurken\n- Paprika"
        assert _classify_segment(rt(text)) == "list"

    def test_list_numbered(self):
        text = "1. Erster Punkt\n2. Zweiter Punkt\n3. Dritter Punkt"
        assert _classify_segment(rt(text)) == "list"

    def test_implicit_list_needs_3_items(self):
        # только 2 коротких строки без точки и без буллетов — НЕ список
        text = "Kurze Zeile\nNoch eine"
        assert _classify_segment(rt(text)) == "paragraph"

    def test_implicit_list_3_items(self):
        text = "Kurze Zeile eins\nKurze Zeile zwei\nKurze Zeile drei"
        assert _classify_segment(rt(text)) == "list"

    def test_field_block_stays_paragraph(self):
        text = "Kundennummer: 12345\nDatum: 01.01.2024\nBetreff: Rechnung"
        assert _classify_segment(rt(text)) == "paragraph"

    def test_signature_stays_paragraph(self):
        text = "Mit freundlichen Grüßen\nMax Mustermann"
        assert _classify_segment(rt(text)) == "paragraph"

    def test_sentences_with_dots_stay_paragraph(self):
        text = "Dies ist ein Satz.\nDies ist noch ein Satz.\nUnd noch einer."
        # заканчиваются на точку → не список
        assert _classify_segment(rt(text)) == "paragraph"


# ---------------------------------------------------------------------------
# _segment_by_blank_lines
# ---------------------------------------------------------------------------

class TestSegmentByBlankLines:
    def test_single_blank_line_stays_in_segment(self):
        text = "line1\n\nline2"
        segs = _segment_by_blank_lines(rt(text))
        # 1 пустая строка не разбивает на сегменты
        assert len(segs) == 1

    def test_double_blank_line_splits(self):
        text = "line1\n\n\nline2"
        segs = _segment_by_blank_lines(rt(text))
        assert len(segs) == 2
        assert segs[0].text.strip() == "line1"
        assert segs[1].text.strip() == "line2"

    def test_empty_text(self):
        segs = _segment_by_blank_lines(rt(""))
        assert segs == [] or all(s.text.strip() == "" for s in segs)

    def test_trailing_blanks_removed(self):
        text = "line1\n\n\nline2\n\n"
        segs = _segment_by_blank_lines(rt(text))
        assert len(segs) == 2
        assert segs[-1].text.strip() == "line2"


# ---------------------------------------------------------------------------
# _normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_crlf_to_lf(self):
        assert _normalize_text("a\r\nb") == "a\nb"

    def test_trailing_spaces_stripped(self):
        assert _normalize_text("line   \nother") == "line\nother"

    def test_cr_to_lf(self):
        assert _normalize_text("a\rb") == "a\nb"