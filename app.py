import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort
import subprocess, os, requests, random

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (direct m3u8)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/safari_tv/playlist.m3u8",
    "asianet_news": "https://vidcdn.vidgyor.com/asianet-origin/liveabr/asianet-origin/live1/chunks.m3u8",
    "media_one": "https://live.wmncdn.net/mediaone/live.stream/index.m3u8",
}

# -----------------------
# YouTube Streams
# -----------------------
YOUTUBE_STREAMS = {
    "manorama_news": "https://www.youtube.com/watch?v=yG9PjYWZZZg",
    "reporter_tv": "https://www.youtube.com/watch?v=84TO2Cc8vJw",
    "janam_tv": "https://www.youtube.com/watch?v=LvV2-9h3lEo",
}

# Cache live status of YouTube streams
LIVE_STATUS = {key: False for key in YOUTUBE_STREAMS.keys()}

def check_live_status():
    while True:
        for key, url in YOUTUBE_STREAMS.items():
            try:
                r = requests.get(url, timeout=10)
                LIVE_STATUS[key] = "live" in r.text.lower()
                logging.info(f"Checked {key}: {LIVE_STATUS[key]}")
            except Exception as e:
                logging.error(f"Error checking {key}: {e}")
                LIVE_STATUS[key] = False
        time.sleep(300)  # check every 5 minutes

threading.Thread(target=check_live_status, daemon=True).start()

# -----------------------
# Homepage Grid (NO LOGOS)
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]
    all_channels = tv_channels + live_youtube

    html = """
<html>
<head>
<title>📺 TV & YouTube Live</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: sans-serif; background:#111; color:#fff; margin:0; padding:20px; }
h2 { font-size:28px; text-align:center; margin-bottom:20px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); gap:15px; }
.card { background:#222; border-radius:10px; padding:20px; text-align:center; font-size:14px; }
.card span { display:block; font-size:15px; color:#0f0; }
.card a { text-decoration:none; color:inherit; display:block; }
.card:hover { background:#333; }
</style>
<script>
document.addEventListener("keydown", function(e) {
    let links = document.querySelectorAll("a[data-index]");
    if (!isNaN(e.key)) {
        if (e.key === "0") {
            let rand = Math.floor(Math.random() * links.length);
            window.location.href = links[rand].href;
        } else {
            let index = parseInt(e.key) - 1;
            if (index >= 0 && index < links.length) {
                window.location.href = links[index].href;
            }
        }
    }
});
</script>
</head>
<body>
<h2>📺 TV & YouTube Live</h2>
<div class="grid">
{% for key in channels %}
<div class="card">
  <a href="/watch/{{ key }}" data-index="{{ loop.index0 }}">
    <span>[{{ loop.index }}] {{ key.replace('_',' ').title() }}</span>
  </a>
</div>
{% endfor %}
</div>
</body>
</html>"""
    return render_template_string(html, channels=all_channels)

# -----------------------
# Stream Proxy
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    if channel in TV_STREAMS:
        url = TV_STREAMS[channel]
    elif channel in YOUTUBE_STREAMS and LIVE_STATUS.get(channel, False):
        url = YOUTUBE_STREAMS[channel]
    else:
        abort(404)

    html = f"""
<html>
<head>
<title>{channel}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>body {{ margin:0; background:#000; }}</style>
</head>
<body>
<iframe width="100%" height="100%" src="{url}" frameborder="0" allowfullscreen></iframe>
</body>
</html>"""
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)