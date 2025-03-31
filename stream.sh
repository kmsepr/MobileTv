#!/bin/bash

OUTPUT_DIR="/var/www/html/videos"
OUTPUT_FILE="stream.3gp"

while true
do
    ffmpeg -re -fflags +genpts -i "https://video.yementdy.tv/hls/yementoday.m3u8" \
        -c:v h263 -b:v 70k -r 15 -vf scale=176:144 \
        -c:a libopencore_amrnb -b:a 12.2k -ac 1 -ar 8000 \
        -f 3gp "$OUTPUT_DIR/$OUTPUT_FILE"

    sleep 5
done