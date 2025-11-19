FROM python:3.11-slim

WORKDIR /app

# Enable non-free repo for x264
RUN sed -i 's/^Components: main$/Components: main contrib non-free/' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        wget \
        yasm \
        libx264-dev \
        libssl-dev \
        pkg-config \
        ffmpeg \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Download and compile FFmpeg with x264 + native AAC
RUN wget https://ffmpeg.org/releases/ffmpeg-4.4.5.tar.gz && \
    tar -xvf ffmpeg-4.4.5.tar.gz && \
    cd ffmpeg-4.4.5 && \
    ./configure \
        --enable-gpl \
        --enable-libx264 \
        --enable-nonfree \
        --enable-openssl \
        --disable-debug \
        --enable-static \
        --disable-shared \
        --extra-cflags="-O3" \
    && make -j$(nproc) && make install

# Python deps
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir flask requests yt-dlp gunicorn

COPY . /app

EXPOSE 8000

CMD ["gunicorn", "-w", "2", "--threads", "2", "-b", "0.0.0.0:8000", "app:app"]