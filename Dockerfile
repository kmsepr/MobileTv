FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp and Flask
RUN pip install --no-cache-dir yt-dlp Flask

# Copy the Flask app
COPY app.py /app/app.py

# Expose the port the app runs on
EXPOSE 8000

# Command to run the app
CMD ["python", "app.py"]
