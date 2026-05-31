FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    git \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY requirements.txt ./
RUN uv venv && uv pip install --no-cache -r requirements.txt
COPY . .


FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    ffmpeg \
    libgomp1 \
    fonts-dejavu-core \
 && mkdir -p /app/fonts \
 && cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/fonts/ \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py"]
