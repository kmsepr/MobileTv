FROM debian:latest

# Install dependencies
RUN apt update && apt install -y \
    apache2 ffmpeg wget curl \
    libssl-dev libxml2-dev libvo-amrwbenc-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up Apache
RUN mkdir -p /var/www/html/videos && \
    chown -R www-data:www-data /var/www/html/videos

# Copy the stream script
COPY stream.sh /usr/local/bin/stream.sh
RUN chmod +x /usr/local/bin/stream.sh

# Expose HTTP port
EXPOSE 80

# Run stream script and start Apache
CMD ["/usr/local/bin/stream.sh"] && apachectl -D FOREGROUND