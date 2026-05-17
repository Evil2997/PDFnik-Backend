"""
Tests for Pydantic models in txt_orders.py.

Coverage includes:
- normalize_legacy_payload: old field format → new format
- TxtTranscribeJob: validation of the new format
- TxtDoneResult
- Edge cases: missing fields, None values
"""

import pytest

from main_app.rabbitmq.txt_orders import (
    TxtCfgOverrides,
    TxtDoneResult,
    TxtReply,
    TxtTarget,
    TxtTranscribeJob,
)

# ---------------------------------------------------------------------------
# TxtTarget
# ---------------------------------------------------------------------------


class TestTxtTarget:
    def test_storage_key(self):
        t = TxtTarget(kind="storage_key", value="uploads/audio.wav")
        assert t.kind == "storage_key"
        assert t.value == "uploads/audio.wav"

    def test_url(self):
        t = TxtTarget(kind="url", value="https://example.com/audio.mp4")
        assert t.kind == "url"

    def test_frozen(self):
        from pydantic import ValidationError

        t = TxtTarget(kind="url", value="https://x.com")
        with pytest.raises((ValidationError, TypeError)):
            t.value = "other"


# ---------------------------------------------------------------------------
# TxtReply
# ---------------------------------------------------------------------------


class TestTxtReply:
    def test_basic(self):
        r = TxtReply(chat_id=123456)
        assert r.chat_id == 123456
        assert r.reply_to_message_id is None

    def test_with_reply_to(self):
        r = TxtReply(chat_id=111, reply_to_message_id=999)
        assert r.reply_to_message_id == 999


# ---------------------------------------------------------------------------
# Legacy payload normalization
# ---------------------------------------------------------------------------


class TestNormalizeLegacyPayload:
    """
    normalize_legacy_payload should accept the old message format
    (flat fields: chat_id, storage_key, input_url) and transform it
    into the new nested format (target, reply, delivery).
    """

    def _make_job(self, data: dict) -> TxtTranscribeJob:
        return TxtTranscribeJob.model_validate(data)

    def test_legacy_storage_key(self):
        job = self._make_job(
            {
                "job_id": "j1",
                "storage_key": "uploads/file.wav",
                "chat_id": 100,
            }
        )
        assert job.target.kind == "storage_key"
        assert job.target.value == "uploads/file.wav"
        assert job.reply is not None
        assert job.reply.chat_id == 100

    def test_legacy_input_url(self):
        job = self._make_job(
            {
                "job_id": "j2",
                "input_url": "https://youtube.com/watch?v=abc",
                "chat_id": 200,
            }
        )
        assert job.target.kind == "url"
        assert job.target.value == "https://youtube.com/watch?v=abc"

    def test_legacy_with_reply_to(self):
        job = self._make_job(
            {
                "job_id": "j3",
                "storage_key": "x.wav",
                "chat_id": 300,
                "reply_to_message_id": 42,
            }
        )
        assert job.reply.reply_to_message_id == 42

    def test_legacy_with_source_type_and_mode(self):
        job = self._make_job(
            {
                "job_id": "j4",
                "storage_key": "x.wav",
                "chat_id": 400,
                "source_type": "video",
                "mode": "fast",
            }
        )
        assert job.delivery is not None
        assert job.delivery.source_type == "video"
        assert job.delivery.mode == "fast"

    def test_new_format_passes_through(self):
        job = self._make_job(
            {
                "job_id": "j5",
                "target": {"kind": "url", "value": "https://x.com"},
                "reply": {"chat_id": 500},
            }
        )
        assert job.target.kind == "url"
        assert job.reply.chat_id == 500

    def test_no_chat_id_reply_is_none(self):
        job = self._make_job(
            {
                "job_id": "j6",
                "storage_key": "x.wav",
            }
        )
        assert job.reply is None

    def test_defaults(self):
        job = self._make_job(
            {
                "job_id": "j7",
                "target": {"kind": "storage_key", "value": "x.wav"},
            }
        )
        assert job.attempt == 1
        assert job.max_attempts == 3


# ---------------------------------------------------------------------------
# TxtCfgOverrides
# ---------------------------------------------------------------------------


class TestTxtCfgOverrides:
    def test_all_none_by_default(self):
        cfg = TxtCfgOverrides()
        assert cfg.model is None
        assert cfg.device is None
        assert cfg.threads is None

    def test_threads_ge1(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TxtCfgOverrides(threads=0)

    def test_valid_overrides(self):
        cfg = TxtCfgOverrides(model="large-v3", threads=8, beam_size=5)
        assert cfg.model == "large-v3"
        assert cfg.threads == 8


# ---------------------------------------------------------------------------
# TxtDoneResult
# ---------------------------------------------------------------------------


class TestTxtDoneResult:
    def test_ok_result(self):
        r = TxtDoneResult(
            job_id="j1",
            status="ok",
            txt_storage_key="outputs/j1.txt",
            reply=TxtReply(chat_id=123),
        )
        assert r.status == "ok"
        assert r.error is None

    def test_error_result(self):
        r = TxtDoneResult(
            job_id="j2",
            status="error",
            error="GPU OOM",
        )
        assert r.status == "error"
        assert r.error == "GPU OOM"
        assert r.txt_storage_key is None

    def test_model_dump_excludes_none(self):
        r = TxtDoneResult(job_id="j3", status="ok")
        dumped = r.model_dump(exclude_none=True)
        assert "error" not in dumped
        assert "txt_storage_key" not in dumped
