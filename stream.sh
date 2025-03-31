#!/bin/bash

# Define variables
YOUTUBE_URL=$1
OUTPUT_FILE="symbian_video.mp4"

# Download YouTube video
yt-dlp -f "best" -o "video.mp4" "$YOUTUBE_URL"

# Convert to Symbian-compatible format
ffmpeg -i video.mp4 -vf "scale=320:240" -c:v libx264 -b:v 500k -c:a aac -b:a 64k $OUTPUT_FILE

# Move to Apache directory
mv $OUTPUT_FILE /var/www/html/videos/

# Output the streaming URL
echo "Your video is ready at: http://localhost/videos/$OUTPUT_FILE"