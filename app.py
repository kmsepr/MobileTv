import time
import threading
import logging
import requests
from flask import Flask, Response, render_template_string, abort
import subprocess, os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (raw m3u8)
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
LIVE_STATUS = {}  # Tracks which YouTube streams are currently live
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube Live URL (raw HLS)
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
        logging.info(f"Not live yet: {youtube_url}")
        return None
    except Exception:
        logging.exception("Exception while extracting YouTube live URL")
        return None

# -----------------------
# Refresh YouTube URLs
# -----------------------
def refresh_stream_urls():
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
                logging.info(f"✅ Live: {name}")
            else:
                LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Proxy raw HLS
# -----------------------
def stream_proxy(url: str):
    try:
        with requests.get(url, stream=True, timeout=10) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk
    except Exception as e:
        logging.error(f"Error proxying stream {url}: {e}")
        yield b""

# -----------------------
# Flask Routes
# -----------------------
@app.route("/")
def home():
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]
    all_channels = list(TV_STREAMS.keys()) + live_youtube
    html = """<html>
<head>
<title>📺 TV & YouTube Live Raw HLS</title>
<style>
body { font-family: sans-serif; background:#111; color:#fff; padding:20px; }
a { color:#0f0; display:block; margin:10px 0; font-size:18px; text-decoration:none; }
</style>
</head>
<body>
<h2>📺 TV & YouTube Live Raw HLS</h2>
{% for key in channels %}
<a href="/watch/{{ key }}">▶ {{ key.replace('_',' ').title() }}</a>
{% endfor %}
</body></html>"""
    return render_template_string(html, channels=all_channels)

@app.route("/watch/<channel>")
def watch(channel):
    if channel not in TV_STREAMS and channel not in CACHE:
        abort(404)
    html = f"""
<html><body style="background:#000; color:#fff; text-align:center;">
<h2>{channel.replace('_',' ').title()} (Raw HLS)</h2>
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
    return Response(stream_proxy(url), mimetype="application/vnd.apple.mpegurl")

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)