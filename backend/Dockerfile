# ============================================================
# IntelliDoc Backend Dockerfile
# ============================================================
# Multi-stage build for smaller production image
#
# How Docker works:
# 1. Define a base image (Python 3.11)
# 2. Copy code and install dependencies
# 3. Build creates an "image" (snapshot of the environment)
# 4. Running the image creates a "container" (running instance)
# ============================================================

# ── Stage 1: Builder ─────────────────────────────────────────
# Install dependencies in a temporary stage to keep final image small
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user --timeout=300 \
    torch==2.5.1+cpu torchvision==0.20.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --user --timeout=300 -r requirements.txt


# ── Stage 2: Production ─────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only (smaller than build deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create directories for ML models and FAISS index
RUN mkdir -p /app/ml/models_cache /app/rag/faiss_index

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the application
# Workers = 1 for ML (models share memory)
# Timeout = 300s for long ML operations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "300"]
