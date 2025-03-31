#!/bin/bash

# Start SRS server
cd /srs && ./objs/srs -c conf/srs.conf &

# Wait for SRS to initialize
sleep 5

# Start FFmpeg streaming to SRS RTMP
ffmpeg -re -i "http://ktv.im:8080/44444/44444/81825" \
    -c:v libx264 -b:v 300k -preset ultrafast -tune zerolatency \
    -c:a aac -b:a 32k -f flv rtmp://localhost/live/stream