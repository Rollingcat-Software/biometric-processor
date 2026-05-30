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
# REPRODUCIBLE BASE (P0-2b, 2026-05-30): pin BOTH FROM lines by DIGEST so the
# floating `python:3.12-slim` tag can never silently drift the Debian point
# release out from under us again (the 13.4→13.5 move + torch/onnxruntime
# native drift is what segfaulted the MiniFASNet ONNX preload under prod
# read_only+cap_drop). Digest below = `python:3.12.13-slim` (Debian 13 trixie,
# Python 3.12.13) as resolved on 2026-05-30. See CLAUDE.md P0-2b for the
# boot-test outcome and the digest-selection rationale (the 13.4-era trixie
# digest is no longer tag-served by Docker Hub — overwritten by the 13.5
# rebuild on 2026-05-22 — so this pins the settled, no-longer-floating digest).
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 AS model-fetcher

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
# Same digest pin as the model-fetcher stage (see P0-2b note above).
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

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

# Copy requirements + the known-good lock.
COPY requirements.txt .
COPY requirements-known-good-2026-05-29.lock .

# REPRODUCIBLE DEPS (P0-2b): the lock is a full `pip freeze` of the proven
# working image (75347c98). We install the staged ML deps + requirements.txt
# WITH the lock applied as a pip CONSTRAINTS file (`-c`), so every transitive
# resolves to the exact known-good version — without letting the lock's plain
# `tensorflow==2.21.0` line pull the GPU wheel (we install `tensorflow-cpu`
# instead; a constraints file only pins, it never forces an install). The
# tf-cpu / deepface / opencv special-casing below is preserved verbatim and
# each version is bumped to the lock's exact pin.
#
# Strip the three lines that need special handling out of the constraints file
# so `-c` does not (a) try to install plain `tensorflow` or (b) conflict with
# our `--no-deps` deepface / headless-opencv staging:
#   - tensorflow==      (we use tensorflow-cpu, line kept separately)
#   - deepface==        (installed --no-deps)
#   - opencv-python-headless==  (installed/forced separately, last)
#   - spoof-detector @ git+...  (VCS line; comes from requirements.txt pin)
RUN grep -viE '^(tensorflow==|deepface==|opencv-python-headless==|spoof-detector @)' \
        requirements-known-good-2026-05-29.lock > /tmp/constraints.txt

# 1. First install opencv-python-headless to claim cv2 namespace (lock pin).
RUN pip install --no-cache-dir opencv-python-headless==4.13.0.92

# 2. Install tensorflow-cpu (big dependency) — lock pins tensorflow_cpu==2.21.0.
RUN pip install --no-cache-dir -c /tmp/constraints.txt tensorflow-cpu==2.21.0

# 3. Install deepface WITHOUT dependencies to avoid opencv-python (lock pin).
#    Then install missing deepface dependencies manually (lock pins).
RUN pip install --no-cache-dir --no-deps deepface==0.0.98 && \
    pip install --no-cache-dir -c /tmp/constraints.txt lightphe==0.0.24 lightdsa==0.0.3

# 4. Install remaining requirements under the lock constraints so every
#    transitive (torch, onnxruntime, numpy, uniface, mediapipe, ...) lands on
#    the exact known-good version. requirements.txt pins librosa==0.9.2 to avoid
#    the numba @stencil/@guvectorize crash on Python 3.12; the lock agrees.
RUN pip install --no-cache-dir -c /tmp/constraints.txt -r requirements.txt

# 5. Force uninstall opencv-python if it got installed, reinstall headless
#    (lock pin, --no-deps so the force-reinstall can't drag numpy back).
RUN pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true && \
    pip install --no-cache-dir --force-reinstall --no-deps opencv-python-headless==4.13.0.92

# Verify dependencies work together
RUN python -c "import cv2; print('OpenCV version:', cv2.__version__)" && \
    python -c "import numpy; print('NumPy version:', numpy.__version__)" && \
    python -c "import tensorflow; print('TensorFlow version:', tensorflow.__version__)"

# Bake MediaPipe face_landmarker.task into the image (2026-05-12).
# The new Tasks API (mp.tasks.vision.FaceLandmarker) requires a .task model
# asset; without it the gaze tracker, active-liveness detector, quality
# assessor and landmark detector all fail-soft with "model missing".
# Pinning + SHA-verifying at build time gives us a reproducible image and
# closes the supply-chain check the loader expects at runtime.
# Companion env vars in .env.example:
#   FACE_LANDMARKER_MODEL_PATH=/app/models/face_landmarker.task
#   FACE_LANDMARKER_MODEL_SHA256=64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff
ARG FACE_LANDMARKER_SHA256=64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff
RUN set -eux; \
    mkdir -p /app/models; \
    curl -fsSL -o /app/models/face_landmarker.task \
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"; \
    echo "${FACE_LANDMARKER_SHA256}  /app/models/face_landmarker.task" | sha256sum -c -; \
    chmod 0644 /app/models/face_landmarker.task

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
