import subprocess
import time
from flask import Flask, Response

app = Flask(__name__)

# 🎥 YouTube Live Streams
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",
}

# Function to get YouTube stream URL using yt-dlp and cookies
def get_youtube_stream_url(youtube_url):
    command = [
        "yt-dlp", 
        "--cookies", "/mnt/data/cookies.txt", 
        "--force-generic-extractor", 
        "-f", "91",  # Audio format
        "-g", youtube_url  # Get the URL of the stream (without downloading)
    ]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stream_url = result.stdout.strip()
        if stream_url:
            return stream_url
        else:
            print("⚠️ No stream URL found.")
            return None
    except Exception as e:
        print(f"⚠️ yt-dlp error: {e}")
        return None

# 🔄 Streaming function with error handling
def generate_youtube_stream(youtube_url):
    process = None
    while True:
        # Get the stream URL from yt-dlp
        stream_url = get_youtube_stream_url(youtube_url)
        if not stream_url:
            print("⚠️ Failed to extract stream URL.")
            time.sleep(5)  # Wait before retrying
            continue
        
        if process:
            process.kill()  # Stop old FFmpeg instance before restarting

        process = subprocess.Popen(
            [
                "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1",
                "-reconnect_delay_max", "10", "-fflags", "nobuffer", "-flags", "low_delay",
                "-i", stream_url, "-vn", "-ac", "1", "-b:a", "40k", "-buffer_size", "1024k", "-f", "mp3", "-"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=8192
        )

        print(f"🎥 Extracting YouTube audio from: {youtube_url} with cookies")

        try:
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk
        except GeneratorExit:
            process.kill()
            break
        except Exception as e:
            print(f"⚠️ YouTube stream error: {e}")

        print("🔄 yt-dlp stopped, restarting stream...")
        time.sleep(5)

# 🌍 API to stream selected YouTube live station
@app.route("/<station_name>")
def stream(station_name):
    youtube_url = YOUTUBE_STREAMS.get(station_name)
    if not youtube_url:
        return "⚠️ Station not found", 404

    return Response(generate_youtube_stream(youtube_url), mimetype="audio/mpeg")

# 🚀 Start Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)