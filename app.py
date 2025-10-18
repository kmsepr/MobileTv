import time
import threading
import logging
import os
import subprocess
import re
import requests

from flask import Flask, Response, render_template_string, abort, stream_with_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# TV streams (direct m3u8)
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    # ... (other entries) ...
}

# YouTube live channels
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    # ... (other entries) ...
}

CHANNEL_LOGOS = {
    "safari_tv": "https://i.imgur.com/dSOfYyh.png",
    # ... (other entries) ...
    **{k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
}

CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

def get_youtube_live_url(youtube_url: str):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd[1:1] = ["--cookies", COOKIES_FILE]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logging.error(f"Error getting YouTube URL for {youtube_url}: {e}")
    return None

def refresh_stream_urls():
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
            else:
                if name not in CACHE:
                    LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

def generate_audio_stream(source_url, channel_name):
    """Generate an MP3 audio stream (40 kbps mono) from the given source."""
    logging.info(f"Starting FFmpeg for {channel_name} audio stream.")
    ffmpeg_command = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",
        "-timeout", "5000000",
        "-user_agent", "Mozilla/5.0",
        "-i", source_url,
        "-vn",
        "-ac", "1",
        "-b:a", "40k",
        "-bufsize", "1M",
        "-f", "mp3",
        "-"
    ]
    try:
        process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for chunk in iter(lambda: process.stdout.read(4096), b''):
            if not chunk:
                break
            yield chunk
        process.wait()
        stderr_output = process.stderr.read().decode(errors="ignore")
        if process.returncode != 0:
            logging.error(f"FFmpeg failed for {channel_name}: {stderr_output}")
        else:
            logging.info(f"FFmpeg exited normally for {channel_name}.")
    except FileNotFoundError:
        logging.critical("FFmpeg not found in PATH.")
        raise
    except Exception as e:
        logging.error(f"Error streaming {channel_name}: {e}")

@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [n for n, live in LIVE_STATUS.items() if live]
    html = """
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📺 Live Channels</title>
<style>
body{font-family:sans-serif;background:#111;color:#fff;margin:0;padding:20px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px;}
.card{background:#222;border-radius:10px;padding:10px;text-align:center;}
.card img{width:100%;height:80px;object-fit:contain;}
a{color:#0f0;text-decoration:none;}
</style>
</head>
<body>
<h2>📺 TV Channels</h2>
<div class="grid">
{% for key in tv_channels %}
  <div class="card">
    <a href="/watch/{{ key }}"><img src="{{ logos.get(key) }}"><br>{{ key.replace('_',' ').title() }}</a><br>
    <a href="/audio/{{ key }}">🎧 Audio</a>
  </div>
{% endfor %}
</div>
<h2>▶ YouTube Live</h2>
<div class="grid">
{% for key in youtube_channels %}
  <div class="card">
    <a href="/watch/{{ key }}"><img src="{{ logos.get(key) }}"><br>{{ key.replace('_',' ').title() }}</a><br>
    <a href="/audio/{{ key }}">🎧 Audio</a>
  </div>
{% endfor %}
</div>
</body>
</html>
    """
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

@app.route("/watch/<channel>")
def watch(channel):
    all_channels = list(TV_STREAMS.keys()) + [n for n, live in LIVE_STATUS.items() if live]
    if channel not in all_channels:
        abort(404)
    src = TV_STREAMS.get(channel, f"/stream/{channel}")
    html = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel.replace('_',' ').title()}</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
body{{background:#000;color:#fff;text-align:center;margin:0;padding:10px;}}
video{{width:95%;max-width:720px;height:auto;background:#000;border:1px solid #333;}}
a{{color:#0f0;text-decoration:none;margin:10px;display:inline-block;font-size:18px;}}
</style>
<script>
document.addEventListener("DOMContentLoaded",function(){{
  const video = document.getElementById("player");
  const src = "{src}";
  if(video.canPlayType("application/vnd.apple.mpegurl")){ video.src = src; }
  else if(Hls.isSupported()){ const hls = new Hls({{lowLatencyMode:true}}); hls.loadSource(src); hls.attachMedia(video); }
  else { alert("⚠️ Browser cannot play HLS stream."); }
}});
</script>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video id="player" controls autoplay playsinline></video>
<div style="margin-top:15px;">
  <a href="/">⬅ Home</a>
  <a href="/audio/{channel}" style="color:#f0;">🎧 Audio</a>
</div>
</body>
</html>
    """
    return html

@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503
    try:
        r = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        return Response(stream_with_context(r.iter_content(4096)), content_type=r.headers.get("Content-Type", "application/vnd.apple.mpegurl"))
    except Exception as e:
        logging.error(f"Proxy error: {e}")
        return f"Error fetching stream: {e}", 502

@app.route("/audio/<channel>")
def audio_stream(channel):
    if channel in TV_STREAMS:
        source_url = TV_STREAMS[channel]
    elif channel in YOUTUBE_STREAMS:
        source_url = CACHE.get(channel)
        if not source_url:
            if LIVE_STATUS.get(channel, False) is False:
                return f"Channel '{channel}' is offline.", 503
            return f"Channel '{channel}' URL not cached yet. Try again.", 503
    else:
        abort(404)

    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', channel)
    return Response(
        stream_with_context(generate_audio_stream(source_url, channel)),
        mimetype="audio/mpeg",
        headers={
            "Content-Disposition": f"inline; filename={safe_name}.mp3"
        }
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)