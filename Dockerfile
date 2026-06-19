# ── Build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --upgrade pip --no-cache-dir

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Kayendar" \
      org.opencontainers.image.description="Lightweight CalDAV/CardDAV server with modern web client" \
      org.opencontainers.image.source="https://github.com/snchz/kayendar" \
      org.opencontainers.image.licenses="MIT"

RUN addgroup --system kayendar && adduser --system --ingroup kayendar kayendar

WORKDIR /app

COPY --from=builder /install /usr/local

COPY server/ ./server/
COPY manage.py .

RUN mkdir -p /data && chown kayendar:kayendar /data

USER kayendar

ENV KAYENDAR_DATA_DIR=/data \
    KAYENDAR_HOST=0.0.0.0 \
    KAYENDAR_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/dav/', method='OPTIONS')" || exit 1

CMD ["python", "-m", "server"]
