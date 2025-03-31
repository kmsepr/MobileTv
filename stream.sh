#!/bin/bash

OUTPUT_DIR="/var/www/html/videos"
OUTPUT_FILE="stream.3gp"

while true
do
    ffmpeg -re -i "https://edge1.1internet.tv/dash-live2/streams/1tv-dvr/1tvdash.mpd" \
        -map 0:v:3 -map 0:a:1 \
        -c:v h263 -b:v 70k -r 15 -vf scale=176:144 \
        -c:a aac -b:a 32k -ar 32000 -ac 1 \
        -f 3gp "$OUTPUT_DIR/$OUTPUT_FILE"

    sleep 5
done