import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string, abort

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (m3u8)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
}

# -----------------------
# YouTube Live Streams
# -----------------------
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
}

CACHE = {}  # Stores direct YouTube live URLs
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube Live URL
# -----------------------
def get_youtube_live_url(youtube_url: str):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logging.error(f"yt-dlp error for {youtube_url}: {result.stderr.strip()}")
        return None
    except Exception:
        logging.exception("Exception while extracting YouTube live URL")
        return None

# -----------------------
# Refresh YouTube URLs
# -----------------------
def refresh_stream_urls():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        now = time.time()
        for name, url in YOUTUBE_STREAMS.items():
            if name not in last_update or now - last_update[name] > 60:
                direct_url = get_youtube_live_url(url)
                if direct_url:
                    CACHE[name] = direct_url
                    last_update[name] = now
                    logging.info(f"✅ Updated {name}")
                else:
                    logging.warning(f"❌ Failed to update {name}")
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Generate 360p HLS
# -----------------------
def generate_hls(url: str):
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-i", url,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", "500k",
            "-maxrate", "500k",
            "-bufsize", "1000k",
            "-vf", "scale=-2:360",
            "-c:a", "aac",
            "-b:a", "64k",
            "-f", "hls",
            "-hls_time", "4",
            "-hls_playlist_type", "event",
            "-"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=10**6,
    )
    try:
        for chunk in iter(lambda: process.stdout.read(4096), b""):
            yield chunk
    finally:
        process.terminate()
        process.wait()

# -----------------------
# Flask Routes
# -----------------------
@app.route("/")
def home():
    all_channels = list(TV_STREAMS.keys()) + list(YOUTUBE_STREAMS.keys())
    html = """<html>
<head>
<title>📺 TV & YouTube Live 360p HLS</title>
<style>
body { font-family: sans-serif; background:#111; color:#fff; padding:20px; }
a { color:#0f0; display:block; margin:10px 0; font-size:18px; text-decoration:none; }
</style>
</head>
<body>
<h2>📺 TV & YouTube Live 360p HLS</h2>
{% for key in channels %}
<a href="/watch/{{ key }}">▶ {{ key.replace('_',' ').title() }}</a>
{% endfor %}
</body></html>"""
    return render_template_string(html, channels=all_channels)

@app.route("/watch/<channel>")
def watch(channel):
    if channel not in TV_STREAMS and channel not in YOUTUBE_STREAMS:
        abort(404)
    html = f"""
<html><body style="background:#000; color:#fff; text-align:center;">
<h2>{channel.replace('_',' ').title()} (360p HLS)</h2>
<video controls autoplay style="width:95%; max-width:700px;">
<source src="/stream/{channel}" type="application/vnd.apple.mpegurl">
</video>
<p><a href='/'>⬅ Back</a></p>
</body></html>"""
    return html

@app.route("/stream/<channel>")
def stream(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        return "Channel not ready", 503
    return Response(generate_hls(url), mimetype="application/vnd.apple.mpegurl")

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)