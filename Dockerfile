# Dockerfile for FIVUCSAS Biometric Processor (FastAPI)

# ============================================================================
# Stage 1: model-fetcher
# ----------------------------------------------------------------------------
# Bake-in stage for DeepFace / Facenet model weights so the runtime container
# does NOT need to download them on first request. Solves the 4th recurrence
# of `feedback_readonly_rootfs_cache_dirs` (2026-05-12): prod uses
# read_only:true rootfs, the cache named volume is owned by root:root, and
# DeepFace runs as uid 100 — first-inference downloads silently fail and
# the anti-spoof verdict collapses to a false-positive. By placing the
# weights inside the image layer (read-only by design, which is fine because
# DeepFace reads but never writes them) we get reproducible deploys + a
# verifiable supply chain (SHA256-checked at build time).
#
# Captured SHA256s (2026-05-12, from the running biometric-api container;
# cross-verified against upstream repos):
#   facenet512_weights.h5          3f76b5117a9ca574d536af8199e6720089eb4ad3dc7e93534496d88265de864f
#   centerface.onnx                77e394b51108381b4c4f7b4baf1c64ca9f4aba73e5e803b2636419578913b5fe
#   2.7_80x80_MiniFASNetV2.pth     a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0
#   4_0_0_80x80_MiniFASNetV1SE.pth 84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990
# ============================================================================
FROM python:3.12-slim AS model-fetcher

ARG FACENET512_SHA256=3f76b5117a9ca574d536af8199e6720089eb4ad3dc7e93534496d88265de864f
ARG CENTERFACE_SHA256=77e394b51108381b4c4f7b4baf1c64ca9f4aba73e5e803b2636419578913b5fe
ARG MINIFASNET_V2_SHA256=a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0
ARG MINIFASNET_V1SE_SHA256=84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# DeepFace looks for weights under $DEEPFACE_HOME/.deepface/weights/. Match
# that layout exactly so the runtime stage can just copy the directory tree
# verbatim into /tmp/.deepface/.
WORKDIR /models

RUN set -eux; \
    mkdir -p /models/.deepface/weights; \
    cd /models/.deepface/weights; \
    \
    curl -fsSL -o facenet512_weights.h5 \
        "https://github.com/serengil/deepface_models/releases/download/v1.0/facenet512_weights.h5"; \
    echo "${FACENET512_SHA256}  facenet512_weights.h5" | sha256sum -c -; \
    \
    curl -fsSL -o centerface.onnx \
        "https://github.com/Star-Clouds/CenterFace/raw/master/models/onnx/centerface.onnx"; \
    echo "${CENTERFACE_SHA256}  centerface.onnx" | sha256sum -c -; \
    \
    curl -fsSL -o 2.7_80x80_MiniFASNetV2.pth \
        "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"; \
    echo "${MINIFASNET_V2_SHA256}  2.7_80x80_MiniFASNetV2.pth" | sha256sum -c -; \
    \
    curl -fsSL -o 4_0_0_80x80_MiniFASNetV1SE.pth \
        "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth"; \
    echo "${MINIFASNET_V1SE_SHA256}  4_0_0_80x80_MiniFASNetV1SE.pth" | sha256sum -c -; \
    \
    chmod 0644 *.h5 *.onnx *.pth

# ============================================================================
# Stage 2: runtime
# ============================================================================
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    TF_USE_LEGACY_KERAS=1 \
    DEEPFACE_HOME=/tmp/.deepface \
    PORT=8001

WORKDIR /app

# Install system dependencies + Tesseract OCR with Turkish language pack.
# `gosu` is used by the entrypoint shim to drop privileges from root → uid 100
# after the (root-only) chown of any externally-mounted cache volume.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    curl \
    ffmpeg \
    gcc \
    git \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-tur \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# 1. First install opencv-python-headless to claim cv2 namespace
RUN pip install --no-cache-dir opencv-python-headless>=4.8.0

# 2. Install tensorflow-cpu (big dependency)
RUN pip install --no-cache-dir tensorflow-cpu==2.21.0

# 3. Install deepface WITHOUT dependencies to avoid opencv-python
#    Then install missing deepface dependencies manually
RUN pip install --no-cache-dir --no-deps deepface==0.0.98 && \
    pip install --no-cache-dir lightphe lightdsa

# 4. Install remaining requirements
# Note: requirements.txt pins librosa==0.9.2 to avoid numba @stencil/@guvectorize
# crash on Python 3.12 (AttributeError: get_call_template). librosa >= 0.10.0
# introduced eager-compiling numba decorators that crash at import time
# regardless of NUMBA_DISABLE_JIT. librosa 0.9.2 has no numba stencil usage.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Force uninstall opencv-python if it got installed, reinstall headless
RUN pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true && \
    pip install --no-cache-dir --force-reinstall opencv-python-headless>=4.8.0

# Verify dependencies work together
RUN python -c "import cv2; print('OpenCV version:', cv2.__version__)" && \
    python -c "import numpy; print('NumPy version:', numpy.__version__)" && \
    python -c "import tensorflow; print('TensorFlow version:', tensorflow.__version__)"

# Copy application code
COPY . .

# Create non-root user for security and ensure uploads dir is writable.
# Pin UID/GID 100/101 explicitly so host-side chown on a named volume
# (e.g. /var/lib/docker/volumes/biometric-processor_biometric_models/_data)
# matches the in-container `app` user across rebuilds. The default
# `--system` numbering on debian-slim is dynamic and previously drifted
# silently — see feedback_readonly_rootfs_cache_dirs.
RUN addgroup --system --gid 101 app \
    && adduser --system --ingroup app --uid 100 app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app

# ----------------------------------------------------------------------------
# Bake the four model files into the image at the path DeepFace expects.
# With read_only:true rootfs in prod, the image-baked content is read-only by
# design — fine because DeepFace only reads these files. The entrypoint shim
# below also seeds an empty mounted cache volume from /opt/baked-models so a
# fresh `docker volume rm` no longer requires the operator to remember to
# re-download MiniFASNet by hand (the bug pattern that triggered this PR).
# ----------------------------------------------------------------------------
COPY --from=model-fetcher --chown=100:101 /models/.deepface /opt/baked-models/.deepface

# Entrypoint shim (runs as root, drops to uid 100 via gosu):
#   1. Chowns any externally-mounted /tmp/.deepface volume to 100:101 so a
#      root-owned named volume does not silently break DeepFace cache writes
#      under uid 100 (the recurring bug pattern — 4th sighting 2026-05-12).
#   2. Seeds missing weight files from /opt/baked-models so a wiped named
#      volume immediately repopulates with the four critical model files,
#      removing operator memory as a load-bearing dependency.
# Both operations are idempotent and best-effort (|| true) — they never block
# container startup. After running them the shim execs the original CMD as
# `app` via gosu.
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# Expose port
EXPOSE ${PORT:-8001}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8001}/api/v1/health || exit 1

# NOTE: ENTRYPOINT starts as root so it can chown the mounted cache volume,
# then execs the CMD under uid 100 (`app`) via gosu. No `USER` directive
# here on purpose — the entrypoint owns privilege drop. Anyone bypassing
# the entrypoint (e.g. `docker run --entrypoint /bin/sh`) must drop
# privileges themselves; this is acceptable because debug bypasses are
# operator-initiated.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Start the application (uses PORT from environment, defaults to 8001).
# The entrypoint forwards $@ to `gosu app` so this CMD runs as uid 100.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
