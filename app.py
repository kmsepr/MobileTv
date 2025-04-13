import os
import logging
import subprocess
import time
from flask import Flask, Response

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Non-live YouTube videos
YOUTUBE_STREAMS = {
    "kalyanaraman": "https://www.youtube.com/watch?v=e_bMbcZt9b4",
    "madhuram": "https://www.youtube.com/watch?v=igmUGt3FIWM",
    # Add more videos as needed
}

def get_youtube_audio_url(youtube_url):
    """Get direct audio stream URL from a non-live YouTube video."""
    try:
        command = ["/usr/local/bin/yt-dlp", "-f", "bestaudio", "-g", youtube_url]

        if os.path.exists("/mnt/data/cookies.txt"):
            command.insert(2, "--cookies")
            command.insert(3, "/mnt/data/cookies.txt")

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logging.error(f"yt-dlp error: {result.stderr}")
            return None
    except Exception as e:
        logging.exception("Exception getting audio URL")
        return None

def generate_stream(url):
    """Stream audio using ffmpeg."""
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-user_agent", "Mozilla/5.0",
            "-i", url,
            "-vn",
            "-ac", "1",
            "-b:a", "40k",
            "-f", "mp3",
            "-"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=4096
    )

    logging.info(f"Streaming from: {url}")

    try:
        for chunk in iter(lambda: process.stdout.read(4096), b""):
            yield chunk
            time.sleep(0.02)
    except GeneratorExit:
        process.terminate()
        process.wait()
    except Exception as e:
        logging.error(f"Stream error: {e}")
        process.terminate()
        process.wait()

@app.route("/<video_name>")
def stream(video_name):
    """Stream the given YouTube video as audio."""
    youtube_url = YOUTUBE_STREAMS.get(video_name)
    if not youtube_url:
        return "Video not found", 404

    stream_url = get_youtube_audio_url(youtube_url)
    if not stream_url:
        return "Unable to fetch stream", 500

    return Response(generate_stream(stream_url), mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)