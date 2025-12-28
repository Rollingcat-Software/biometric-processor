# Dockerfile for Google Cloud Run deployment
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    DEEPFACE_HOME=/tmp/.deepface \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create constraint file to prevent incompatible package versions
RUN echo "numpy<2.0" > /tmp/constraints.txt && \
    echo "keras<3.0" >> /tmp/constraints.txt

# Install dependencies with constraints to prevent numpy upgrade:
# 1. Pin numpy to compatible version (TensorFlow 2.15 requires numpy<2.0)
RUN pip install --no-cache-dir -c /tmp/constraints.txt "numpy>=1.26.0,<2.0"

# 2. First install opencv-python-headless to claim cv2 namespace
RUN pip install --no-cache-dir -c /tmp/constraints.txt opencv-python-headless>=4.8.0

# 3. Install tensorflow-cpu (big dependency)
RUN pip install --no-cache-dir -c /tmp/constraints.txt tensorflow-cpu==2.15.0

# 4. Install deepface WITHOUT dependencies to avoid opencv-python
#    Then install missing deepface dependencies manually
RUN pip install --no-cache-dir --no-deps deepface>=0.0.79 && \
    pip install --no-cache-dir -c /tmp/constraints.txt lightphe

# 5. Install remaining requirements with constraints
RUN pip install --no-cache-dir -c /tmp/constraints.txt -r requirements.txt

# 6. Force uninstall opencv-python if it got installed, reinstall headless
RUN pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true && \
    pip install --no-cache-dir -c /tmp/constraints.txt --force-reinstall opencv-python-headless>=4.8.0

# Verify dependencies work together
RUN python -c "import cv2; print('OpenCV version:', cv2.__version__)" && \
    python -c "import numpy; print('NumPy version:', numpy.__version__)" && \
    python -c "import tensorflow; print('TensorFlow version:', tensorflow.__version__)"

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Start the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
