import subprocess
import time
import logging
from flask import Flask, Response

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# List of radio stations & YouTube Live links
RADIO_STATIONS = {
    "media_one": "https://www.youtube.com/watch?v=-8d8-c0yvyU",
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
}

def get_youtube_audio_url(youtube_url):
    """Extracts direct audio stream URL from YouTube Live using yt-dlp."""
    try:
        command = [
            "yt-dlp",
            "--cookies", "/mnt/data/cookies.txt",
            "-f", "91",
            "-g", youtube_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logging.error(f"Error extracting YouTube audio: {result.stderr}")
            return None
    except Exception as e:
        logging.error(f"Exception: {e}")
        return None

def generate_stream(url):
    """Streams audio using FFmpeg and auto-reconnects."""
    while True:
        if "youtube.com" in url or "youtu.be" in url:
            url = get_youtube_audio_url(url)
            if not url:
                logging.warning("Failed to get YouTube stream URL, retrying in 30 seconds...")
                time.sleep(30)
                continue

        process = subprocess.Popen(
            [
                "ffmpeg", "-reconnect_at_eof", "1",
                "-i", url, "-vn",
                "-b:a", "64k", "-buffer_size", "2048k", "-f", "mp3", "-"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=8192
        )

        logging.info(f"Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk
        except GeneratorExit:
            process.kill()
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")

        logging.info("FFmpeg stopped, restarting stream...")
        time.sleep(5)

@app.route("/<station_name>")
def stream(station_name):
    """Serve the requested station as a live stream."""
    url = RADIO_STATIONS.get(station_name)

    if not url:
        return "Station not found", 404

    return Response(generate_stream(url), mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
