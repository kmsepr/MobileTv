import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort, send_from_directory
import subprocess, os, requests, signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "bloomberg_tv": "https://bloomberg-bloomberg-3-br.samsung.wurl.tv/manifest/playlist.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
}

# -----------------------
# YouTube Live
# -----------------------
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
}

CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

LOW_DIR = "./lowhls"
os.makedirs(LOW_DIR, exist_ok=True)

LOW_PROCS = {}

# -----------------------
# YouTube extractor
# -----------------------
def get_youtube_live_url(url):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except:
        pass
    return None

# -----------------------
# Refresh thread
# -----------------------
def refresh():
    while True:
        for k, v in YOUTUBE_STREAMS.items():
            u = get_youtube_live_url(v)
            if u:
                CACHE[k] = u
                LIVE_STATUS[k] = True
            else:
                LIVE_STATUS[k] = False
        time.sleep(60)

threading.Thread(target=refresh, daemon=True).start()

# -----------------------
# Start LOW video FFmpeg
# -----------------------
def start_low(channel, src):
    out = os.path.join(LOW_DIR, channel)
    os.makedirs(out, exist_ok=True)

    if channel in LOW_PROCS and LOW_PROCS[channel].poll() is None:
        return

    cmd = [
        "ffmpeg",
        "-i", src,
        "-an",
        "-vf", "scale=240:-2",
        "-r", "6",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-profile:v", "baseline",
        "-b:v", "40k",
        "-maxrate", "40k",
        "-bufsize", "80k",
        "-f", "hls",
        "-hls_time", "1",
        "-hls_list_size", "3",
        "-hls_flags", "delete_segments+omit_endlist",
        os.path.join(out, "index.m3u8")
    ]

    LOW_PROCS[channel] = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

# -----------------------
# Home
# -----------------------
@app.route("/")
def home():
    tv = list(TV_STREAMS.keys())
    yt = [k for k, v in LIVE_STATUS.items() if v]

    return render_template_string("""
    <h3>TV</h3>
    {% for k in tv %}
      <p>{{k}} :
      <a href="/watch/{{k}}">▶</a>
      <a href="/audio/{{k}}">🎵</a>
      <a href="/low/{{k}}">📉</a></p>
    {% endfor %}
    <h3>YouTube</h3>
    {% for k in yt %}
      <p>{{k}} :
      <a href="/watch/{{k}}">▶</a>
      <a href="/audio/{{k}}">🎵</a>
      <a href="/low/{{k}}">📉</a></p>
    {% endfor %}
    """, tv=tv, yt=yt)

# -----------------------
# Normal (RAW)
# -----------------------
@app.route("/watch/<c>")
def watch(c):
    url = TV_STREAMS.get(c) or CACHE.get(c)
    if not url:
        abort(404)

    return f"""
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <video id=v controls autoplay></video>
    <script>
    var v=document.getElementById('v');
    var s="{url}";
    if(Hls.isSupported()){{var h=new Hls();h.loadSource(s);h.attachMedia(v);}}
    else v.src=s;
    </script>
    """

# -----------------------
# LOW VIDEO (40 kbps)
# -----------------------
@app.route("/low/<c>")
def low(c):
    url = TV_STREAMS.get(c) or CACHE.get(c)
    if not url:
        abort(404)

    start_low(c, url)

    return f"""
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <video id=v controls autoplay></video>
    <script>
    var h=new Hls();
    h.loadSource("/lowhls/{c}/index.m3u8");
    h.attachMedia(document.getElementById('v'));
    </script>
    """

# -----------------------
# Serve LOW HLS
# -----------------------
@app.route("/lowhls/<path:p>")
def lowfiles(p):
    return send_from_directory(LOW_DIR, p)

# -----------------------
# AUDIO ONLY (unchanged)
# -----------------------
@app.route("/audio/<c>")
def audio(c):
    url = TV_STREAMS.get(c) or CACHE.get(c)
    if not url:
        abort(404)

    def gen():
        p = subprocess.Popen(
            ["ffmpeg", "-i", url, "-vn", "-ac", "1", "-b:a", "40k", "-f", "mp3", "pipe:1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        while True:
            d = p.stdout.read(1024)
            if not d:
                break
            yield d

    return Response(gen(), mimetype="audio/mpeg")

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)