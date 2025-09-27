# -----------------------
# Base image
# -----------------------
FROM python:3.11-slim

# -----------------------
# Set working directory
# -----------------------
WORKDIR /app

# -----------------------
# Install system dependencies
# -----------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg curl wget build-essential && \
    rm -rf /var/lib/apt/lists/*

# -----------------------
# Copy requirements & install Python packages
# -----------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------
# Copy app
# -----------------------
COPY app.py .

# -----------------------
# Expose port
# -----------------------
EXPOSE 8000

# -----------------------
# Run app
# -----------------------
CMD ["python", "app.py"]