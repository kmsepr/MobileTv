FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg + required build tools)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install yt-dlp first (latest version)
RUN pip install --no-cache-dir --upgrade pip yt-dlp

# Copy dependencies and install them
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Flask app
COPY . /app/

# Expose the port
EXPOSE 8000

# Run the app
CMD ["python", "app.py"]