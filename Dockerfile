FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install system dependencies (ffmpeg for yt-dlp, curl useful for debugging)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip

# Install app dependencies
RUN pip install --no-cache-dir flask requests yt-dlp gunicorn

# Copy your app code
COPY . /app

# Expose port
EXPOSE 8000

# Start app with Gunicorn (2 workers, bind to all addresses)
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]