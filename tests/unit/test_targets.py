"""
Тесты для targets.py (AudioTargetPreparer логика).

ffmpeg и yt-dlp мокируются через patch, чтобы тесты работали
без внешних зависимостей.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import subprocess

import pytest

from main_app.domain.work_with_pdf.actions.files.audio.targets import (
    is_url,
    prepare_target,
    _hash,
    normalize_to_wav_16k_mono,
    download_audio_from_url,
)
from main_app.domain.work_with_pdf.actions.files.exceptions import TargetPrepareError


# ---------------------------------------------------------------------------
# is_url
# ---------------------------------------------------------------------------

class TestIsUrl:
    def test_http(self):
        assert is_url("http://example.com/audio.mp3") is True

    def test_https(self):
        assert is_url("https://youtube.com/watch?v=abc") is True

    def test_file_path(self):
        assert is_url("/home/user/audio.wav") is False

    def test_relative_path(self):
        assert is_url("audio.wav") is False

    def test_ftp_not_url(self):
        # только http/https
        assert is_url("ftp://example.com/audio.mp3") is False


# ---------------------------------------------------------------------------
# _hash
# ---------------------------------------------------------------------------

class TestHash:
    def test_deterministic(self):
        assert _hash("hello") == _hash("hello")

    def test_different_inputs(self):
        assert _hash("a") != _hash("b")

    def test_length(self):
        assert len(_hash("anything")) == 12


# ---------------------------------------------------------------------------
# normalize_to_wav_16k_mono
# ---------------------------------------------------------------------------

class TestNormalizeToWav:
    def test_calls_ffmpeg_with_correct_args(self, tmp_dir: Path):
        src = tmp_dir / "input.mp3"
        src.write_bytes(b"fake mp3")
        dst = tmp_dir / "output.wav"

        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd"
        ) as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="")
            normalize_to_wav_16k_mono(src, dst)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        assert "ffmpeg" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert str(src) in cmd
        assert str(dst) in cmd


# ---------------------------------------------------------------------------
# download_audio_from_url
# ---------------------------------------------------------------------------

class TestDownloadAudioFromUrl:
    def test_calls_yt_dlp(self, tmp_dir: Path):
        fake_file = tmp_dir / "src_abc123.mp4"
        fake_file.write_bytes(b"fake video")

        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd"
        ) as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="")
            result = download_audio_from_url("https://example.com/video", tmp_dir)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "yt-dlp" in cmd
        assert "https://example.com/video" in cmd
        assert "--no-playlist" in cmd

    def test_raises_if_no_file(self, tmp_dir: Path):
        """Если yt-dlp не создал файл — TargetPrepareError."""
        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.run_cmd"
        ) as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="")
            with pytest.raises(TargetPrepareError, match="no file was saved"):
                download_audio_from_url("https://example.com/video", tmp_dir)


# ---------------------------------------------------------------------------
# prepare_target — file path
# ---------------------------------------------------------------------------

class TestPrepareTargetFile:
    def test_file_not_found_raises(self, tmp_dir: Path):
        with pytest.raises(TargetPrepareError, match="File not found"):
            prepare_target("/nonexistent/audio.wav", work_dir=tmp_dir)

    def test_normalizes_existing_file(self, tmp_dir: Path):
        src = tmp_dir / "audio.mp3"
        src.write_bytes(b"fake audio")

        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.normalize_to_wav_16k_mono"
        ) as mock_norm, patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.get_audio_duration_sec",
            return_value=42.0,
        ):
            mock_norm.side_effect = lambda src, dst: dst.parent.mkdir(parents=True, exist_ok=True) or dst.write_bytes(b"RIFF")
            result = prepare_target(str(src), work_dir=tmp_dir)

        assert result.target == str(src)
        assert result.target_id.startswith("file_")
        assert result.base_name == "audio"
        assert result.wav_path.suffix == ".wav"
        assert result.audio_duration_sec == 42.0

    def test_wav_cache_skips_normalize(self, tmp_dir: Path):
        """Если WAV уже существует — normalize не вызывается повторно."""
        src = tmp_dir / "audio.mp3"
        src.write_bytes(b"fake audio")

        target_id = f"file_{_hash(str(src.resolve()))}"
        wav_path = tmp_dir / "prepared" / f"audio__{target_id}.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        wav_path.write_bytes(b"RIFF cached")

        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.normalize_to_wav_16k_mono"
        ) as mock_norm, patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.get_audio_duration_sec",
            return_value=10.0,
        ):
            result = prepare_target(str(src), work_dir=tmp_dir)

        mock_norm.assert_not_called()
        assert result.wav_path == wav_path


# ---------------------------------------------------------------------------
# prepare_target — URL
# ---------------------------------------------------------------------------

class TestPrepareTargetUrl:
    def test_url_triggers_download(self, tmp_dir: Path):
        url = "https://youtube.com/watch?v=test"
        fake_downloaded = tmp_dir / "downloads" / "src_test.mp4"

        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.download_audio_from_url",
            return_value=fake_downloaded,
        ) as mock_dl, patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.normalize_to_wav_16k_mono"
        ) as mock_norm, patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.get_audio_duration_sec",
            return_value=60.0,
        ):
            fake_downloaded.parent.mkdir(parents=True, exist_ok=True)
            fake_downloaded.write_bytes(b"fake")

            def _make_wav(src, dst):
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(b"RIFF")

            mock_norm.side_effect = _make_wav

            result = prepare_target(url, work_dir=tmp_dir)

        mock_dl.assert_called_once_with(url, tmp_dir / "downloads")
        assert result.target_id.startswith("url_")
        assert result.audio_duration_sec == 60.0

    def test_duration_none_on_ffprobe_error(self, tmp_dir: Path):
        """Если ffprobe падает — duration=None, но подготовка продолжается."""
        src = tmp_dir / "audio.mp3"
        src.write_bytes(b"fake")

        with patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.normalize_to_wav_16k_mono"
        ) as mock_norm, patch(
            "main_app.domain.work_with_pdf.actions.files.audio.targets.get_audio_duration_sec",
            side_effect=RuntimeError("ffprobe failed"),
        ):
            mock_norm.side_effect = lambda s, d: (d.parent.mkdir(parents=True, exist_ok=True), d.write_bytes(b"RIFF"))
            result = prepare_target(str(src), work_dir=tmp_dir)

        assert result.audio_duration_sec is None