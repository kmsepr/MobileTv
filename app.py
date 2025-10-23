import os
import time
import json
import threading
import logging
import subprocess
import random
from collections import deque
from flask import Flask, Response, render_template_string, abort, stream_with_context, request, redirect, url_for
from logging.handlers import RotatingFileHandler

# -----------------------------
# CONFIG & LOGGING
# -----------------------------
LOG_PATH = "/mnt/data/unified_radio.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

handler = RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), handler]
)

app = Flask(__name__)

COOKIES_FILE = "/mnt/data/cookies.txt"
CACHE_FILE = "/mnt/data/cache.json"
PLAYLISTS_FILE = "/mnt/data/playlists.json"
MAX_QUEUE_SIZE = 100

# -----------------------------
# TV HLS STREAMS
# -----------------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/2.m3u8",
}

# -----------------------------
# YouTube Live Channels
# -----------------------------
YOUTUBE_LIVE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
}

# -----------------------------
# Playlist Radio
# -----------------------------
def load_playlists():
    if os.path.exists(PLAYLISTS_FILE):
        try:
            with open(PLAYLISTS_FILE, "r") as f:
                data = json.load(f)
                return data.get("playlists", {}), set(data.get("shuffle", []))
        except Exception as e:
            logging.error(f"Failed to load playlists: {e}")
    return {
        "Malayalam": "https://youtube.com/playlist?list=PLs0evDzPiKwAyJDAbmMOg44iuNLPaI4nn",
        "Hindi": "https://youtube.com/playlist?list=PLlXSv-ic4-yJj2djMawc8XqqtCn1BVAc2",
    }, {"Malayalam", "Hindi"}

def save_playlists():
    try:
        with open(PLAYLISTS_FILE, "w") as f:
            json.dump({"playlists": PLAYLISTS, "shuffle": list(SHUFFLE_PLAYLISTS)}, f)
    except Exception as e:
        logging.error(f"Failed to save playlists: {e}")

PLAYLISTS, SHUFFLE_PLAYLISTS = load_playlists()
STREAMS = {}
CACHE = {}
LIVE_CACHE = {}
LIVE_STATUS = {}

# -----------------------------
# Load/Save Cache
# -----------------------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load cache: {e}")
    return {}

def save_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(CACHE, f)
    except Exception as e:
        logging.error(f"Failed to save cache: {e}")

CACHE = load_cache()

# -----------------------------
# HTML TEMPLATES
# -----------------------------
HOME_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>📺 Unified TV & Radio</title>
<style>
body { font-family: sans-serif; background: #000; color: #fff; text-align: center; }
h2 { color: #0ff; }
.tab { display: inline-block; background: #111; color: #0ff; padding: 10px 20px; margin: 5px; border-radius: 10px; cursor: pointer; }
.tab.active { background: #0ff; color: #000; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; padding: 10px; }
.card { background: #111; border-radius: 15px; padding: 20px 10px; }
.card a { display: block; margin: 6px 0; padding: 8px 0; background: #0ff; color: #000; border-radius: 8px; text-decoration: none; font-weight: bold; }
a#addbtn { display: block; background: #0f0; color: #000; margin: 20px auto; padding: 10px; border-radius: 10px; width: 200px; font-weight: bold; text-decoration: none; }
.hidden { display: none; }
</style>
<script>
function showTab(tab){
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.grid').forEach(g=>g.classList.add('hidden'));
    document.getElementById(tab).classList.remove('hidden');
    document.getElementById('tab_'+tab).classList.add('active');
}
window.onload=()=>showTab('tv');
</script>
</head>
<body>
<h2>📺 Unified TV & YouTube Radio</h2>
<div>
    <div class="tab" id="tab_tv" onclick="showTab('tv')">📺 TV</div>
    <div class="tab" id="tab_live" onclick="showTab('live')">▶ YouTube Live</div>
    <div class="tab" id="tab_playlists" onclick="showTab('playlists')">🎵 Playlists</div>
</div>
<div id="tv" class="grid">
{% for key in tv_channels %}
<div class="card">
  <b>{{key.replace('_',' ').title()}}</b><br>
  <a href="/watch/{{key}}">▶ Watch</a>
  <a href="/audio/{{key}}">🎵 Audio</a>
</div>
{% endfor %}
</div>
<div id="live" class="grid hidden">
{% for key in live_channels %}
<div class="card">
  <b>{{key.replace('_',' ').title()}}</b><br>
  <a href="/watch/{{key}}">▶ Watch</a>
  <a href="/audio/{{key}}">🎵 Audio</a>
</div>
{% endfor %}
</div>
<div id="playlists" class="grid hidden">
{% for name in playlists %}
<div class="card">
  <b>{{name}}</b><br>
  <a href="/listen/{{name}}">▶ Listen</a>
  <a href="/delete/{{name}}" style="background:#f33;color:#fff;">🗑 Delete</a>
</div>
{% endfor %}
</div>
<a id="addbtn" href="/add_playlist_form">➕ Add Playlist</a>
</body>
</html>
"""

PLAYER_HTML = """
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{name}} Radio</title></head>
<body style="background:#000;color:#0f0;text-align:center;">
<h3>🎶 {{name}} Radio</h3>
<audio controls autoplay style="width:95%;max-width:500px;margin:20px auto;display:block;">
  <source src="/stream/{{name}}" type="audio/mpeg">
</audio>
<p>🎵 Playlist: <a href="{{playlist_url}}" target="_blank">{{playlist_url}}</a></p>
<a href="/" style="color:#0ff;">⬅ Home</a>
</body></html>
"""

# -----------------------------
# YouTube HLS Fetch
# -----------------------------
def get_youtube_hls(youtube_url):
    try:
        cmd = [
            "yt-dlp", "--geo-bypass", "--no-warnings", "--retries", "3",
            "-f", "best[height<=360]", "-g", youtube_url
        ]
        if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
            cmd.extend(["--cookies", COOKIES_FILE])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            logging.warning(f"[HLS] Failed for {youtube_url}: {result.stderr[:100]}")
    except subprocess.TimeoutExpired:
        logging.warning(f"[HLS] Timeout fetching {youtube_url}")
    except Exception as e:
        logging.error(f"[HLS] Error fetching {youtube_url}: {e}")
    return None

def refresh_youtube_live():
    while True:
        for name, url in YOUTUBE_LIVE_STREAMS.items():
            hls = get_youtube_hls(url)
            if hls:
                LIVE_CACHE[name] = hls
                LIVE_STATUS[name] = True
            else:
                LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_youtube_live, daemon=True).start()

# -----------------------------
# Playlist IDs
# -----------------------------
def load_playlist_ids(name, force=False):
    now = time.time()
    cached = CACHE.get(name, {})
    if not force and cached and now - cached.get("time", 0) < 1800:
        return cached["ids"]
    url = PLAYLISTS[name]
    try:
        result = subprocess.run(
            ["yt-dlp", "--geo-bypass", "--flat-playlist", "--no-warnings", "--retries", "3", "-J", url, "--cookies", COOKIES_FILE],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, timeout=60
        )
        data = json.loads(result.stdout)
        ids = [e["id"] for e in data.get("entries", []) if not e.get("private")]
        if name in SHUFFLE_PLAYLISTS:
            random.shuffle(ids)
        CACHE[name] = {"ids": ids, "time": now}
        save_cache()
        return ids
    except Exception as e:
        logging.warning(f"[{name}] Playlist load failed: {e}")
        return cached.get("ids", [])

# -----------------------------
# STREAM WORKER
# -----------------------------
def stream_worker(name):
    stream = STREAMS[name]
    failed_videos = set()
    shuffle_enabled = name in SHUFFLE_PLAYLISTS

    while True:
        try:
            if not stream["VIDEO_IDS"]:
                logging.info(f"[{name}] Playlist empty, reloading...")
                stream["VIDEO_IDS"] = load_playlist_ids(name, force=True)
                failed_videos.clear()
                stream["INDEX"] = 0
                continue

            if time.time() - stream["LAST_REFRESH"] > 1800:
                logging.info(f"[{name}] Refreshing playlist...")
                stream["VIDEO_IDS"] = load_playlist_ids(name, force=True)
                stream["LAST_REFRESH"] = time.time()

            if shuffle_enabled:
                available = [v for v in stream["VIDEO_IDS"] if v not in failed_videos]
                if not available:
                    failed_videos.clear()
                    available = stream["VIDEO_IDS"]
                vid = random.choice(available)
            else:
                vid = stream["VIDEO_IDS"][stream["INDEX"] % len(stream["VIDEO_IDS"])]
                stream["INDEX"] += 1

            url = f"https://www.youtube.com/watch?v={vid}"
            logging.info(f"[{name}] ▶️ Preparing: {url}")

            cmd = [
                "yt-dlp", "--geo-bypass", "--no-warnings", "--retries", "3",
                "-f", "bestaudio[ext=m4a]/bestaudio", "--cookies", COOKIES_FILE, "-g", url
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
            if result.returncode != 0 or not result.stdout.strip():
                logging.warning(f"[{name}] Failed to get audio URL for {vid}: {result.stderr[:100]}")
                failed_videos.add(vid)
                continue

            stream["CURRENT_AUDIO_URL"] = result.stdout.strip()

            while True:
                if stream.get("SKIP_CURRENT"):
                    stream["SKIP_CURRENT"] = False
                    break
                time.sleep(1)

        except Exception as e:
            logging.error(f"[{name}] Worker error: {e}", exc_info=True)
            time.sleep(5)

# -----------------------------
# STREAM ROUTE
# -----------------------------
@app.route("/stream/<name>")
def stream_audio(name):
    if name not in STREAMS:
        abort(404)
    stream = STREAMS[name]
    if not stream.get("CURRENT_AUDIO_URL"):
        return "Stream not ready yet", 503

    cmd = f'ffmpeg -re -i "{stream["CURRENT_AUDIO_URL"]}" -b:a 40k -ac 1 -f mp3 pipe:1 -loglevel quiet'
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

    def generate():
        try:
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.kill()

    return Response(stream_with_context(generate()), mimetype="audio/mpeg")

# -----------------------------
# FLASK ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template_string(HOME_HTML, tv_channels=list(TV_STREAMS.keys()), live_channels=[n for n, live in LIVE_STATUS.items() if live], playlists=PLAYLISTS.keys())

@app.route("/listen/<name>")
def listen(name):
    if name not in PLAYLISTS:
        abort(404)
    return render_template_string(PLAYER_HTML, name=name, playlist_url=PLAYLISTS[name])

@app.route("/add_playlist_form")
def add_playlist_form():
    return """
    <html><body style='background:#000;color:#0f0;text-align:center;'>
    <h3>Add Playlist</h3>
    <form action='/add_playlist' method='post'>
    Name: <input type='text' name='name' required><br>
    URL: <input type='url' name='url' required><br>
    <label><input type='checkbox' name='shuffle'> Shuffle</label><br>
    <button type='submit'>Add</button></form>
    <a href='/'>⬅ Home</a></body></html>
    """

@app.route("/add_playlist", methods=["POST"])
def add_playlist():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    if not name or not url:
        abort(400, "Name and URL required")

    import re
    match = re.search(r"(?:list=)([A-Za-z0-9_-]+)", url)
    if not match:
        abort(400, "Invalid YouTube playlist URL")

    url = f"https://www.youtube.com/playlist?list={match.group(1)}"
    PLAYLISTS[name] = url
    if request.form.get("shuffle"):
        SHUFFLE_PLAYLISTS.add(name)
    save_playlists()

    video_ids = load_playlist_ids(name)
    STREAMS[name] = {"VIDEO_IDS": video_ids, "INDEX": 0, "LOCK": threading.Lock(), "LAST_REFRESH": time.time(), "CURRENT_AUDIO_URL": None, "SKIP_CURRENT": False}
    threading.Thread(target=stream_worker, args=(name,), daemon=True).start()
    return redirect(url_for("home"))

@app.route("/delete/<name>")
def delete_playlist(name):
    if name not in PLAYLISTS:
        abort(404)
    STREAMS.pop(name, None)
    PLAYLISTS.pop(name, None)
    SHUFFLE_PLAYLISTS.discard(name)
    CACHE.pop(name, None)
    save_cache()
    save_playlists()
    return redirect(url_for("home"))

@app.route("/watch/<channel>")
def watch(channel):
    url = TV_STREAMS.get(channel) or LIVE_CACHE.get(channel)
    if not url:
        abort(404)
    return f"""
    <html><head><title>{channel}</title><script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script></head>
    <body style='background:#000;color:#fff;text-align:center;'>
    <h3>{channel}</h3><video id='player' controls autoplay style='width:95%;max-width:720px;'></video>
    <script>
    const video=document.getElementById('player');
    if(Hls.isSupported()){{const hls=new Hls();hls.loadSource("{url}");hls.attachMedia(video);}}
    else{{video.src="{url}";video.play();}}
    </script><a href='/'>⬅ Home</a></body></html>
    """

@app.route("/audio/<channel>")
def audio_only(channel):
    url = TV_STREAMS.get(channel) or LIVE_CACHE.get(channel)
    if not url:
        abort(404)
    cmd = f'ffmpeg -i "{url}" -b:a 40k -ac 1 -f mp3 pipe:1 -loglevel quiet'
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    def generate():
        while True:
            data = proc.stdout.read(4096)
            if not data:
                break
            yield data
    return Response(stream_with_context(generate()), mimetype="audio/mpeg")

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    DEFAULT_PLAYLISTS = {
        "Malayalam": "https://youtube.com/playlist?list=PLs0evDzPiKwAyJDAbmMOg44iuNLPaI4nn",
        "Hindi": "https://youtube.com/playlist?list=PLlXSv-ic4-yJj2djMawc8XqqtCn1BVAc2"
    }

    for name, url in DEFAULT_PLAYLISTS.items():
        if name not in PLAYLISTS:
            PLAYLISTS[name] = url
            SHUFFLE_PLAYLISTS.add(name)
    save_playlists()

    for name in PLAYLISTS:
        STREAMS[name] = {
            "VIDEO_IDS": load_playlist_ids(name),
            "INDEX": 0,
            "LOCK": threading.Lock(),
            "LAST_REFRESH": time.time(),
            "CURRENT_AUDIO_URL": None,
            "SKIP_CURRENT": False
        }
        threading.Thread(target=stream_worker, args=(name,), daemon=True).start()

    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
