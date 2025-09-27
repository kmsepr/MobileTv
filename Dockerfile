FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential cmake git libass-dev libfreetype6-dev \
    libsdl2-dev libtool libva-dev libvdpau-dev libvorbis-dev libxcb1-dev \
    libxcb-shm0-dev libxcb-xfixes0-dev meson nasm pkg-config texinfo wget yasm \
    zlib1g-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Compile FFmpeg (latest stable)
ENV FFMPEG_VERSION=6.0
RUN wget https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.bz2 && \
    tar xjf ffmpeg-${FFMPEG_VERSION}.tar.bz2 && \
    cd ffmpeg-${FFMPEG_VERSION} && \
    ./configure \
        --enable-gpl \
        --enable-nonfree \
        --enable-libass \
        --enable-libfreetype \
        --enable-libvorbis \
        --enable-libxcb \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvpx \
        --enable-libmp3lame \
        --enable-libopus \
        --enable-libfdk-aac \
        --enable-libdav1d \
    && make -j$(nproc) && make install && cd .. && rm -rf ffmpeg-${FFMPEG_VERSION}*

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip yt-dlp
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy Flask app
COPY . /app/

# Expose port
EXPOSE 8000

# Run Flask app
CMD ["python", "app.py"]