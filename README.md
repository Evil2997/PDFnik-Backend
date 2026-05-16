# PDFnik — PDF Service

Микросервис в составе экосистемы **PDFnik**:
принимает заказы на генерацию PDF и транскрибирование аудио через RabbitMQ,
возвращает результаты в ответные очереди.

---

## Архитектура

```
                         ┌──────────────────────────────────────┐
Telegram Bot ──► pdf.generate ──► pdf-service ──► pdf.send ──► Telegram Bot
             ──► txt.transcribe ──►           ──► txt.done  ──►
                         └──────────────────────────────────────┘
                                    │            │
                                 RabbitMQ      Redis
                                              (кеш runs)
```

Пять контейнеров:

| Контейнер | Роль |
|---|---|
| `rabbitmq` | Брокер сообщений (AMQP + Management UI) |
| `redis` | Хранилище Redis (зарезервировано для будущего rate-limiting и версионирования) |
| `pdf-service` | **Этот сервис** — FastAPI + FastStream |
| `telegram-bot` | Бот-фронтенд (отдельный репозиторий) |
| `files-cleaner` | Периодическая очистка файлов (отдельный репозиторий) |

Общий Docker volume `files_storage` используется как шина файлов между контейнерами.

---

## Структура кода

```
main_app/
├── api/routes/
│   └── orders.py                    # HTTP-эндпоинт /order (тестовый)
├── core/
│   ├── constants.py                 # Пути, URL, имена очередей
│   ├── logger.py
│   └── settings.py                  # Pydantic-settings из .env
├── infrastructure/
│   └── rabbit_connector.py          # FastStream broker + router
└── domain/work_with_pdf/
    ├── create_pdf.py                # Основной PDF-рендерер (ReportLab)
    ├── models/
    │   ├── pdf_layout.py            # Типографика и отступы
    │   └── image_render_options.py  # Настройки рендера изображений
    └── actions/
        ├── generate_pdf_path.py
        ├── images/draw_images.py    # Рендер изображений в PDF
        ├── text/wrap_by_width.py    # Перенос текста по ширине
        └── files/                   # Транскрибирование аудио
            ├── models.py            # PreparedTarget, TranscribeConfig, RunResult
            ├── run_logic.py         # Логика кеша + запуск движка
            ├── prod_service.py      # Точка входа для транскрибирования
            ├── whisper_engine.py    # Thread-safe обёртка над faster-whisper
            ├── audio/
            │   ├── audio_target_preparer.py  # AudioTargetPreparer (реализация)
            │   ├── targets.py       # yt-dlp + ffmpeg: скачать и нормализовать
            │   ├── media.py         # ffprobe: длительность аудио
            │   └── process.py       # run_cmd() — обёртка subprocess
            ├── ports/               # Протоколы (интерфейсы)
            │   ├── run_repository.py
            │   ├── target_preparer.py
            │   └── transcribe_engine.py
            └── sqlite/
                ├── schema.py        # DDL + атомарная миграция
                └── sqlite_repo.py   # SqliteRunRepository
```

**Очереди RabbitMQ:**

| Очередь | Направление | Описание |
|---|---|---|
| `pdf.generate` | → сервис | Запрос на генерацию PDF |
| `pdf.send` | ← сервис | Готовый PDF (storage_key) |
| `txt.transcribe` | → сервис | Запрос на транскрибирование |
| `txt.done` | ← сервис | Результат транскрибирования |

---

## Быстрый старт

### Требования

- [uv](https://docs.astral.sh/uv/) ≥ 0.4
- Docker + Docker Compose
- Python 3.13+

### Установка зависимостей

```bash
uv sync
uv sync --extra dev   # включая инструменты разработки
```

### Настройка окружения

Скопируй `.env.example` → `.env` и заполни значения:

```bash
cp .env.example .env
```

Обязательные переменные:

```env
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
REDIS_URL=redis://redis:6379/0

# Пути к файловому хранилищу (внутри контейнера)
FILES_ROOT=/data_files_storage
PDF_OUTPUT_DIR=/data_files_storage/pdfs
TXT_OUTPUT_DIR=/data_files_storage/txts
RUNS_DB_PATH=/data_files_storage/runs.db

# Шрифт для ReportLab (должен быть в образе)
FONT_PATH=/app/fonts/DejaVuSans.ttf
FONT_TYPE=DejaVuSans

# Настройки Whisper
TRANSCRIBE_MODEL=base
TRANSCRIBE_DEVICE=cpu
TRANSCRIBE_THREADS=4
TRANSCRIBE_WORKERS=1
TRANSCRIBE_BEAM_SIZE=5
TRANSCRIBE_PATIENCE=1.0
TRANSCRIBE_VAD=false
TRANSCRIBE_LANG=auto
```

Если сервисы не в монорепо, укажи пути:

```env
PDF_SERVICE_PATH=/absolute/path/to/pdf-service
TELEGRAM_BOT_PATH=/absolute/path/to/telegram-bot
FILES_CLEANER_PATH=/absolute/path/to/files-cleaner
```

### Запуск

```bash
# Запустить всю экосистему
docker compose up --build

# Только RabbitMQ + Redis (для локальной разработки сервиса)
docker compose up rabbitmq redis

# Запустить сервис локально
uv run python main.py
```

RabbitMQ Management UI: http://localhost:15672 (guest / guest)

---

## Тесты

```bash
# Все тесты
uv run pytest tests/ -v

# С отчётом о покрытии
uv run pytest tests/ --cov=main_app --cov-report=term-missing

# Только один модуль
uv run pytest tests/unit/test_run_logic.py -v
```

**Покрытые модули:**

| Файл | Что тестируем |
|---|---|
| `test_run_logic.py` | Кеш run_once, детерминизм ключей, обработка ошибок |
| `test_classify_segment.py` | Классификатор блоков PDF: heading/list/price_table/paragraph |
| `test_sqlite_repo.py` | upsert/get/миграция схемы БД |
| `test_txt_orders_model.py` | Legacy payload normalization, валидация Pydantic-моделей |
| `test_targets.py` | prepare_target с mock-ами ffmpeg и yt-dlp |

---

## Известные ограничения

- `WhisperEngine` — синглтон, транскрибирование полностью сериализовано через `threading.Lock`.
  При необходимости параллельного транскрибирования нужен pool воркеров с отдельным экземпляром модели.
- SQLite `runs.db` — подходит для одного воркера. При горизонтальном масштабировании
  нужно перейти на PostgreSQL.
- `files_storage` volume — разделяется между сервисами без блокировок.
  `files-cleaner` может удалить файл, который ещё читается другим сервисом.
  Рекомендуется добавить soft-delete или TTL-метки.

---

## Зависимости

| Пакет | Версия | Назначение |
|---|---|---|
| fastapi | 0.127.1 | HTTP-сервер |
| faststream[rabbit] | 0.6.3 | RabbitMQ consumer/publisher |
| pydantic | 2.11.10 | Валидация данных |
| reportlab | 4.4.7 | Генерация PDF |
| pillow | 12.1.1 | Обработка изображений |
| faster-whisper | 1.2.1 | Транскрибирование аудио |
| yt-dlp | 2026.3.3 | Скачивание аудио по URL |
| pdfnik-schemes | v1.2.1 | Общие контракты экосистемы PDFnik |