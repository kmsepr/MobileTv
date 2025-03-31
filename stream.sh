#!/bin/bash

# Start Nginx
service nginx start

# Check if a video URL is provided
if [ -n "$YOUTUBE_URL" ]; then
    echo "Downloading video from: $YOUTUBE_URL"
    
    # Download and convert
    yt-dlp -f best -o "/videos/video.mp4" "$YOUTUBE_URL"
    ffmpeg -i "/videos/video.mp4" -vf "scale=320:240" -c:v libx264 -b:v 500k -c:a aac -b:a 64k "/videos/symbian_video.mp4"

    echo "Video ready at: http://your-server-ip/videos/symbian_video.mp4"
fi

# Keep container running
tail -f /dev/null