FROM python:3.11-slim

# -----------------------------
# Set working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# Install system dependencies
# -----------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        git \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Upgrade pip and install Python dependencies
# -----------------------------
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir flask requests yt-dlp gunicorn

# -----------------------------
# Copy application code
# -----------------------------
COPY . /app

# -----------------------------
# Expose port
# -----------------------------
EXPOSE 8000

# -----------------------------
# Start Gunicorn with 2 workers and 2 threads
# -----------------------------
CMD ["gunicorn", "-w", "2", "--threads", "2", "-b", "0.0.0.0:8000", "app:app"]