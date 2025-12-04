#!/usr/bin/env python3
"""
Merged Flask app: YouTube Playlist Radio + TV (m3u8) + YouTube Live
Option A: Single server with 3 tabs on home page: Radio | TV | YouTube Live
"""

import os
import time
import random
import json
import threading
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from collections import deque
from flask import Flask, Response, render_template_string, abort, stream_with_context
import requests

# -----------------------
# Basic logging & Flask
# -----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# Paths & constants
# -----------------------
BASE_DIR = "/mnt/data"
os.makedirs(BASE_DIR, exist_ok=True)
LOG_PATH = os.path.join(BASE_DIR, "radio_tv.log")
COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")
PLAYLIST_CACHE_FILE = os.path.join(BASE_DIR, "playlist_cache.json")
RADIO_DOWNLOAD_DIR = os.path.join(BASE_DIR, "radio_cache")
os.makedirs(RADIO_DOWNLOAD_DIR, exist_ok=True)

handler = RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3)
logging.getLogger().addHandler(handler)

MAX_QUEUE = 128
REFRESH_INTERVAL = 1800  # seconds for playlist cache refresh (30 min)

# -----------------------
# ========== RADIO: YouTube Playlist Radio ==========
# -----------------------
PLAYLISTS = {
    "talent_ca": "https://youtube.com/playlist?list=PL5RD_h4gTSuQbCndwvolzeTDwZVGwCl53",
    # add more playlist name: url pairs here
}

STREAMS_RADIO = {}
CACHE_RADIO_LOCK = threading.Lock()

def load_cache_radio():
    if os.path.exists(PLAYLIST_CACHE_FILE):
        try:
            with open(PLAYLIST_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Error loading playlist cache: %s", e)
            return {}
    return {}

def save_cache_radio(data):
    try:
        with open(PLAYLIST_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error("Error saving playlist cache: %s", e)

CACHE_RADIO = load_cache_radio()

def load_playlist_ids_radio(name, force=False):
    now = time.time()
    with CACHE_RADIO_LOCK:
        cached = CACHE_RADIO.get(name, {})
        if not force and cached and now - cached.get("time", 0) < REFRESH_INTERVAL:
            return cached.get("ids", [])

    url = PLAYLISTS[name]
    try:
        logging.info(f"[radio:{name}] Refreshing playlist via yt-dlp...")
        cmd = ["yt-dlp", "--flat-playlist", "-J", url, "--cookies", COOKIES_PATH] if os.path.exists(COOKIES_PATH) else ["yt-dlp", "--flat-playlist", "-J", url]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        ids = [e["id"] for e in data.get("entries", []) if "id" in e][::-1]
        with CACHE_RADIO_LOCK:
            CACHE_RADIO[name] = {"ids": ids, "time": now}
            save_cache_radio(CACHE_RADIO)
        logging.info(f"[radio:{name}] Cached {len(ids)} videos.")
        return ids
    except Exception as e:
        logging.error(f"[radio:{name}] Playlist error: {e}")
        with CACHE_RADIO_LOCK:
            return CACHE_RADIO.get(name, {}).get("ids", [])

def stream_worker_radio(name):
    s = STREAMS_RADIO[name]
    while True:
        try:
            ids = s["IDS"]
            if not ids:
                ids = load_playlist_ids_radio(name, True)
                s["IDS"] = ids
            if not ids:
                logging.warning(f"[radio:{name}] No playlist ids found; sleeping 10s...")
                time.sleep(10)
                continue

            vid = ids[s["INDEX"] % len(ids)]
            s["INDEX"] += 1
            url = f"https://www.youtube.com/watch?v={vid}"
            logging.info(f"[radio:{name}] ▶️ {url}")

            cmd = (
                f'yt-dlp -f "bestaudio/best" --cookies "{COOKIES_PATH}" '
                f'--user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" '
                f'-o - --quiet --no-warnings "{url}"'
            ) if os.path.exists(COOKIES_PATH) else (
                f'yt-dlp -f "bestaudio/best" --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -o - --quiet --no-warnings "{url}"'
            )

            # Pipe through ffmpeg to produce consistent mp3 stream
            ffmpeg_cmd = 'ffmpeg -loglevel quiet -i pipe:0 -ac 1 -ar 44100 -b:a 64k -f mp3 pipe:1'
            proc = subprocess.Popen(f"{cmd} | {ffmpeg_cmd}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            # stream into QUEUE in chunks
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                # block if queue full
                while len(s["QUEUE"]) >= MAX_QUEUE:
                    time.sleep(0.05)
                s["QUEUE"].append(chunk)

            proc.wait()
            logging.info(f"[radio:{name}] ✅ Track completed.")
            time.sleep(2)
        except Exception as e:
            logging.error(f"[radio:{name}] Worker error: {e}")
            time.sleep(5)

# Radio endpoints (namespaced under /radio)
@app.route("/radio/")
def radio_index():
    playlists = list(PLAYLISTS.keys())
    html = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🎧 YouTube Radio</title>
<style>
body{background:#000;color:#0f0;font-family:Arial,Helvetica,sans-serif;text-align:center;margin:0;padding:12px}
a{display:block;color:#0f0;text-decoration:none;border:1px solid #0f0;padding:10px;margin:8px;border-radius:8px;font-size:18px}
a:hover{background:#0f0;color:#000}
</style></head><body>
<h2>🎶 YouTube Playlist Radio</h2>
{% for p in playlists %}
  <a href="/radio/listen/{{p}}">▶ {{p|capitalize}}</a>
  <a href="/radio/stream/{{p}}">🔊 Stream {{p|capitalize}}</a>
{% endfor %}
<p><a href="/">⬅ Back to main</a></p>
</body></html>"""
    return render_template_string(html, playlists=playlists)

@app.route("/radio/listen/<name>")
def listen_radio_download(name):
    if name not in STREAMS_RADIO:
        abort(404)
    s = STREAMS_RADIO[name]
    def gen():
        while True:
            if s["QUEUE"]:
                yield s["QUEUE"].popleft()
            else:
                time.sleep(0.05)
    headers = {"Content-Disposition": f"attachment; filename={name}.mp3"}
    return Response(stream_with_context(gen()), mimetype="audio/mpeg", headers=headers)

@app.route("/radio/stream/<name>")
def stream_audio_radio(name):
    if name not in STREAMS_RADIO:
        abort(404)
    s = STREAMS_RADIO[name]
    def gen():
        while True:
            if s["QUEUE"]:
                yield s["QUEUE"].popleft()
            else:
                time.sleep(0.05)
    return Response(stream_with_context(gen()), mimetype="audio/mpeg")

# Playlist mode control endpoints
PLAYLIST_ORDER = {name: "normal" for name in PLAYLISTS}  # current mode

def reorder_playlist(name, mode="normal"):
    with CACHE_RADIO_LOCK:
        if name not in CACHE_RADIO or "ids" not in CACHE_RADIO[name]:
            return
        ids = CACHE_RADIO[name]["ids"]
        if mode == "shuffle":
            random.shuffle(ids)
        elif mode == "reverse":
            ids = list(reversed(ids))
        CACHE_RADIO[name]["ids"] = ids
        CACHE_RADIO[name]["time"] = time.time()
        save_cache_radio(CACHE_RADIO)
        PLAYLIST_ORDER[name] = mode
        logging.info(f"[radio:{name}] Playlist set to {mode} mode with {len(ids)} videos.")

@app.route("/radio/mode/<name>/<mode>")
def set_playlist_mode(name, mode):
    if name not in PLAYLISTS:
        abort(404)
    if mode not in ["shuffle", "reverse", "normal"]:
        return f"❌ Invalid mode. Use /radio/mode/<name>/shuffle | reverse | normal"
    reorder_playlist(name, mode)
    return f"✅ {name} playlist set to {mode} mode."

@app.route("/radio/status")
def show_radio_status():
    html = "<h3>🎶 Playlist Modes</h3><ul>"
    for k, v in PLAYLIST_ORDER.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul><p><a href='/'>⬅ Back to main</a></p>"
    return html

# -----------------------
# ========== TV & YouTube Live ==========
# -----------------------

# TV direct m3u8 streams
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    # ... add more if desired
}

# YouTube Live channels (URLs or channel/live page links)
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "xylem_psc": "https://www.youtube.com/@XylemPSC/live",
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    # ... add more
}

# Channel logos for UI
CHANNEL_LOGOS = {
    "safari_tv": "https://i.imgur.com/dSOfYyh.png",
    "victers_tv": "https://i.imgur.com/kj4OEsb.png",
    "bloomberg_tv": "https://i.imgur.com/OuogLHx.png",
    "france_24": "https://upload.wikimedia.org/wikipedia/commons/c/c1/France_24_logo_%282013%29.svg",
    # default YouTube logo for YouTube entries
    **{k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
}

# Live cache and status
CACHE = {}
LIVE_STATUS = {}
CACHE_LOCK = threading.Lock()
COOKIES_FILE = COOKIES_PATH  # reuse same cookies path

def get_youtube_live_url(youtube_url: str):
    """
    Use yt-dlp to extract a direct url (HLS if available) for a yt live page.
    Returns URL string or None.
    """
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logging.debug("get_youtube_live_url error: %s", e)
    return None

def refresh_stream_urls():
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            with CACHE_LOCK:
                if direct_url:
                    CACHE[name] = direct_url
                    LIVE_STATUS[name] = True
                    logging.info(f"[live:{name}] live -> {direct_url}")
                else:
                    LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Main combined home page (3 tabs)
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    # only show youtube channels that are marked live (LIVE_STATUS True)
    youtube_live_available = [n for n, live in LIVE_STATUS.items() if live]
    # Also include youtube channels even if not live, but mark as offline - we choose to show live ones by default
    html = """
<html>
<head>
<title>📺 TV · 🎧 Radio · ▶ YouTube Live</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family:sans-serif; background:#111; color:#fff; margin:0; padding:0; }
h2 { text-align:center; margin:10px 0; }
.tabs { display:flex; justify-content:center; background:#000; padding:10px; }
.tab { padding:10px 20px; cursor:pointer; background:#222; color:#0ff; border-radius:10px; margin:0 5px; transition:0.2s; }
.tab.active { background:#0ff; color:#000; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(140px,1fr)); gap:12px; padding:10px; }
.card { background:#222; border-radius:10px; padding:10px; text-align:center; transition:0.2s; }
.card:hover { background:#333; }
.card img { width:100%; height:80px; object-fit:contain; margin-bottom:8px; }
.card span { font-size:14px; color:#0f0; display:block; margin-bottom:6px; }
.small { font-size:12px; color:#ccc; }
.hidden { display:none; }
a { color:#0ff; text-decoration:none; }
</style>
<script>
function showTab(tab){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.grid').forEach(g=>g.classList.add('hidden'));
  document.getElementById(tab).classList.remove('hidden');
  document.getElementById('tab_'+tab).classList.add('active');
}
window.onload=()=>showTab('radio');
</script>
</head>
<body>
<div class="tabs">
  <div class="tab active" id="tab_radio" onclick="showTab('radio')">🎧 Radio</div>
  <div class="tab" id="tab_tv" onclick="showTab('tv')">📺 TV</div>
  <div class="tab" id="tab_youtube" onclick="showTab('youtube')">▶ YouTube Live</div>
</div>

<div id="radio" class="grid">
  <!-- Radio cards -->
  {% for p in radio_list %}
  <div class="card">
    <img src="https://i.imgur.com/7yUvePI.png">
    <span>{{ p.replace('_',' ').title() }}</span>
    <a href="/radio/listen/{{p}}">▶ Download</a> |
    <a href="/radio/stream/{{p}}">🔊 Stream</a>
  </div>
  {% endfor %}
</div>

<div id="tv" class="grid hidden">
  {% for key in tv_channels %}
  <div class="card">
    <img src="{{ logos.get(key) }}">
    <span>{{ key.replace('_',' ').title() }}</span>
    <div class="small">
      <a href="/watch/{{ key }}">▶ Watch</a> |
      <a href="/audio/{{ key }}">🎵 Audio</a>
    </div>
  </div>
  {% endfor %}
</div>

<div id="youtube" class="grid hidden">
  {% for key in youtube_channels %}
  <div class="card">
    <img src="{{ logos.get(key) }}">
    <span>{{ key.replace('_',' ').title() }}</span>
    <div class="small">
      <a href="/watch/{{ key }}">▶ Watch</a> |
      <a href="/audio/{{ key }}">🎵 Audio</a>
    </div>
  </div>
  {% endfor %}
</div>

</body>
</html>
"""
    return render_template_string(
        html,
        radio_list=list(PLAYLISTS.keys()),
        tv_channels=tv_channels,
        youtube_channels=youtube_live_available,
        logos=CHANNEL_LOGOS
    )

# -----------------------
# Watch route (TV or YouTube-live)
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]
    all_channels = tv_channels + live_youtube
    if channel not in all_channels:
        abort(404)

    # choose video source URL for the player
    if channel in TV_STREAMS:
        video_url = TV_STREAMS[channel]
    else:
        # youtube live direct url from CACHE (HLS or mp4)
        video_url = CACHE.get(channel) or ""
    current_index = all_channels.index(channel)
    prev_channel = all_channels[(current_index - 1) % len(all_channels)]
    next_channel = all_channels[(current_index + 1) % len(all_channels)]

    html = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel.replace('_',' ').title()}</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
body {{ background:#000; color:#fff; text-align:center; margin:0; padding:10px; }}
video {{ width:95%; max-width:720px; height:auto; background:#000; border:1px solid #333; }}
a {{ color:#0f0; text-decoration:none; margin:10px; display:inline-block; font-size:18px; }}
</style>
<script>
document.addEventListener("DOMContentLoaded", function() {{
  const video = document.getElementById("player");
  const src = "{video_url}";
  if (!src) {{
    document.getElementById('msg').innerText = "Stream not ready.";
    return;
  }}
  if (video.canPlayType("application/vnd.apple.mpegurl")) {{
    video.src = src;
  }} else if (Hls.isSupported()) {{
    const hls = new Hls({{lowLatencyMode:true}});
    hls.loadSource(src);
    hls.attachMedia(video);
  }} else {{
    alert("⚠️ Browser cannot play HLS stream.");
  }}
}});
document.addEventListener("keydown", function(e) {{
  const v=document.getElementById("player");
  if(e.key==="4")window.location.href="/watch/{prev_channel}";
  if(e.key==="6")window.location.href="/watch/{next_channel}";
  if(e.key==="0")window.location.href="/";
  if(e.key==="5"&&v){{v.paused?v.play():v.pause();}}
  if(e.key==="9")window.location.reload();
}});
</script>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video id="player" controls autoplay playsinline></video>
<div id="msg" style="color:#f88;margin-top:8px;"></div>
<div style="margin-top:15px;">
  <a href="/">⬅ Home</a>
  <a href="/watch/{prev_channel}">⏮ Prev</a>
  <a href="/watch/{next_channel}">⏭ Next</a>
  <a href="/watch/{channel}" style="color:#0ff;">🔄 Reload</a>
</div>
</body>
</html>"""
    return html

# -----------------------
# Proxy for HLS content (for players that can't access remote)
# -----------------------
@app.route("/stream/<channel>")
def stream(channel):
    # For TV: use TV_STREAMS, for YouTube-live: CACHE
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return f"Error fetching stream: {e}", 502

    content_type = r.headers.get("Content-Type", "application/vnd.apple.mpegurl")
    return Response(r.content, content_type=content_type)

# -----------------------
# Audio-only endpoint for TV or YouTube-live
# -----------------------
@app.route("/audio/<channel>")
def audio_only(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    filename = f"{channel}.mp3"

    def generate():
        # Uses ffmpeg to convert remote stream to mp3 on the fly
        cmd = [
            "ffmpeg", "-i", url,
            "-vn",               # no video
            "-ac", "1",          # mono
            "-b:a", "40k",       # 40kbps
            "-f", "mp3",
            "pipe:1"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                data = proc.stdout.read(1024)
                if not data:
                    break
                yield data
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    return Response(generate(), mimetype="audio/mpeg", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

# -----------------------
# -----------------------
# Startup: Initialize radio STREAMS and start radio workers
# -----------------------
def start_radio_workers():
    for pname in PLAYLISTS:
        STREAMS_RADIO[pname] = {
            "IDS": load_playlist_ids_radio(pname),
            "INDEX": 0,
            "QUEUE": deque(),
            "LAST_REFRESH": time.time(),
        }
        t = threading.Thread(target=stream_worker_radio, args=(pname,), daemon=True)
        t.start()
        logging.info(f"[radio:{pname}] worker started.")

# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    logging.info("Starting merged server: Radio + TV + YouTube Live")
    start_radio_workers()
    # refresh_stream_urls thread already started earlier when module imported; ensure it's running
    app.run(host="0.0.0.0", port=8000, debug=False)