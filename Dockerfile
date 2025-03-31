FROM ubuntu:latest

# Install required packages
RUN apt update && apt install -y \
    apache2 \
    ffmpeg \
    yt-dlp \
    && rm -rf /var/lib/apt/lists/*

# Enable Apache modules for MP4 streaming
RUN a2enmod rewrite headers

# Create a directory for MP4 files
RUN mkdir -p /var/www/html/videos

# Set the document root to videos directory
RUN sed -i 's|DocumentRoot /var/www/html|DocumentRoot /var/www/html/videos|' /etc/apache2/sites-available/000-default.conf

# Expose HTTP port
EXPOSE 80

# Start Apache
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]