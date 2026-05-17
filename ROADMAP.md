# PDFnik — Roadmap

Приоритеты выстроены по принципу: сначала то, что даёт наибольший leverage
при наименьших затратах и не ломает текущую работу системы.

---

## ✅ Сделано (текущая версия)

- PDF-генерация из структурированных блоков (paragraph, heading, list, price_table, image)
- Автоматическая нормализация `PdfTextBlock` → структурные блоки (классификатор + сегментер)
- Транскрибирование через faster-whisper (CPU / CUDA)
- Идемпотентный кеш транскрибирования по run_key (SQLite)
- Retry-логика: до 3 попыток с реквотированием обратно в очередь
- Per-run-key asyncio Lock против дублирующих параллельных транскрибирований
- Thread-safe WhisperEngine (threading.Lock)
- Атомарная DDL-миграция SQLite схемы
- Поддержка URL (yt-dlp) и file-path как источников аудио
- Docker Compose с healthcheck на RabbitMQ

---

## 🔴 Приоритет 1 — Надёжность (ближайшие 2–4 недели)

### 1.1 Observability: структурированные логи + метрики

Текущие логи — обычный текст. При росте нагрузки нужна возможность агрегации.

- Перейти на JSON-логи (`python-json-logger` или structlog)
- Добавить correlation_id (job_id) во все log-записи по цепочке обработки
- Экспортировать базовые метрики: количество обработанных job, ошибки, latency
  (Prometheus `/metrics` эндпоинт через `prometheus-fastapi-instrumentator`)
- Добавить health-check эндпоинт `GET /health` с проверкой подключения к RabbitMQ и Redis

### 1.2 Dead Letter Queue для неизлечимых ошибок

Сейчас после 3 попыток job теряется (публикуется `txt.done` с `status=error`
и обработка завершается). При сетевых сбоях это может терять задачи безвозвратно.

- Настроить DLQ (`txt.transcribe.dlq`) в RabbitMQ
- Логировать все попавшие в DLQ сообщения с оповещением в Telegram

### 1.3 Graceful shutdown

При `SIGTERM` (docker stop) текущий транскрибирующий поток прерывается на полуслове.

- Перехватить сигнал в `main.py`
- Дождаться завершения текущего in-flight job перед остановкой

---

## 🟡 Приоритет 2 — Качество кода (2–6 недель)

### 2.1 CI: GitHub Actions

```yaml
# .github/workflows/ci.yml
- pytest + coverage (fail под 70%)
- ruff lint
- docker build (проверка что образ собирается)
```

### 2.2 Расширить покрытие тестами

Текущее покрытие ~60% по бизнес-логике. Цель — 80%+.

- Интеграционные тесты с реальным RabbitMQ (testcontainers)
- Тест полного цикла `txt.transcribe` → `txt.done` с mock WhisperEngine
- Тест `create_pdf_from_blocks` с реальным ReportLab (на корректность файла)
- Тест `draw_images` с PIL

### 2.3 Типизация

- Включить `mypy --strict` (или `pyright`) в CI
- Аннотировать `RunRow` как `TypedDict` вместо `dict[str, Any]`

### 2.4 Рефакторинг `create_pdf.py`

Файл вырос до ~700 строк. Разбить:

```
create_pdf.py            # только orchestration (create_pdf_from_blocks)
normalizer.py            # normalize_document_blocks + вся сегментация
classifier.py            # _classify_segment + эвристики
renderers/
    paragraph.py
    heading.py
    list_block.py
    price_table.py
    image_block.py
```

---

## 🟢 Приоритет 3 — Новые возможности (1–3 месяца)

### 3.1 Structured Transcript

Сейчас транскрибирование возвращает plain text. Добавить:

- SRT / VTT экспорт (временные метки из `segments`)
- Семантическое чанкование (по паузам, по длине)
- JSON-контракт для downstream систем (RAG-ready)

Изменения:
- `TranscribeConfig` + флаг `output_format: Literal["txt", "srt", "vtt", "json"]`
- `RunResult.output_txt` → `RunResult.output_path` + метаданные
- Новая очередь `txt.done.structured`

### 3.2 Async SQLite → PostgreSQL

При горизонтальном масштабировании (несколько воркеров pdf-service) SQLite не работает как shared store.

- Порт `RunRepository` уже абстрагирует хранилище
- Добавить `PostgresRunRepository` через `asyncpg`
- Переключение через `settings.RUNS_DB_BACKEND = "sqlite" | "postgres"`

### 3.3 PDF-генерация v2: поддержка rich formatting

- **Жирный / курсивный текст** через `PdfTextEntity` (уже есть в контрактах, не рендерится)
- **Ссылки** (url из entity)
- **Многоколоночная вёрстка** для price_table
- **Кастомные шрифты** через настройку `PdfLayout`

### 3.4 Whisper Worker Pool

Сейчас `WhisperEngine` — синглтон с глобальным Lock (сериализует всё).

- Вынести Whisper в отдельный процесс (`multiprocessing.Process`)
- Или запустить несколько `pdf-service` реплик с разными CUDA device

### 3.5 files-cleaner: TTL-метки вместо mtime

Cleaner сейчас удаляет по mtime, что может затронуть файлы в процессе обработки.

- Добавить в `runs` таблицу колонку `expires_at`
- Cleaner удаляет только `expires_at < now`

---

## 📊 Технический долг (в любой момент, по возможности)

| # | Что | Где | Сложность |
|---|---|---|---|
| TD-1 | Удалить `draw_text_block.py` (мёртвый код) | `actions/text/` | Trivial |
| TD-2 | `service.py` в `domain/pdf/` — переименовать в `pdf_service.py` | `domain/pdf/` | Easy |
| TD-3 | Убрать старый `audio/target_preparer.py` после переименования | `audio/` | Easy |
| TD-4 | `_PRICE_RE` — проверить на edge cases с целыми числами | `create_pdf.py` | Medium |
| TD-5 | `_classify_segment` — добавить scoring вместо порогов | `create_pdf.py` | Medium |
| TD-6 | `WhisperEngine.model_name` — поддержка per-request модели | `whisper_engine.py` | Medium |
