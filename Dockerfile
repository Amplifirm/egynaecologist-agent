FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    MALLOC_ARENA_MAX=2

# System libs:
#   ffmpeg              — needed for any audio resampling
#   libgomp1            — onnxruntime (silero VAD, turn detector)
#   libsndfile1         — soundfile / audio reading
#   libstdc++6 libgcc-s1 — ML wheels frequently link against these
#   build-essential gcc — fallback for any wheel that needs compiling
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl \
        libgomp1 libsndfile1 \
        libstdc++6 libgcc-s1 \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv pip install --system .

COPY . .

# Pre-download VAD + turn-detector models so cold starts don't time out.
# The `|| true` keeps the build resilient if HF is briefly unavailable.
RUN python agent.py download-files || true

CMD ["python", "agent.py", "start"]
