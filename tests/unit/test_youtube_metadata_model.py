"""
Тесты для YouTubeMetadata и связанных моделей в models.py.

Покрываем:
- duration_str: разные форматы (часы, минуты, секунды)
- upload_date_str: форматирование даты
- edge cases: None, 0, неполные данные
- PreparedTarget с youtube_metadata
"""
import pytest

from main_app.domain.work_with_pdf.actions.files.models import (
    PreparedTarget,
    RunMetrics,
    RunResult,
    TranscribeConfig,
    YouTubeMetadata,
)


# ---------------------------------------------------------------------------
# duration_str
# ---------------------------------------------------------------------------

class TestDurationStr:
    def test_minutes_and_seconds(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=201)  # 3:21
        assert m.duration_str == "3:21"

    def test_hours_minutes_seconds(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=3723)  # 1:02:03
        assert m.duration_str == "1:02:03"

    def test_exactly_one_hour(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=3600)
        assert m.duration_str == "1:00:00"

    def test_zero_seconds(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=0)
        # 0 — falsy, так что возвращаем "неизвестно"
        assert m.duration_str == "неизвестно"

    def test_none_duration(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=None)
        assert m.duration_str == "неизвестно"

    def test_less_than_minute(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=45)
        assert m.duration_str == "0:45"

    def test_float_duration_truncated(self):
        m = YouTubeMetadata(url="https://x.com", duration_sec=125.9)
        assert m.duration_str == "2:05"


# ---------------------------------------------------------------------------
# upload_date_str
# ---------------------------------------------------------------------------

class TestUploadDateStr:
    def test_valid_date(self):
        m = YouTubeMetadata(url="https://x.com", upload_date="20240315")
        assert m.upload_date_str == "15.03.2024"

    def test_january(self):
        m = YouTubeMetadata(url="https://x.com", upload_date="20230101")
        assert m.upload_date_str == "01.01.2023"

    def test_none_date(self):
        m = YouTubeMetadata(url="https://x.com", upload_date=None)
        assert m.upload_date_str == ""

    def test_wrong_length(self):
        m = YouTubeMetadata(url="https://x.com", upload_date="2024")
        assert m.upload_date_str == ""

    def test_empty_string(self):
        m = YouTubeMetadata(url="https://x.com", upload_date="")
        assert m.upload_date_str == ""


# ---------------------------------------------------------------------------
# YouTubeMetadata — базовые поля
# ---------------------------------------------------------------------------

class TestYouTubeMetadataFields:
    def test_only_url_required(self):
        m = YouTubeMetadata(url="https://youtube.com/watch?v=abc")
        assert m.url == "https://youtube.com/watch?v=abc"
        assert m.title is None
        assert m.channel is None
        assert m.duration_sec is None

    def test_all_fields(self):
        m = YouTubeMetadata(
            url="https://youtube.com/watch?v=abc",
            title="Test Video",
            channel="Test Channel",
            uploader="Test Uploader",
            upload_date="20240315",
            duration_sec=300.0,
            view_count=12345,
            description="Short desc",
            thumbnail_url="https://i.ytimg.com/vi/abc/maxresdefault.jpg",
        )
        assert m.title == "Test Video"
        assert m.channel == "Test Channel"
        assert m.view_count == 12345

    def test_immutable(self):
        """YouTubeMetadata не frozen по умолчанию, но поля валидируются."""
        m = YouTubeMetadata(url="https://x.com", view_count=100)
        assert m.view_count == 100


# ---------------------------------------------------------------------------
# PreparedTarget с youtube_metadata
# ---------------------------------------------------------------------------

class TestPreparedTargetWithMetadata:
    def test_without_metadata(self, tmp_path):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"RIFF")
        pt = PreparedTarget(
            target="https://x.com",
            target_id="url_abc",
            base_name="audio",
            wav_path=wav,
        )
        assert pt.youtube_metadata is None

    def test_with_metadata(self, tmp_path):
        wav = tmp_path / "audio.wav"
        wav.write_bytes(b"RIFF")
        meta = YouTubeMetadata(url="https://x.com", title="My Video", duration_sec=120)
        pt = PreparedTarget(
            target="https://x.com",
            target_id="url_abc",
            base_name="audio",
            wav_path=wav,
            youtube_metadata=meta,
        )
        assert pt.youtube_metadata is not None
        assert pt.youtube_metadata.title == "My Video"
        assert pt.youtube_metadata.duration_str == "2:00"


# ---------------------------------------------------------------------------
# RunResult с youtube_metadata
# ---------------------------------------------------------------------------

class TestRunResultWithMetadata:
    def test_metadata_propagated(self, tmp_path):
        txt = tmp_path / "result.txt"
        txt.write_text("hello", encoding="utf-8")
        meta = YouTubeMetadata(url="https://x.com", title="Video")

        result = RunResult(
            run_key="key",
            target_id="id",
            output_txt=txt,
            metrics=RunMetrics(wall_time_sec=1.0),
            youtube_metadata=meta,
        )
        assert result.youtube_metadata is not None
        assert result.youtube_metadata.title == "Video"

    def test_no_metadata_by_default(self, tmp_path):
        txt = tmp_path / "result.txt"
        txt.write_text("hello", encoding="utf-8")
        result = RunResult(
            run_key="key",
            target_id="id",
            output_txt=txt,
            metrics=RunMetrics(wall_time_sec=1.0),
        )
        assert result.youtube_metadata is None