"""
Тесты для fetch_youtube_metadata() в targets.py.

Мокируем run_cmd чтобы не вызывать реальный yt-dlp.
Тестируем: парсинг JSON, неполные данные, ошибки, обрезку description.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from main_app.domain.work_with_pdf.actions.files.audio.targets import (
    fetch_youtube_metadata,
    _DESCRIPTION_MAX_LEN,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run_cmd_result(data: dict) -> MagicMock:
    mock = MagicMock()
    mock.stdout = json.dumps(data)
    return mock


_FULL_METADATA = {
    "title": "How Python Works",
    "channel": "Tech Channel",
    "uploader": "Tech Channel",
    "upload_date": "20240315",
    "duration": 1234.5,
    "view_count": 99999,
    "description": "This is a description of the video.",
    "thumbnail": "https://i.ytimg.com/vi/abc/maxresdefault.jpg",
    "webpage_url": "https://youtube.com/watch?v=abc",
}


# ---------------------------------------------------------------------------
# Успешное получение метаданных
# ---------------------------------------------------------------------------

class TestFetchYouTubeMetadataSuccess:
    def test_basic_fields_parsed(self):
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(_FULL_METADATA),
        ):
            meta = fetch_youtube_metadata("https://youtube.com/watch?v=abc")

        assert meta is not None
        assert meta.title == "How Python Works"
        assert meta.channel == "Tech Channel"
        assert meta.upload_date == "20240315"
        assert meta.duration_sec == 1234.5
        assert meta.view_count == 99999
        assert meta.thumbnail_url == "https://i.ytimg.com/vi/abc/maxresdefault.jpg"

    def test_url_preserved(self):
        url = "https://youtube.com/watch?v=abc"
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(_FULL_METADATA),
        ):
            meta = fetch_youtube_metadata(url)
        assert meta.url == url

    def test_yt_dlp_called_with_correct_args(self):
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(_FULL_METADATA),
        ) as mock_run:
            fetch_youtube_metadata("https://youtube.com/watch?v=abc")

        cmd = mock_run.call_args[0][0]
        assert "yt-dlp" in cmd
        assert "--dump-json" in cmd
        assert "--no-playlist" in cmd
        assert "--quiet" in cmd
        assert "https://youtube.com/watch?v=abc" in cmd

    def test_channel_fallback_to_uploader(self):
        data = {**_FULL_METADATA, "channel": None, "uploader": "Fallback Uploader"}
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(data),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta.channel == "Fallback Uploader"


# ---------------------------------------------------------------------------
# Обрезка description
# ---------------------------------------------------------------------------

class TestDescriptionTruncation:
    def test_long_description_truncated(self):
        long_desc = "x" * (_DESCRIPTION_MAX_LEN + 100)
        data = {**_FULL_METADATA, "description": long_desc}
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(data),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta.description is not None
        assert len(meta.description) <= _DESCRIPTION_MAX_LEN + 1  # +1 for "…"
        assert meta.description.endswith("…")

    def test_short_description_not_truncated(self):
        short_desc = "Short description."
        data = {**_FULL_METADATA, "description": short_desc}
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(data),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta.description == short_desc

    def test_empty_description_becomes_none(self):
        data = {**_FULL_METADATA, "description": ""}
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(data),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta.description is None


# ---------------------------------------------------------------------------
# Неполные / отсутствующие поля
# ---------------------------------------------------------------------------

class TestPartialMetadata:
    def test_minimal_data_only_url(self):
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result({}),
        ):
            meta = fetch_youtube_metadata("https://x.com/minimal")

        assert meta is not None
        assert meta.url == "https://x.com/minimal"
        assert meta.title is None
        assert meta.channel is None
        assert meta.duration_sec is None

    def test_missing_duration(self):
        data = {k: v for k, v in _FULL_METADATA.items() if k != "duration"}
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=_make_run_cmd_result(data),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta.duration_sec is None
        assert meta.duration_str == "неизвестно"


# ---------------------------------------------------------------------------
# Обработка ошибок — всегда возвращает None, не поднимает
# ---------------------------------------------------------------------------

class TestFetchYouTubeMetadataErrors:
    def test_run_cmd_exception_returns_none(self):
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            side_effect=RuntimeError("yt-dlp not found"),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta is None

    def test_invalid_json_returns_none(self):
        mock = MagicMock()
        mock.stdout = "not valid json {{{"
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            return_value=mock,
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta is None

    def test_network_error_returns_none(self):
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            side_effect=ConnectionError("network unreachable"),
        ):
            meta = fetch_youtube_metadata("https://x.com")

        assert meta is None

    def test_private_video_returns_none(self):
        """Приватные видео могут вернуть ошибку от yt-dlp."""
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd",
            side_effect=RuntimeError("This video is private"),
        ):
            meta = fetch_youtube_metadata("https://youtube.com/watch?v=private")

        assert meta is None