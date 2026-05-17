# PDFnik — Roadmap

## Current state (v0.2)

### Working
- Text → PDF (paragraphs, headings, lists, price tables)
- Photos → PDF (one per page, fills available area)
- Voice / audio / video → transcript (Whisper, CPU)
- YouTube URL → transcript + PDF with title, channel, date, source link
- /done, /cancel, /start, /help commands
- Session pause timer with reminder
- Deduplication of concurrent identical requests
- Transcription cache (SQLite, keyed by content hash + model config)
- Retry logic (up to 3 attempts per job)
- CI (GitHub Actions): lint → test → docker build
- pre-commit: ruff, detect-secrets
- Coverage: Backend ≥70%, TelegramBot ≥65%

### Known limitations
- Photos: one per page (no multi-image layout)
- Transcription model: `base` by default (fast, ~80% accuracy on Russian)
- No Dead Letter Queue for permanently failed jobs
- YouTube PDF generated only when transcript fits in one short message path

---

## P1 — Stability (next)

- [ ] Dead Letter Queue for transcription failures
- [ ] YouTube → PDF for long transcripts (currently only short path)
- [ ] /cancel guard: confirm if session has content
- [ ] Health check endpoint for Docker

---

## P2 — Features

- [ ] Multi-image layout — fit 2 images per page when both are landscape
- [ ] Batch YouTube — multiple URLs → one combined PDF
- [ ] LLM summary — short summary block at the top of YouTube PDF
- [ ] OCR — extract text from images, include in PDF
- [ ] Large Whisper model option — `large-v3` for higher accuracy
- [ ] CUDA support — automatic device detection in Docker

---

## P3 — Platform (AFO / VTT direction)

VTT is an independent project growing out of PDFnik's transcription layer:
- SaaS transcription API
- Voice assistant with response and action capabilities
- Multi-model routing (Whisper, cloud STT)

PDFnik-Backend evolves toward:
- REST API for external PDF generation clients
- Subscription model and usage tracking
- GitHub/GitLab integration (commit summaries → PDF)
- S3 storage backend (replace local volume)
