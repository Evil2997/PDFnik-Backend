# /home/dmitriy/PycharmProjects/PDFnik-Backend/tests/unit/test_classify_segment.py
# repo: PDFnik-Backend

"""
Tests for the classifier and heuristics in pdf_normalizer.py.

Following the refactoring of create_pdf.py, the classification functions
were moved to pdf_normalizer.py—the imports have been updated accordingly.
"""

import sys
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Stub pdfnik_contracts
# ---------------------------------------------------------------------------

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


_contracts.PdfRichText = _PdfRichText
_contracts.PdfTextEntity = _PdfTextEntity
_contracts.PdfBlock = object
_contracts.PdfTextBlock = object
_contracts.PdfParagraphBlock = lambda **kw: SimpleNamespace(**kw)
_contracts.PdfHeadingBlock = lambda **kw: SimpleNamespace(**kw)
_contracts.PdfListBlock = lambda **kw: SimpleNamespace(**kw)
_contracts.PdfPriceRow = lambda **kw: SimpleNamespace(**kw)
_contracts.PdfPriceTableBlock = lambda **kw: SimpleNamespace(**kw)
_contracts.PdfBlockType = SimpleNamespace(
    PARAGRAPH="paragraph",
    HEADING="heading",
    LIST="list",
    PRICE_TABLE="price_table",
)
_contracts.PdfImageBlock = object

# FIX: Import from pdf_normalizer, not create_pdf.
# Following the refactoring, the classification functions now reside in pdf_normalizer.py.
# create_pdf.py imports reportlab at the module level, which breaks tests
# in environments where reportlab is not installed.
from main_app.domain.work_with_pdf.pdf_normalizer import (  # noqa: E402
    _classify_segment,
    _is_heading,
    _is_signature_segment,
    _looks_like_field_line,
    _normalize_text,
    _segment_by_blank_lines,
    _try_split_price_line,
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
        assert _is_signature_segment(rt("Berlin, 12.03.2024\nMax Mustermann")) is True

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
        assert _try_split_price_line("Latte Macchiato: 3.90 EUR") is not None

    def test_no_price(self):
        assert _try_split_price_line("Just a regular line") is None

    def test_price_only_no_name(self):
        assert _try_split_price_line("— 5,00 €") is None

    def test_integer_price(self):
        assert _try_split_price_line("Wasser — 1 €") is not None


# ---------------------------------------------------------------------------
# _classify_segment
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
        assert _classify_segment(rt("• Tomaten\n• Gurken\n• Paprika")) == "list"

    def test_list_with_dashes(self):
        assert _classify_segment(rt("- Tomaten\n- Gurken\n- Paprika")) == "list"

    def test_list_numbered(self):
        assert (
            _classify_segment(rt("1. Erster Punkt\n2. Zweiter Punkt\n3. Dritter Punkt")) == "list"
        )

    def test_implicit_list_needs_3_items(self):
        assert _classify_segment(rt("Kurze Zeile\nNoch eine")) == "paragraph"

    def test_implicit_list_3_items(self):
        assert (
            _classify_segment(rt("Kurze Zeile eins\nKurze Zeile zwei\nKurze Zeile drei")) == "list"
        )

    def test_field_block_stays_paragraph(self):
        text = "Kundennummer: 12345\nDatum: 01.01.2024\nBetreff: Rechnung"
        assert _classify_segment(rt(text)) == "paragraph"

    def test_signature_stays_paragraph(self):
        assert _classify_segment(rt("Mit freundlichen Grüßen\nMax Mustermann")) == "paragraph"

    def test_sentences_with_dots_stay_paragraph(self):
        text = "Dies ist ein Satz.\nDies ist noch ein Satz.\nUnd noch einer."
        assert _classify_segment(rt(text)) == "paragraph"


# ---------------------------------------------------------------------------
# _segment_by_blank_lines
# ---------------------------------------------------------------------------


class TestSegmentByBlankLines:
    def test_single_blank_line_stays_in_segment(self):
        segs = _segment_by_blank_lines(rt("line1\n\nline2"))
        assert len(segs) == 1

    def test_double_blank_line_splits(self):
        segs = _segment_by_blank_lines(rt("line1\n\n\nline2"))
        assert len(segs) == 2
        assert segs[0].text.strip() == "line1"
        assert segs[1].text.strip() == "line2"

    def test_empty_text(self):
        segs = _segment_by_blank_lines(rt(""))
        assert segs == [] or all(s.text.strip() == "" for s in segs)

    def test_trailing_blanks_removed(self):
        segs = _segment_by_blank_lines(rt("line1\n\n\nline2\n\n"))
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
