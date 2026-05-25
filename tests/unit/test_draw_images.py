from unittest.mock import MagicMock, patch

from main_app.domain.work_with_pdf.actions.images.draw_images import (
    _is_landscape,
    draw_image_pair,
)

_MODULE = "main_app.domain.work_with_pdf.actions.images.draw_images"


def _make_img_mock(w: int, h: int) -> MagicMock:
    m = MagicMock()
    m.size = (w, h)
    m.convert.return_value = m
    m.__enter__ = lambda s: m
    m.__exit__ = MagicMock(return_value=False)
    return m


class TestIsLandscape:
    def test_wide_image_returns_true(self, tmp_path):
        img = _make_img_mock(200, 100)
        with patch(f"{_MODULE}.Image") as mock_image, patch(f"{_MODULE}.ImageOps") as mock_ops:
            mock_image.open.return_value = img
            mock_ops.exif_transpose.return_value = img
            assert _is_landscape(tmp_path / "wide.jpg") is True

    def test_tall_image_returns_false(self, tmp_path):
        img = _make_img_mock(100, 200)
        with patch(f"{_MODULE}.Image") as mock_image, patch(f"{_MODULE}.ImageOps") as mock_ops:
            mock_image.open.return_value = img
            mock_ops.exif_transpose.return_value = img
            assert _is_landscape(tmp_path / "tall.jpg") is False

    def test_square_image_returns_false(self, tmp_path):
        img = _make_img_mock(100, 100)
        with patch(f"{_MODULE}.Image") as mock_image, patch(f"{_MODULE}.ImageOps") as mock_ops:
            mock_image.open.return_value = img
            mock_ops.exif_transpose.return_value = img
            assert _is_landscape(tmp_path / "square.jpg") is False

    def test_returns_false_on_exception(self, tmp_path):
        with patch(f"{_MODULE}.Image") as mock_image:
            mock_image.open.side_effect = OSError("file not found")
            assert _is_landscape(tmp_path / "missing.jpg") is False


class TestDrawImagePair:
    _PAGE_W = 595.0
    _PAGE_H = 842.0
    _MARGIN_L = 60.0
    _MARGIN_T = 80.0
    _MARGIN_B = 60.0

    def _call(self, c, img, tmp_path, **kwargs):
        defaults = {
            "c": c,
            "image_path_1": tmp_path / "a.jpg",
            "image_path_2": tmp_path / "b.jpg",
            "page_width": self._PAGE_W,
            "page_height": self._PAGE_H,
            "margin_left": self._MARGIN_L,
            "margin_top": self._MARGIN_T,
            "margin_bottom": self._MARGIN_B,
        }
        defaults.update(kwargs)
        with (
            patch(f"{_MODULE}.Image") as mock_image,
            patch(f"{_MODULE}.ImageOps") as mock_ops,
            patch(f"{_MODULE}.ImageReader"),
        ):
            mock_image.open.return_value = img
            mock_ops.exif_transpose.return_value = img
            return draw_image_pair(**defaults)

    def test_both_images_drawn_returns_true(self, tmp_path):
        img = _make_img_mock(400, 200)
        c = MagicMock()
        result = self._call(c, img, tmp_path)
        assert result is True
        assert c.drawImage.call_count == 2

    def test_start_new_page_calls_show_page(self, tmp_path):
        img = _make_img_mock(400, 200)
        c = MagicMock()
        self._call(c, img, tmp_path, start_new_page=True)
        c.showPage.assert_called_once()

    def test_no_show_page_when_false(self, tmp_path):
        img = _make_img_mock(400, 200)
        c = MagicMock()
        self._call(c, img, tmp_path, start_new_page=False)
        c.showPage.assert_not_called()

    def test_one_image_fails_still_returns_true(self, tmp_path):
        img_good = _make_img_mock(400, 200)
        c = MagicMock()
        call_count = [0]

        def open_side_effect(path):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("bad image")
            return img_good

        with (
            patch(f"{_MODULE}.Image") as mock_image,
            patch(f"{_MODULE}.ImageOps") as mock_ops,
            patch(f"{_MODULE}.ImageReader"),
        ):
            mock_image.open.side_effect = open_side_effect
            mock_ops.exif_transpose.return_value = img_good
            result = draw_image_pair(
                c=c,
                image_path_1=tmp_path / "a.jpg",
                image_path_2=tmp_path / "b.jpg",
                page_width=self._PAGE_W,
                page_height=self._PAGE_H,
                margin_left=self._MARGIN_L,
                margin_top=self._MARGIN_T,
                margin_bottom=self._MARGIN_B,
            )
        assert result is True

    def test_both_fail_returns_false(self, tmp_path):
        c = MagicMock()
        with (
            patch(f"{_MODULE}.Image") as mock_image,
            patch(f"{_MODULE}.ImageOps"),
            patch(f"{_MODULE}.ImageReader"),
        ):
            mock_image.open.side_effect = OSError("bad image")
            result = draw_image_pair(
                c=c,
                image_path_1=tmp_path / "a.jpg",
                image_path_2=tmp_path / "b.jpg",
                page_width=self._PAGE_W,
                page_height=self._PAGE_H,
                margin_left=self._MARGIN_L,
                margin_top=self._MARGIN_T,
                margin_bottom=self._MARGIN_B,
            )
        assert result is False
