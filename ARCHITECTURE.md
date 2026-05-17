# PDFnik — Architecture

## Overview

PDFnik is a message-driven microservice ecosystem.
The Telegram bot is the only user-facing component.
All heavy work (PDF generation, transcription) happens in the backend service asynchronously.

```
User (Telegram)
      │
      ▼
┌─────────────────────┐
│  PDFnik-TelegramBot │  aiogram polling
│                     │
│  • session manager  │──── pdf.generate ──────────┐
│  • vtt handler      │──── txt.transcribe ─────────┼──┐
│  • pdf consumer     │◄─── pdf.send ───────────────┘  │
│  • txt consumer     │◄─── txt.done ───────────────────┘
└─────────────────────┘
           │                    │
         Redis              RabbitMQ
    (session state)       (message bus)
                               │
                    ┌──────────▼──────────┐
                    │  PDFnik-Backend     │
                    │                     │
                    │  pdf.generate ──►   │
                    │    ReportLab        │
                    │    → pdf.send       │
                    │                     │
                    │  txt.transcribe ──► │
                    │    yt-dlp + ffmpeg  │
                    │    Whisper          │
                    │    → txt.done       │
                    └─────────┬───────────┘
                              │
                      files_storage
                    (shared Docker volume)
                              │
                    ┌─────────▼───────────┐
                    │ PDFnik-files_cleaner│
                    │  TTL cleanup        │
                    └─────────────────────┘
```

---

## Docker containers

| Container | Image | Role |
|---|---|---|
| `rabbitmq` | rabbitmq:3-management | Message broker |
| `redis` | redis:7 | Session state, dedup locks |
| `pdf-service` | local build | PDF + transcription |
| `telegram-bot` | local build | Telegram frontend |
| `files-cleaner` | local build | Expired file removal |

All containers share the `files_storage` volume.

---

## Message flows

### Text/photo → PDF

```
User sends text/photo
  → TelegramBot saves to Redis session (pdf_session:{chat_id})
  → User sends /done
  → TelegramBot reads session, publishes to pdf.generate
  → Backend generates PDF, saves to files_storage, publishes to pdf.send
  → TelegramBot reads from pdf.send, sends document to user
```

### Voice/audio/video → Transcript

```
User sends voice/audio/video
  → TelegramBot downloads file, saves to files_storage
  → Publishes to txt.transcribe {target: {kind: storage_key, value: ...}}
  → Backend normalizes audio (ffmpeg), transcribes (Whisper)
  → Publishes to txt.done {txt_storage_key: ..., cached: bool}
  → TelegramBot reads transcript, sends as text or file
```

### YouTube URL → Transcript + PDF

```
User sends YouTube URL
  → TelegramBot detects URL, publishes to txt.transcribe {target: {kind: url, value: ...}}
  → Backend fetches metadata (yt-dlp --dump-json)
  → Backend downloads audio (yt-dlp), normalizes (ffmpeg), transcribes (Whisper)
  → Publishes to txt.done {txt_storage_key: ..., youtube_metadata: {...}}
  → TelegramBot delivers transcript
  → TelegramBot builds PdfOrder with title/channel/date header
  → Publishes to pdf.generate
  → Backend generates PDF, publishes to pdf.send
  → TelegramBot sends PDF to user
```

---

## Transcription pipeline

```
prepare_target()
  ├── fetch_youtube_metadata()   ← yt-dlp --dump-json (YouTube only)
  ├── download_audio_from_url()  ← yt-dlp (YouTube only)
  └── normalize_to_wav_16k_mono() ← ffmpeg

run_once()
  ├── make_run_key()   ← hash of target_id + model + device + config
  ├── cache hit?  → return RunResult(cached=True)
  └── WhisperEngine.transcribe() → RunResult(cached=False)
```

Cache key includes: `target_id | model | device | compute_type | threads | workers | beam_size | patience | vad | lang`

Same URL with same config → cache hit, no re-transcription.

---

## PDF block types

Text input from the bot is normalized through a classifier before rendering:

```
PdfTextBlock (raw text)
  │
  ▼ pdf_normalizer.normalize_document_blocks()
  │
  ├── _segment_by_blank_lines()   split on 2+ blank lines
  └── _classify_segment()
        ├── heading      ← short, uppercase or ends with ":"
        ├── price_table  ← lines with "Name — 9.90 €" pattern
        ├── list         ← bullet/numbered lines
        └── paragraph    ← everything else

PdfImageBlock → draw_images() (ReportLab)
PdfHeadingBlock → render_heading()
PdfParagraphBlock → render_paragraph()
PdfListBlock → render_list()
PdfPriceTableBlock → render_price_table()
```

---

## Shared contracts

All inter-service data models live in [PDFnik-Schemes](https://github.com/Evil2997/PDFnik-Schemes):

- `PdfOrder` — input to pdf.generate
- `BotDocument` — output from pdf.send
- `PdfBlock` subtypes — content blocks

Both services install schemes as a git dependency:
```
pdfnik-schemes @ git+https://github.com/Evil2997/PDFnik-Schemes@v1.2.1
```

---

## Font handling

DejaVuSans is installed from the `fonts-dejavu-core` system package during the Docker image build.
No font files are stored in the repository.

```dockerfile
RUN apt-get install -y fonts-dejavu-core \
 && mkdir -p /app/fonts \
 && cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/fonts/
```
