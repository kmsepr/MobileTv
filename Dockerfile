# Use an official Python base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . .

# Expose the port Flask will run on
EXPOSE 8080

# Command to run the Flask app
CMD ["python", "app.py"]