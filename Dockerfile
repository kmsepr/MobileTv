# ------------------------------------------------------------
# Base image
# ------------------------------------------------------------
FROM python:3.11-slim

# ------------------------------------------------------------
# Enable contrib & non-free + install build deps
# ------------------------------------------------------------
RUN sed -i 's/Components: main/Components: main contrib non-free/' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y \
        procps \
        gcc \
        build-essential \
        make \
        yasm \
        libfdk-aac-dev \
        libssl-dev \
        wget \
        python3 \
        pkg-config \
        libopencore-amrwb-dev \
        libopencore-amrnb-dev \
        libmp3lame-dev \
        libvorbis-dev \
        libx264-dev \
        libx265-dev \
        cmake \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Download & compile FFmpeg 4.4.5
# ------------------------------------------------------------
RUN wget https://ffmpeg.org/releases/ffmpeg-4.4.5.tar.gz && \
    tar -xvf ffmpeg-4.4.5.tar.gz -C /usr/src

RUN cd /usr/src/ffmpeg-4.4.5 && \
    ./configure \
        --enable-gpl \
        --enable-nonfree \
        --enable-libfdk-aac \
        --enable-openssl \
        --enable-libopencore-amrwb \
        --enable-libopencore-amrnb \
        --enable-libmp3lame \
        --enable-libvorbis \
        --enable-libx264 \
        --enable-libx265 \
        --disable-debug \
        --enable-static \
        --disable-shared \
        --extra-cflags="-O3" \
    && make -j$(nproc) \
    && make install \
    && hash -r

# ------------------------------------------------------------
# Working directory
# ------------------------------------------------------------
WORKDIR /app

# ------------------------------------------------------------
# Upgrade pip and install Python deps
# ------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir flask requests yt-dlp gunicorn

# ------------------------------------------------------------
# Copy project
# ------------------------------------------------------------
COPY . /app

# ------------------------------------------------------------
# Expose port
# ------------------------------------------------------------
EXPOSE 8000

# ------------------------------------------------------------
# Start Gunicorn
# ------------------------------------------------------------
CMD ["gunicorn", "-w", "2", "--threads", "2", "-b", "0.0.0.0:8000", "app:app"]