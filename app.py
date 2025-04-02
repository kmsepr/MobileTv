from flask import Flask, Response
import subprocess
import os

app = Flask(__name__)

YOUTUBE_URL = "https://www.youtube.com/live/xxcdNDOleBw?si=PAZR5uS4jjGxLJaa"
YTDLP_PATH = "/opt/venv/bin/yt-dlp"
COOKIES_PATH = "/mnt/data/cookies.txt"

def generate_stream():
    yt_cmd = [YTDLP_PATH, "-f", "bestaudio", "-g", YOUTUBE_URL]

    # Check if cookies.txt exists before using it
    if os.path.exists(COOKIES_PATH):
        yt_cmd.insert(1, "--cookies")
        yt_cmd.insert(2, COOKIES_PATH)

    process = subprocess.run(yt_cmd, capture_output=True, text=True)

    if process.returncode != 0:
        print("Error getting stream URL")
        return

    stream_url = process.stdout.strip()

    ffmpeg_cmd = [
        "ffmpeg", "-re", "-i", stream_url,
        "-vn", "-ac", "1", "-b:a", "40k", "-ar", "22050",
        "-f", "mp3", "pipe:1"
    ]

    ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    try:
        while True:
            chunk = ffmpeg_process.stdout.read(1024)
            if not chunk:
                break
            yield chunk
    finally:
        ffmpeg_process.kill()

@app.route("/radio")
def radio_stream():
    return Response(generate_stream(), mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)