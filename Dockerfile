# Dockerfile for FIVUCSAS Biometric Processor (FastAPI)
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    TF_USE_LEGACY_KERAS=1 \
    DEEPFACE_HOME=/tmp/.deepface \
    PORT=8001

WORKDIR /app

# Install system dependencies + Tesseract OCR with Turkish language pack
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
    build-essential \
    tesseract-ocr \
    tesseract-ocr-tur \
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

# Create non-root user for security and ensure uploads dir is writable
RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app

# Expose port
EXPOSE ${PORT:-8001}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8001}/api/v1/health || exit 1

USER app

# Start the application (uses PORT from environment, defaults to 8001)
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
