FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy dependencies file and install packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Flask app
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the app
CMD ["python", "app.py"]
