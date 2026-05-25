# PDFnik — Roadmap

## Current state (v0.3)

### Working
- Text → PDF (paragraphs, headings, lists, price tables)
- Photos → PDF (one per page, fills available area)
- Voice / audio / video → transcript (Whisper)
- YouTube URL → transcript + PDF with title, channel, date, source link
- /done, /cancel, /start, /help commands
- Session pause timer with reminder
- Deduplication of concurrent identical requests
- Transcription cache (SQLite, keyed by content hash + model config)
- Retry logic (up to 3 attempts per job)
- Dead Letter Queue — failed jobs land in txt.dead / pdf.dead, logged for review
- Health check endpoint — GET /health checks RabbitMQ, files_storage, runs DB
- Whisper model configurable via TRANSCRIBE_MODEL env var (base → large-v3)
- CI (GitHub Actions): lint → test → docker build
- pre-commit: ruff, detect-secrets
- Coverage: Backend ≥70%, TelegramBot ≥65%

### Known limitations
- DLQ is log-only (no alerting, no Telegram notification)

---

## P1 — Stability ✅ Done

- [x] Dead Letter Queue for transcription and PDF failures
- [x] Health check endpoint (GET /health)
- [x] Whisper model configurable via env (TRANSCRIBE_MODEL=large-v3)
- [x] YouTube → PDF for long transcripts — both short and document delivery paths now generate PDF
- [x] /cancel confirmation guard

---

## P2 — Features (next)

- [x] Multi-image layout — fit 2 landscape images per page
- [ ] Batch YouTube — multiple URLs → one combined PDF
- [ ] LLM summary — short summary block at top of YouTube PDF
- [ ] OCR — extract text from images, include in PDF

---

## P3 — Platform

### Internal dashboard (FastAPI)
Browser-based control panel for self-use (and eventually for the wife):
- Queue depth and message rates (RabbitMQ management API)
- Transcription job history and cache hit rate
- Storage usage graph
- Whisper model selector without restarting the service
- Manual retry for DLQ messages

### VTT (separate repo)
Independent project growing out of PDFnik's transcription layer:
- SaaS transcription API with usage tracking
- Voice assistant — speech recognition + action execution + voice response
- Multi-model routing (Whisper, cloud STT fallback)

### PDFnik API
- REST endpoints for PDF generation without Telegram
- Subscription model and usage tracking
- GitHub/GitLab integration (commit summaries → PDF)
- S3 storage backend (replace local Docker volume)
