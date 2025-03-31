#!/bin/bash

# Define the output directory and file name
OUTPUT_DIR="/var/www/html/videos"
OUTPUT_FILE="stream.3gp"

# Ensure the output directory exists
mkdir -p "$OUTPUT_DIR"

# Infinite loop to keep the streaming and transcoding process running
while true
do
    ffmpeg -re -i "http://ktv.im:8080/44444/44444/81825" \
        -c:v h263 -b:v 70k -r 15 -s 176x144 \
        -c:a aac -b:a 32k -ac 1 -ar 32000 \
        -f 3gp "$OUTPUT_DIR/$OUTPUT_FILE"

    # Wait for 5 seconds before restarting the process in case of failure
    sleep 5
done