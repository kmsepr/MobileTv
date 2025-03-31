#!/bin/bash

# Start SRS server
cd /srs && ./objs/srs -c conf/srs.conf &

# Wait for SRS to initialize
sleep 5

# Start FFmpeg streaming to an MP4 file (FastStart for progressive playback)
ffmpeg -re -i "http://ktv.im:8080/44444/44444/81825" \
    -c:v libx264 -b:v 300k -movflags +faststart \
    -c:a aac -b:a 32k -f mp4 /var/www/html/stream.mp4

# Keep the container running
tail -f /dev/null