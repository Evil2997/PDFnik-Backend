"""
Тесты для run_logic.py.

Покрываем:
- make_run_key / txt_name_for_run — детерминизм и стабильность
- run_once — cache hit (ok), cache miss (failed), полный запуск, ошибка транскрибации
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from main_app.domain.work_with_pdf.actions.files.models import (
    PreparedTarget,
    TranscribeConfig,
)
from main_app.domain.work_with_pdf.actions.files.run_logic import (
    make_run_key,
    resolve_compute_type,
    run_once,
    txt_name_for_run,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(**kwargs) -> TranscribeConfig:
    defaults = dict(
        model="base",
        device="cpu",
        compute_type=None,
        threads=4,
        workers=1,
        beam_size=5,
        patience=1.0,
        vad=False,
        lang="auto",
    )
    defaults.update(kwargs)
    return TranscribeConfig(**defaults)


def _prepared(tmp_path: Path, name: str = "audio") -> PreparedTarget:
    wav = tmp_path / f"{name}.wav"
    wav.write_bytes(b"RIFF")
    return PreparedTarget(
        target=str(wav),
        target_id=f"file_abc123",
        base_name=name,
        wav_path=wav,
        audio_duration_sec=10.0,
    )


def _mock_repo(status: str | None = None, output_txt: str | None = None) -> MagicMock:
    repo = MagicMock()
    if status is not None:
        repo.get.return_value = {"run_key": "k", "status": status, "output_txt": output_txt or ""}
    else:
        repo.get.return_value = None
    return repo


def _mock_engine(text: str = "hello world", lang: str = "de") -> MagicMock:
    engine = MagicMock()
    engine.transcribe.return_value = (text, lang)
    return engine


# ---------------------------------------------------------------------------
# make_run_key & resolve_compute_type
# ---------------------------------------------------------------------------

class TestMakeRunKey:
    def test_deterministic(self):
        cfg = _cfg()
        k1 = make_run_key("id1", cfg, "int8")
        k2 = make_run_key("id1", cfg, "int8")
        assert k1 == k2

    def test_different_targets(self):
        cfg = _cfg()
        assert make_run_key("id1", cfg, "int8") != make_run_key("id2", cfg, "int8")

    def test_different_models(self):
        assert make_run_key("id", _cfg(model="base"), "int8") != make_run_key("id", _cfg(model="large"), "int8")

    def test_different_beam(self):
        assert make_run_key("id", _cfg(beam_size=5), "int8") != make_run_key("id", _cfg(beam_size=1), "int8")

    def test_contains_all_parts(self):
        cfg = _cfg(model="base", device="cpu", threads=4, workers=1, beam_size=5)
        key = make_run_key("myid", cfg, "int8")
        assert "myid" in key
        assert "base" in key
        assert "cpu" in key
        assert "int8" in key
        assert "thr=4" in key
        assert "beam=5" in key


class TestResolveComputeType:
    def test_explicit_wins(self):
        cfg = _cfg(compute_type="float32")
        assert resolve_compute_type(cfg) == "float32"

    def test_cuda_default(self):
        cfg = _cfg(device="cuda", compute_type=None)
        assert resolve_compute_type(cfg) == "float16"

    def test_cpu_default(self):
        cfg = _cfg(device="cpu", compute_type=None)
        assert resolve_compute_type(cfg) == "int8"


class TestTxtNameForRun:
    def test_contains_base_name(self):
        name = txt_name_for_run("my_audio", "some_run_key")
        assert name.startswith("my_audio__")
        assert name.endswith(".txt")

    def test_stable(self):
        assert txt_name_for_run("x", "key") == txt_name_for_run("x", "key")

    def test_different_keys_different_names(self):
        assert txt_name_for_run("x", "key1") != txt_name_for_run("x", "key2")


# ---------------------------------------------------------------------------
# run_once
# ---------------------------------------------------------------------------

class TestRunOnceCacheHit:
    def test_cache_hit_ok_returns_cached(self, tmp_dir):
        """Если файл существует и статус ok — возвращаем кеш, не вызываем движок."""
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = _mock_engine()

        # Создаём файл результата заранее
        from main_app.domain.work_with_pdf.actions.files.run_logic import txt_name_for_run, make_run_key, resolve_compute_type
        compute = resolve_compute_type(cfg)
        run_key = make_run_key(prepared.target_id, cfg, compute)
        out_txt = tmp_dir / txt_name_for_run(prepared.base_name, run_key)
        out_txt.write_text("cached text", encoding="utf-8")

        repo = _mock_repo(status="ok", output_txt=str(out_txt))

        result = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )

        assert result.cached is True
        assert result.status == "ok"
        engine.transcribe.assert_not_called()

    def test_cache_hit_failed_reruns(self, tmp_dir):
        """
        КРИТИЧЕСКИЙ БАГ: если предыдущий запуск завершился с failed —
        файл может существовать, но кешировать его нельзя.
        Движок должен быть вызван заново.
        """
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = _mock_engine()

        from main_app.domain.work_with_pdf.actions.files.run_logic import txt_name_for_run, make_run_key, resolve_compute_type
        compute = resolve_compute_type(cfg)
        run_key = make_run_key(prepared.target_id, cfg, compute)
        out_txt = tmp_dir / txt_name_for_run(prepared.base_name, run_key)
        out_txt.write_text("partial broken output", encoding="utf-8")

        # Репо говорит: статус failed
        repo = _mock_repo(status="failed", output_txt=str(out_txt))

        result = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )

        # Должен был запустить транскрибацию заново
        engine.transcribe.assert_called_once()
        assert result.cached is False

    def test_cache_miss_no_file(self, tmp_dir):
        """Файла нет — всегда запускаем движок."""
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = _mock_engine()
        repo = _mock_repo(status="ok")

        result = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )

        engine.transcribe.assert_called_once()
        assert result.cached is False

    def test_allow_skip_false_ignores_cache(self, tmp_dir):
        """allow_skip=False — игнорируем кеш даже при статусе ok."""
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = _mock_engine()

        from main_app.domain.work_with_pdf.actions.files.run_logic import txt_name_for_run, make_run_key, resolve_compute_type
        compute = resolve_compute_type(cfg)
        run_key = make_run_key(prepared.target_id, cfg, compute)
        out_txt = tmp_dir / txt_name_for_run(prepared.base_name, run_key)
        out_txt.write_text("old text", encoding="utf-8")
        repo = _mock_repo(status="ok", output_txt=str(out_txt))

        run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=False,
        )

        engine.transcribe.assert_called_once()


class TestRunOnceSuccess:
    def test_writes_txt_and_upserts_ok(self, tmp_dir):
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = _mock_engine(text="Hallo Welt", lang="de")
        repo = MagicMock()
        repo.get.return_value = None

        result = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )

        assert result.status == "ok"
        assert result.output_txt.exists()
        assert result.output_txt.read_text(encoding="utf-8") == "Hallo Welt"
        assert result.detected_language == "de"
        assert result.cached is False

        repo.upsert.assert_called_once()
        upserted = repo.upsert.call_args[0][0]
        assert upserted["status"] == "ok"
        assert upserted["run_key"] == result.run_key

    def test_rtf_computed_when_duration_known(self, tmp_dir):
        prepared = _prepared(tmp_dir)  # audio_duration_sec=10.0
        cfg = _cfg()
        engine = _mock_engine()
        repo = MagicMock()
        repo.get.return_value = None

        result = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )

        assert result.metrics.rtf is not None
        assert result.metrics.rtf >= 0


class TestRunOnceFailure:
    def test_engine_error_returns_failed_result(self, tmp_dir):
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = MagicMock()
        engine.transcribe.side_effect = RuntimeError("GPU OOM")
        repo = MagicMock()
        repo.get.return_value = None

        result = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )

        assert result.status == "failed"
        assert "GPU OOM" in (result.error or "")

        repo.upsert.assert_called_once()
        assert repo.upsert.call_args[0][0]["status"] == "failed"

    def test_failed_result_not_cached_on_rerun(self, tmp_dir):
        """После failed upsert следующий вызов не должен брать из кеша."""
        prepared = _prepared(tmp_dir)
        cfg = _cfg()
        engine = MagicMock()
        engine.transcribe.side_effect = [RuntimeError("first fail"), ("ok text", "en")]
        repo = MagicMock()
        repo.get.return_value = None

        # Первый запуск — упал
        r1 = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )
        assert r1.status == "failed"

        # Репо теперь возвращает failed
        repo.get.return_value = {"run_key": r1.run_key, "status": "failed", "output_txt": str(r1.output_txt)}

        # Второй запуск — должен повторить, не читать кеш
        r2 = run_once(
            prepared=prepared, cfg=cfg, out_dir=tmp_dir,
            repo=repo, engine=engine, allow_skip=True,
        )
        assert r2.status == "ok"
        assert r2.cached is False
        assert engine.transcribe.call_count == 2