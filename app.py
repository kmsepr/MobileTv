from flask import Flask, Response, render_template_string
import subprocess
import yt_dlp

app = Flask(__name__)

# ---------------- TV STATIONS ----------------
TV_STREAMS = {
    "media_one": "https://live.mediaoneonline.com/hls/mediaone.m3u8",
    "safari_tv": "https://live.safari.tv/safari.m3u8",
    "victers_tv": "https://victerslive.kite.kerala.gov.in/hls/victers.m3u8",
}

# ---------------- YOUTUBE LINKS ----------------
YOUTUBE_LINKS = {
    "flowerstv": "https://www.youtube.com/watch?v=k0gPo3b3VbQ",
    "asianetnews": "https://www.youtube.com/watch?v=K7S5pB4VbqU",
}


# ---------------- HOME UI ----------------
@app.route("/")
def index():
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Live TV + YouTube</title>
            <style>
                body { font-family: sans-serif; background: #f4f4f4; margin: 0; }
                h1 { background: #00695c; color: white; padding: 10px; margin: 0; }
                .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; padding: 15px; }
                .card { background: white; border-radius: 10px; padding: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); }
                video { width: 100%; border-radius: 10px; background: black; }
                h3 { margin: 8px 0; text-align: center; }
            </style>
        </head>
        <body>
            <h1>📺 Live TV & YouTube Grid</h1>
            <div class="grid">
                {% for key, url in tv.items() %}
                <div class="card">
                    <h3>{{ key.replace("_"," ").title() }}</h3>
                    <video controls poster="" preload="none">
                        <source src="/tv/{{ key }}" type="video/mp4">
                        Your browser does not support video.
                    </video>
                </div>
                {% endfor %}

                {% for key, url in yt.items() %}
                <div class="card">
                    <h3>{{ key.replace("_"," ").title() }}</h3>
                    <video controls poster="" preload="none">
                        <source src="/yt/{{ key }}" type="video/mp4">
                        Your browser does not support video.
                    </video>
                </div>
                {% endfor %}
            </div>
        </body>
        </html>
        """,
        tv=TV_STREAMS,
        yt=YOUTUBE_LINKS,
    )


# ---------------- TV STREAM (FFmpeg Proxy) ----------------
@app.route("/tv/<station>")
def tv_stream(station):
    if station not in TV_STREAMS:
        return "Station not found", 404

    url = TV_STREAMS[station]

    def generate():
        ffmpeg_cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-i", url,
            "-c:v", "copy",
            "-c:a", "aac",
            "-f", "mp4",
            "-"
        ]
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
        finally:
            process.terminate()
            process.wait()

    return Response(generate(), mimetype="video/mp4")


# ---------------- YOUTUBE STREAM (yt-dlp + FFmpeg Proxy) ----------------
@app.route("/yt/<channel>")
def yt_stream(channel):
    if channel not in YOUTUBE_LINKS:
        return "YouTube channel not found", 404

    yt_url = YOUTUBE_LINKS[channel]

    # Extract best video URL
    ydl_opts = {"format": "best", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(yt_url, download=False)
        real_url = info["url"]

    def generate():
        ffmpeg_cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-i", real_url,
            "-c:v", "copy",
            "-c:a", "aac",
            "-f", "mp4",
            "-"
        ]
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
        finally:
            process.terminate()
            process.wait()

    return Response(generate(), mimetype="video/mp4")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)