# Use slim Python image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg + curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install yt-dlp
RUN pip install --no-cache-dir --upgrade pip yt-dlp

# Copy app files
COPY . /app

# Expose port
EXPOSE 8000

# Run Flask app
CMD ["python", "app.py"]