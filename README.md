# PDFnik — Backend

PDF generation and audio transcription microservice.

Part of the PDFnik ecosystem:
- **PDFnik-Backend** (this repo) — PDF generation, audio transcription via Whisper
- [PDFnik-TelegramBot](https://github.com/Evil2997/PDFnik-TelegramBot) — Telegram frontend
- [PDFnik-Schemes](https://github.com/Evil2997/PDFnik-Schemes) — shared Pydantic contracts
- [PDFnik-files_cleaner](https://github.com/Evil2997/PDFnik-files_cleaner) — TTL file cleanup

---

## Stack

- Python 3.13, FastAPI, FastStream
- RabbitMQ — message queues
- Redis — session state, deduplication
- faster-whisper — audio transcription (CPU/CUDA)
- yt-dlp + ffmpeg — YouTube audio download and normalization
- ReportLab — PDF generation
- SQLite — transcription run cache
- Docker, uv

---

## Queues

| Queue | Direction | Description |
|---|---|---|
| `pdf.generate` | → Backend | Generate PDF from blocks |
| `pdf.send` | Backend → | Send PDF to Telegram user |
| `txt.transcribe` | → Backend | Transcribe audio/YouTube |
| `txt.done` | Backend → | Deliver transcript + metadata |

---

## Running

```bash
cp .env.example .env
# fill in BOT_TOKEN, RABBITMQ_URL, REDIS_URL

./run_PDFnik.sh
```

Stops all services:
```bash
./down_PDFnik.sh
```

---

## Development

```bash
uv sync
uv run pytest
uv run pre-commit install
uv run pre-commit run --all-files
```

---

## Project structure

```
main_app/
├── api/routes/          # FastAPI HTTP routes
├── core/                # constants, settings, logger
├── infrastructure/      # RabbitMQ connector
├── rabbitmq/
│   ├── pdf_orders.py    # consumer: pdf.generate
│   └── txt_orders.py    # consumer: txt.transcribe
└── domain/work_with_pdf/
    ├── create_pdf.py        # orchestration
    ├── pdf_normalizer.py    # text block classifier
    ├── pdf_renderers.py     # block renderers
    ├── pdf_service.py       # entry point
    ├── models/
    └── actions/files/       # transcription pipeline
        ├── models.py
        ├── run_logic.py     # cache + transcription
        ├── whisper_engine.py
        └── audio/
            ├── targets.py   # yt-dlp, ffmpeg, metadata
            └── audio_target_preparer.py
```
