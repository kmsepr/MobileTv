#!/bin/bash

OUTPUT_DIR="/var/www/html/videos"
OUTPUT_FILE="stream.mp4"

while true
do
    ffmpeg -re -i "https://video.yementdy.tv/hls/yementoday.m3u8" \
        -c:v h263 -b:v 70k -r 15 -vf scale=176:144 \
        -c:a aac -b:a 32k -ac 1 -ar 32000 \
        -f mp4 "$OUTPUT_DIR/$OUTPUT_FILE"

    sleep 5
done