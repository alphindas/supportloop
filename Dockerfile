# CPU-only image of the API. Search models are downloaded on first start into /models
# (a volume), so they are not baked into the image.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY scripts/install_cpu.sh scripts/
RUN uv venv /opt/venv && scripts/install_cpu.sh /opt/venv/bin/python && rm -rf /root/.cache

COPY app ./app
COPY ab ./ab
COPY evals ./evals
COPY scripts ./scripts
COPY config ./config
COPY experiments ./experiments
COPY data/kb ./data/kb

RUN useradd --create-home appuser && mkdir -p /models data/index data/runtime logs \
    && chown -R appuser /models data logs
USER appuser

ENV PATH=/opt/venv/bin:$PATH \
    HF_HOME=/models \
    SUPPORTLOOP_RETRIEVAL_DEVICE=cpu \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# The first start downloads the models, so allow a long start period.
HEALTHCHECK --interval=30s --timeout=5s --start-period=900s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["sh", "-c", "python -m scripts.ingest && exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000"]
