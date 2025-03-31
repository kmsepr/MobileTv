# Use Ubuntu as the base image
FROM ubuntu:latest

# Install necessary packages
RUN apt update && apt install -y \
    apache2 \
    ffmpeg \
    curl \
    yt-dlp \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for videos
RUN mkdir -p /var/www/html/videos

# Set the working directory
WORKDIR /var/www/html/videos

# Copy the script to container
COPY stream.sh /stream.sh
RUN chmod +x /stream.sh

# Expose Apache's HTTP port
EXPOSE 80

# Start Apache server
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]