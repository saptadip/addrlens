# Per-city app image. Target size ~200 MB (plan §7.1).
# NO model weights, NO mlx-lm / llama.cpp — those live in ops/Dockerfile.inference.
#
# Build context = repo root (micro-service/). Build:
#   docker build -f ops/Dockerfile.app -t addrlens-app .

FROM python:3.11-slim AS base

# System deps: libgeos for shapely (the wheels bundle it, but keep tzdata for
# structured log timestamps and ca-certificates for outbound HTTPS to WFS).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# uv is the fastest resolver + installer; the copy comes from the official image
# so no pip bootstrap on top of the slim base.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

# ---- deps layer (cacheable) ----
# Copy the manifest first so `docker build` reuses the deps layer whenever only
# app code has changed.
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

# ---- app layer ----
COPY app ./app
COPY web ./web

# Non-root user (production security). uid 10001 avoids collisions with
# base-image system users.
RUN useradd -u 10001 -m -s /sbin/nologin addrlens \
    && chown -R addrlens:addrlens /srv
USER addrlens

ENV CITY=berlin \
    PORT=8001 \
    INFERENCE_URL=http://inference:8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
