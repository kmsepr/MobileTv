FROM debian:stable-slim AS ffmpeg-build

# ---------------------------------------------
# Install build dependencies
# ---------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf automake build-essential cmake libtool pkg-config \
    yasm nasm \
    libx264-dev libx265-dev libnuma-dev \
    libvpx-dev libmp3lame-dev libopus-dev \
    git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# ---------------------------------------------
# Build fdk-aac from source WITH LOGS
# ---------------------------------------------
RUN echo "===== CLONING fdk-aac =====" && \
    git clone --depth 1 https://github.com/mstorsjo/fdk-aac.git && \
    cd fdk-aac && \
    echo "===== AUTORECONF =====" && autoreconf -fiv && \
    echo "===== CONFIGURE fdk-aac =====" && ./configure --prefix=/usr/local --disable-shared && \
    echo "===== MAKE fdk-aac =====" && make -j$(nproc) V=1 && \
    echo "===== INSTALL fdk-aac =====" && make install

# ---------------------------------------------
# Build FFmpeg WITH LOGS
# ---------------------------------------------
WORKDIR /tmp/ffmpeg
RUN echo "===== CLONING FFmpeg =====" && \
    git clone --depth 1 https://github.com/FFmpeg/FFmpeg.git .

RUN echo "===== CONFIGURE FFmpeg =====" && \
    ./configure \
        --prefix=/usr/local \
        --pkg-config-flags="--static" \
        --extra-cflags="-I/usr/local/include" \
        --extra-ldflags="-L/usr/local/lib" \
        --extra-libs="-lpthread -lm" \
        --bindir=/usr/local/bin \
        --enable-gpl \
        --enable-nonfree \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvpx \
        --enable-libfdk-aac \
        --enable-libmp3lame \
        --enable-libopus \
        --enable-static \
        --disable-debug \
        --disable-doc \
        --disable-ffplay  | tee /tmp/ffmpeg_configure.log

RUN echo "===== MAKE FFmpeg =====" && \
    make -j$(nproc) V=1 | tee /tmp/ffmpeg_build.log && \
    echo "===== INSTALL FFmpeg =====" && \
    make install


# ===========================================================
# FINAL PYTHON IMAGE
# ===========================================================

FROM python:3.11-slim AS final

WORKDIR /app

COPY --from=ffmpeg-build /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-build /usr/local/bin/ffprobe /usr/local/bin/ffprobe

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir flask requests yt-dlp gunicorn

COPY . /app

EXPOSE 8000

CMD ["gunicorn", "-w", "2", "--threads", "2", "-b", "0.0.0.0:8000", "app:app"]