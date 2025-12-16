import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort, send_from_directory
import subprocess, os, shutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (direct m3u8)
# -----------------------
TV_STREAMS = {
    "kairali_we": "https://cdn-3.pishow.tv/live/1530/master.m3u8",
    "amrita_tv": "https://ddash74r36xqp.cloudfront.net/master.m3u8",
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "bloomberg_tv": "https://bloomberg.com/media-manifest/streams/us.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
    "aqsa_tv": "http://167.172.161.13/hls/feedspare/6udfi7v8a3eof6nlps6e9ovfrs65c7l7.m3u8",
    "mult": "http://stv.mediacdn.ru/live/cdn/mult/playlist.m3u8",
    "yemen_today": "https://video.yementdy.tv/hls/yementoday.m3u8",
    "yemen_shabab": "https://starmenajo.com/hls/yemenshabab/index.m3u8",
}

# -----------------------
# YouTube Live Channels
# -----------------------
YOUTUBE_STREAMS = {
    "asianet_news": "https://www.youtube.com/@asianetnews/live",
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
}

# -----------------------
# Logos
# -----------------------
CHANNEL_LOGOS = {
    "amrita_tv": "https://i.imgur.com/WdSjlPl.png",
    "kairali_we": "https://i.imgur.com/zXpROBj.png",
    "safari_tv": "https://i.imgur.com/dSOfYyh.png",
    "victers_tv": "https://i.imgur.com/kj4OEsb.png",
    "bloomberg_tv": "https://i.imgur.com/OuogLHx.png",
    "france_24": "https://upload.wikimedia.org/wikipedia/commons/c/c1/France_24_logo_%282013%29.svg",
    **{k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
}

CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"
LOW_HLS_DIR = "/tmp/lowhls"

os.makedirs(LOW_HLS_DIR, exist_ok=True)

# -----------------------
# Extract YouTube HLS URL
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
    except Exception:
        pass
    return None

# -----------------------
# Background refresh YouTube URLs
# -----------------------
def refresh_stream_urls():
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
            else:
                LIVE_STATUS[name] = False
        time.sleep(600)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Launch low-res HLS FFmpeg
# -----------------------
def launch_low_hls(channel, src_url):
    channel_dir = os.path.join(LOW_HLS_DIR, channel)
    os.makedirs(channel_dir, exist_ok=True)
    playlist_path = os.path.join(channel_dir, "index.m3u8")

    # Skip if already running
    if getattr(launch_low_hls, f"{channel}_proc", None):
        return

    cmd = [
        "ffmpeg",
        "-i", src_url,
        "-vf", "scale=160:90",
        "-r", "8",
        "-b:v", "30k",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-ac", "1",
        "-ar", "22050",
        "-b:a", "10k",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "3",
        "-hls_flags", "delete_segments+omit_endlist",
        os.path.join(channel_dir, "index.m3u8")
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    setattr(launch_low_hls, f"{channel}_proc", proc)
    logging.info(f"🚀 Low-res HLS launched for {channel}")

# -----------------------
# Home Page
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [n for n, live in LIVE_STATUS.items() if live]

    html = """
<html>
<head>
<title>📺 TV & YouTube Live</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family:sans-serif; background:#111; color:#fff; margin:0; padding:0; }
h2 { text-align:center; margin:10px 0; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); gap:12px; padding:10px; }
.card { background:#222; border-radius:10px; padding:10px; text-align:center; }
.card img { width:100%; height:80px; object-fit:contain; margin-bottom:8px; }
.btns { display:flex; justify-content:center; gap:12px; margin-top:8px; }
.iconbtn { font-size:28px; background:#111; padding:6px 12px; border-radius:10px; color:#0ff; text-decoration:none; }
</style>
</head>
<body>
<h2>📺 TV & YouTube Live</h2>
<div class="grid">
{% for key in tv_channels %}
<div class="card">
    <img src="{{ logos.get(key) }}">
    <span>{{ key.replace('_',' ').title() }}</span>
    <div class="btns">
        <a class="iconbtn" href="/watch/{{ key }}">▶</a>
        <a class="iconbtn" href="/audio/{{ key }}">🎵</a>
        <a class="iconbtn" href="/lowvideo/{{ key }}">🔽</a>
    </div>
</div>
{% endfor %}
{% for key in youtube_channels %}
<div class="card">
    <img src="{{ logos.get(key) }}">
    <span>{{ key.replace('_',' ').title() }}</span>
    <div class="btns">
        <a class="iconbtn" href="/watch/{{ key }}">▶</a>
        <a class="iconbtn" href="/audio/{{ key }}">🎵</a>
        <a class="iconbtn" href="/lowvideo/{{ key }}">🔽</a>
    </div>
</div>
{% endfor %}
</div>
</body>
</html>
"""
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

# -----------------------
# Watch normal HLS
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        abort(404)
    html = f"""
<html>
<head>
<title>{channel}</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
</head>
<body>
<h2>{channel}</h2>
<video id="player" controls autoplay playsinline style="width:95%; max-width:720px;"></video>
<script>
const video=document.getElementById('player');
const src="{url}";
if(Hls.isSupported()){{const hls=new Hls(); hls.loadSource(src); hls.attachMedia(video);}}
else{{video.src=src;}}
</script>
</body>
</html>
"""
    return html

# -----------------------
# Audio-only FFmpeg
# -----------------------
@app.route("/audio/<channel>")
def audio_only(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    def generate():
        cmd = [
            "ffmpeg", "-re", "-i", url,
            "-vn", "-ac", "1", "-ar", "44100", "-b:a", "40k",
            "-f", "mp3", "pipe:1"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                chunk = proc.stdout.read(1024)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.terminate()
    return Response(generate(), mimetype="audio/mpeg")

# -----------------------
# Low-res HLS
# -----------------------
@app.route("/lowvideo/<channel>")
def low_video(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        abort(404)
    launch_low_hls(channel, url)
    playlist_path = f"/lowhls/{channel}/index.m3u8"
    html = f"""
<html>
<head>
<title>{channel} Low Video</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
</head>
<body>
<h2>{channel} Low 144p</h2>
<video id="player" controls autoplay playsinline style="width:95%; max-width:720px;"></video>
<script>
const video=document.getElementById('player');
const src="{playlist_path}";
if(Hls.isSupported()){{const hls=new Hls(); hls.loadSource(src); hls.attachMedia(video);}}
else{{video.src=src;}}
</script>
</body>
</html>
"""
    return html

# -----------------------
# Serve low HLS files
# -----------------------
@app.route("/lowhls/<channel>/<path:filename>")
def serve_lowhls(channel, filename):
    directory = os.path.join(LOW_HLS_DIR, channel)
    if not os.path.exists(os.path.join(directory, filename)):
        abort(404)
    return send_from_directory(directory, filename)

# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)