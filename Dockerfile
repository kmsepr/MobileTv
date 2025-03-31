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
COPY stream_to_http.sh /usr/local/bin/stream_to_http.sh
RUN chmod +x /usr/local/bin/stream_to_http.sh

# Start streaming script in the background
RUN echo "#!/bin/bash\n/usr/local/bin/stream_to_http.sh &\nexec apachectl -D FOREGROUND" > /start.sh && chmod +x /start.sh

# Expose HTTP port
EXPOSE 80

# Run script and start Apache
CMD ["/bin/bash", "/start.sh"]
