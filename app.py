#!/usr/bin/env python3
import time
import threading
import logging
import subprocess
import os
import requests

from flask import Flask, Response, render_template_string, abort

# ============================================================
# BASIC SETUP
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)

COOKIES_FILE = "/mnt/data/cookies.txt"
CACHE = {}
LIVE_STATUS = {}

# ============================================================
# TV STREAMS (DIRECT HLS)
# ============================================================
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "bloomberg_tv": "https://bloomberg-bloomberg-3-br.samsung.wurl.tv/manifest/playlist.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
    "aqsa_tv": "http://167.172.161.13/hls/feedspare/6udfi7v8a3eof6nlps6e9ovfrs65c7l7.m3u8",
}

# ============================================================
# YOUTUBE LIVE CHANNELS
# ============================================================
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
}

# ============================================================
# YOUTUBE → HLS URL
# ============================================================
def get_youtube_live_url(url: str):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception as e:
        logging.error(e)

    return None

# ============================================================
# BACKGROUND REFRESH
# ============================================================
def refresh_youtube():
    while True:
        logging.info("🔄 Refreshing YouTube streams")
        for name, url in YOUTUBE_STREAMS.items():
            direct = get_youtube_live_url(url)
            if direct:
                CACHE[name] = direct
                LIVE_STATUS[name] = True
            else:
                LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_youtube, daemon=True).start()

# ============================================================
# HOME
# ============================================================
@app.route("/")
def home():
    tv = list(TV_STREAMS.keys())
    yt = [k for k, v in LIVE_STATUS.items() if v]

    html = """
    <h2>📺 TV</h2>
    {% for c in tv %}
      <a href="/watch/{{c}}">{{c}}</a> |
      <a href="/audio/{{c}}">🎵</a><br>
    {% endfor %}

    <h2>▶ YouTube Live</h2>
    {% for c in yt %}
      <a href="/watch/{{c}}">{{c}}</a> |
      <a href="/audio/{{c}}">🎵</a><br>
    {% endfor %}
    """
    return render_template_string(html, tv=tv, yt=yt)

# ============================================================
# WATCH (VIDEO)
# ============================================================
@app.route("/watch/<channel>")
def watch(channel):
    if channel in TV_STREAMS:
        src = TV_STREAMS[channel]
    elif channel in CACHE:
        src = f"/stream/{channel}"
    else:
        abort(404)

    return f"""
    <html>
    <head>
      <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    </head>
    <body style="background:#000;color:#fff">
      <h3>{channel}</h3>
      <video id="v" controls autoplay playsinline style="width:95%"></video>
      <script>
        var v=document.getElementById('v');
        var src="{src}";
        if(v.canPlayType('application/vnd.apple.mpegurl')){
            v.src=src;
        }else if(Hls.isSupported()){
            var h=new Hls();
            h.loadSource(src);
            h.attachMedia(v);
        }
      </script>
    </body>
    </html>
    """

# ============================================================
# TRUE STREAM PROXY (FIXED)
# ============================================================
@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Not ready", 503

    def generate():
        with requests.get(url, stream=True, timeout=10) as r:
            r.raise_for_status()
            for chunk in r.iter_content(8192):
                if chunk:
                    yield chunk

    return Response(
        generate(),
        mimetype="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-cache"}
    )

# ============================================================
# AUDIO ONLY (MP3 – STABLE)
# ============================================================
@app.route("/audio/<channel>")
def audio(channel):

    if channel in YOUTUBE_STREAMS:
        url = get_youtube_live_url(YOUTUBE_STREAMS[channel])
    else:
        url = TV_STREAMS.get(channel)

    if not url:
        return "Stream unavailable", 503

    def generate():
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-fflags", "+genpts+nobuffer",
            "-flags", "low_delay",
            "-i", url,
            "-vn",
            "-ac", "1",
            "-ar", "22050",
            "-c:a", "libmp3lame",
            "-b:a", "40k",
            "-f", "mp3",
            "pipe:1"
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0
        )

        try:
            while True:
                data = proc.stdout.read(2048)
                if not data:
                    break
                yield data
        finally:
            proc.terminate()

    return Response(
        generate(),
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)