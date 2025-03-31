# Use Ubuntu as the base image
FROM ubuntu:latest

# Install dependencies
RUN apt update && apt install -y \
    ffmpeg \
    git \
    nginx \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build SRS
RUN git clone --depth=1 https://github.com/ossrs/srs.git /srs \
    && cd /srs \
    && ./configure --rtmp-server && make

# Copy the SRS config file
COPY conf/srs.conf /srs/conf/srs.conf

# Copy the stream script
COPY stream.sh /stream.sh
RUN chmod +x /stream.sh

# Configure Nginx to serve MP4 files
RUN echo 'server { \
    listen 80; \
    location / { root /var/www/html; index index.html; } \
    location /stream.mp4 { add_header Content-Type video/mp4; } \
}' > /etc/nginx/sites-enabled/default

# Expose ports (RTMP & HTTP)
EXPOSE 1935 80

# Start services
CMD service nginx start && /stream.sh