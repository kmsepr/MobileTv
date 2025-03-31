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

# Clone and build SRS (Simple RTMP Server)
RUN git clone --depth=1 https://github.com/ossrs/srs.git /srs \
    && cd /srs/trunk \
    && ./configure --rtmp-server \
    && make

# Ensure the configuration directory exists
RUN mkdir -p /srs/conf

# Copy the SRS config file
COPY conf/srs.conf /srs/conf/srs.conf

# Copy the streaming script
COPY stream.sh /stream.sh
RUN chmod +x /stream.sh

# Expose necessary ports
EXPOSE 1935 8080 1985

# Start SRS and FFmpeg
CMD ["/stream.sh"]