import subprocess
import time
from flask import Flask, Response

app = Flask(__name__)

# 🎥 YouTube Live Streams
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",
}

# 🔄 Streaming function with yt-dlp and FFmpeg
def generate_youtube_stream(youtube_url):
    process = None
    while True:
        if process:
            process.kill()  # Stop old yt-dlp instance before restarting
        
        process = subprocess.Popen(
            [
                "/opt/venv/bin/yt-dlp", "-f", "bestaudio", "-o", "-", 
                "--cookies", "/mnt/data/cookies.txt", youtube_url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=8192
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