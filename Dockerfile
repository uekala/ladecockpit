FROM python:3.14-slim-trixie@sha256:f57c4c23b985d95deea5bc5249e2f9c8a512b4cc9d5d3fd31900cbd2f5f0a604

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    TZ=Europe/Berlin

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Läuft absichtlich als root: Als Home-Assistant-App gehört der Ordner /data root.
RUN mkdir -p /data
VOLUME /data
EXPOSE 8077

HEALTHCHECK --interval=60s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8077/healthz', timeout=3)" || exit 1

CMD ["python", "-m", "app"]
