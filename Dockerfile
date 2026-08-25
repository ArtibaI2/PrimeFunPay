# ==========================================
# FunPay Bot - Production Dockerfile
# ==========================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Moscow

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p storage/logs storage/goods

# Expose Web Dashboard port
EXPOSE 8080

# Healthcheck (supports custom PORT from cloud providers like Render)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD sh -c "curl -f http://localhost:${PORT:-8080}/ping || exit 1"

# Run bot
CMD ["python", "main.py"]
