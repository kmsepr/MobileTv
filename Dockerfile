# Base image
FROM ubuntu:latest

# Install required packages
RUN apt update && apt install -y \
    nginx ffmpeg python3-pip \
    && pip3 install yt-dlp \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /videos /scripts

# Copy scripts & config
COPY start.sh /scripts/start.sh
COPY nginx.conf /etc/nginx/nginx.conf

# Set permissions
RUN chmod +x /scripts/start.sh

# Expose HTTP port
EXPOSE 80

# Start server
CMD ["/bin/bash", "/scripts/start.sh"]