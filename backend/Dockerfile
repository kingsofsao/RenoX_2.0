# ResearchMind API. Runs as an unprivileged user, a single process (investigations and their live
# progress are held in memory), behind the frontend's reverse proxy.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production \
    RESEARCHMIND_DATA_DIR=/data \
    HF_HOME=/models

RUN useradd --create-home --uid 10001 app && mkdir -p /data /models && chown app:app /data /models
WORKDIR /app

# EMBEDDINGS=light leaves out SentenceTransformers (PyTorch, several GB) for small instances such as
# Render's free plan (512 MB); run it with EMBEDDING_BACKEND=hashing (the built-in offline embedder).
ARG EMBEDDINGS=full
COPY requirements.txt .
RUN pip install --upgrade pip && \
    if [ "$EMBEDDINGS" = "light" ]; then grep -v '^sentence-transformers' requirements.txt > /tmp/req.txt; \
    else cp requirements.txt /tmp/req.txt; fi && \
    pip install -r /tmp/req.txt && rm /tmp/req.txt

COPY app ./app
COPY researchmind ./researchmind

USER app
# Download the embedding model at build time, so containers start without network access.
RUN if [ "$EMBEDDINGS" != "light" ]; then \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"; fi
ENV HF_HUB_OFFLINE=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/live').status == 200 else 1)"
# --forwarded-allow-ips: trust X-Forwarded-* only from the reverse proxy on the internal network.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
