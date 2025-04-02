import subprocess
import time
import threading
from flask import Flask, Response

app = Flask(__name__)

# List of radio stations & YouTube Live links
RADIO_STATIONS = {
    "media_one": "https://www.youtube.com/watch?v=-8d8-c0yvyU",
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
}

# Global cache for URLs
cached_urls = {station: None for station in RADIO_STATIONS}
last_updated = {station: None for station in RADIO_STATIONS}

def get_youtube_audio_url(youtube_url):
    """Extracts direct audio stream URL from YouTube Live using yt-dlp."""
    try:
        command = [  
        "yt-dlp",  
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

def update_url_periodically():
    """Updates the cached URLs every 30 minutes."""
    while True:
        time.sleep(1800)  # 30 minutes
        for station in RADIO_STATIONS:
            url = RADIO_STATIONS[station]
            if "youtube.com" in url or "youtu.be" in url:
                updated_url = get_youtube_audio_url(url)
                if updated_url:
                    cached_urls[station] = updated_url
                    last_updated[station] = time.time()
                    print(f"Updated {station} URL.")
                else:
                    print(f"Failed to update URL for {station}.")

def generate_stream(station_name):
    """Streams audio using FFmpeg and auto-reconnects."""
    while True:
        url = cached_urls.get(station_name)
        if not url:
            print("Failed to get stream URL, retrying in 30 seconds...")
            time.sleep(30)
            continue

        process = subprocess.Popen(
        [
            "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10", "-i", url, "-vn",
            "-b:a", "64k", "-buffer_size", "1024k", "-f", "mp3", "-"
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

        print(f"Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk
        except GeneratorExit:
            process.kill()
            break
        except Exception as e:
            print(f"Stream error: {e}")
            stderr_output = process.stderr.read().decode("utf-8")
            print(f"FFmpeg stderr: {stderr_output}")

        print("FFmpeg stopped, restarting stream...")
        time.sleep(5)

@app.route("/<station_name>")
def stream(station_name):
    """Serve the requested station as a live stream."""
    if station_name not in RADIO_STATIONS:
        return "Station not found", 404

    return Response(generate_stream(station_name), mimetype="audio/mpeg")

if __name__ == "__main__":
    # Start the periodic URL update in the background
    threading.Thread(target=update_url_periodically, daemon=True).start()

    app.run(host="0.0.0.0", port=8000, debug=True)
