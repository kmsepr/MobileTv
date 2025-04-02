import subprocess
import time
import threading
from flask import Flask, Response

app = Flask(__name__)

# 📡 List of YouTube Live Streams
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live"
}

# 🌐 Cache for storing direct stream URLs
CACHE = {}

def get_youtube_audio_url(youtube_url):
    """Extracts direct audio stream URL from YouTube Live."""
    try:
        command = [
            "/usr/local/bin/yt-dlp", 
            "--cookies", "/mnt/data/cookies.txt",
            "--force-generic-extractor",
            "-f", "91",  # Audio format
            "-g", youtube_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Error extracting YouTube audio: {result.stderr}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def refresh_stream_urls():
    """Refresh stream URLs every 60 minutes."""
    while True:
        print("🔄 Refreshing stream URLs...")
        for name, yt_url in YOUTUBE_STREAMS.items():
            url = get_youtube_audio_url(yt_url)
            if url:
                CACHE[name] = url
                print(f"✅ Updated {name}: {url}")
            else:
                print(f"❌ Failed to update {name}")
        time.sleep(3600)  # Refresh every 60 minutes

# Start the background thread for URL refreshing
threading.Thread(target=refresh_stream_urls, daemon=True).start()

def generate_stream(url):
    """Streams audio using FFmpeg and auto-reconnects."""
    while True:
        process = subprocess.Popen(
            [
                "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1",
                "-reconnect_delay_max", "10", "-i", url, "-vn",
                "-b:a", "64k", "-bufsize", "1024k", "-f", "mp3", "-"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096
        )

        print(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
        except GeneratorExit:
            print("❌ Client disconnected. Killing FFmpeg process...")
            process.terminate()
            process.wait()
            break
        except Exception as e:
            print(f"Stream error: {e}")

        print("⚠️ FFmpeg stopped, restarting stream...")
        process.terminate()
        process.wait()
        time.sleep(5)

@app.route("/<station_name>")
def stream(station_name):
    """Serve the requested station as a live stream."""
    url = CACHE.get(station_name)

    if not url:
        return "Station not found or not available", 404

    return Response(generate_stream(url), mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
