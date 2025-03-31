#!/bin/bash

VIDEO_URL="$1"
OUTPUT_DIR="/var/www/html/videos"
OUTPUT_FILE="$OUTPUT_DIR/video.mp4"

# Download the video
yt-dlp -f "best" -o "$OUTPUT_FILE" "$VIDEO_URL"

# Convert to Symbian-compatible format (H.264 + AAC)
ffmpeg -i "$OUTPUT_FILE" -vf "scale=320:240" -c:v libx264 -b:v 500k -c:a aac -b:a 64k "$OUTPUT_DIR/symbian_video.mp4"

echo "Video ready: http://your-server-ip/videos/symbian_video.mp4"