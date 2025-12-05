import os
import time
import threading
import logging
import subprocess
import requests
import select
from glob import glob
from flask import Flask, Response, render_template_string, request, abort, send_from_directory

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Flask(__name__)

# -----------------------
# CONFIG
# -----------------------
CACHE_DIR = "/mnt/data/mp3_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

COOKIES_FILE = "/mnt/data/cookies.txt"   # used by yt-dlp if present

# -----------------------
# YouTube Live Channels
# -----------------------
YOUTUBE_STREAMS = {
    "unacademy_neet": "https://www.youtube.com/@uaneetenglish/live",
    "samastha": "https://youtube.com/@samasthaonlineoffical/live",
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/@quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
    "yaqeen_institute": "https://www.youtube.com/@yaqeeninstituteofficial/live",
    "bayyinah_tv": "https://www.youtube.com/@bayyinah/live",
    "eft_guru": "https://www.youtube.com/@EFTGuru-ql8dk/live",
    "unacademy_ias": "https://www.youtube.com/@UnacademyIASEnglish/live",
    "studyiq_hindi": "https://www.youtube.com/@StudyIQEducationLtd/live",
    "aljazeera_arabic": "https://www.youtube.com/@aljazeera/live",
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    "entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",
    "xylem_psc": "https://www.youtube.com/@XylemPSC/live",
    "xylem_sslc": "https://www.youtube.com/@XylemSSLC2023/live",
    "entri_app": "https://www.youtube.com/@entriapp/live",
    "entri_ias": "https://www.youtube.com/@EntriIAS/live",
    "studyiq_english": "https://www.youtube.com/@studyiqiasenglish/live",
    "voice_rahmani": "https://www.youtube.com/@voiceofrahmaniyya5828/live",
}

# Minimal logos dict
CHANNEL_LOGOS = {k: "" for k in YOUTUBE_STREAMS.keys()}

# Runtime caches
CACHE = {}        # channel -> direct stream URL (string)
LIVE_STATUS = {}  # channel -> bool (True if available)


# -----------------------
# Helper: check if live page reachable
# -----------------------
def is_live_page_reachable(url: str) -> bool:
    try:
        r = requests.get(url, timeout=4)
        return r.status_code == 200
    except Exception as e:
        logging.debug("Live page check failed for %s: %s", url, e)
        return False


# -----------------------
# Helper: get youtube direct URL using yt-dlp
# -----------------------
def get_youtube_live_url(youtube_url: str):
    if not is_live_page_reachable(youtube_url):
        logging.info("Live page unreachable: %s", youtube_url)
        return None

    try:
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=default",
            "-f", "best[height<=360]",
            "-g",
            youtube_url
        ]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)

        logging.info("Running yt-dlp for URL: %s", youtube_url)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = result.stdout.strip()
        err = result.stderr.lower()

        if "sign in to confirm" in err or "unable to extract" in err:
            logging.warning("Blocked or restricted by YouTube: %s", youtube_url)
            return None

        if result.returncode == 0 and out:
            logging.info("yt-dlp success: %s", youtube_url)
            return out.splitlines()[0]
        else:
            logging.info("yt-dlp returned no URL: %s", youtube_url)
            return None
    except Exception as e:
        logging.error("yt-dlp exception for %s: %s", youtube_url, e)
        return None


# -----------------------
# Background thread: refresh live URLs
# -----------------------
def refresh_stream_urls():
    while True:
        logging.info("Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
                logging.info("Live found: %s -> %s", name, direct_url)
            else:
                LIVE_STATUS[name] = False
                if name in CACHE:
                    del CACHE[name]
                logging.info("Not live: %s", name)
        time.sleep(60)  # refresh every 60s


threading.Thread(target=refresh_stream_urls, daemon=True).start()


# -----------------------
# MP3 converter helper (yt-dlp -> mp3 40kbps mono)
# -----------------------
def convert_to_mp3(url: str):
    timestamp = str(int(time.time()))
    out_template = os.path.join(CACHE_DIR, f"{timestamp}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "40K",
        "--postprocessor-args", "ffmpeg:-ac 1 -b:a 40k -map_metadata -1",
        "-o", out_template,
        url,
    ]
    if os.path.exists(COOKIES_FILE):
        cmd.insert(1, "--cookies")
        cmd.insert(2, COOKIES_FILE)

    logging.info("Running yt-dlp to convert: %s", url)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        logging.error("yt-dlp failed: %s", proc.stderr)
        return None

    # find output mp3 file
    candidates = glob(os.path.join(CACHE_DIR, f"{timestamp}.*"))
    for c in candidates:
        if c.lower().endswith(".mp3"):
            return os.path.basename(c)
    return os.path.basename(candidates[0]) if candidates else None


# -----------------------
# FFmpeg readiness check + streaming generator
# -----------------------
def stream_audio_with_ffmpeg(input_url: str, timeout: float = 6.0):
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_url,
        "-vn",
        "-ac", "1",
        "-b:a", "40k",
        "-f", "mp3",
        "pipe:1"
    ]
    logging.info("Starting ffmpeg: %s ...", " ".join(cmd[:6]))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    start = time.time()
    first_chunk = b""
    try:
        while True:
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                raise RuntimeError(f"ffmpeg exited early: {stderr[:200]}")
            rlist, _, _ = select.select([proc.stdout.fileno()], [], [], 0.2)
            if rlist:
                first_chunk = proc.stdout.read(1024)
                if first_chunk:
                    break
            if time.time() - start > timeout:
                proc.terminate()
                raise RuntimeError("ffmpeg did not start producing data within timeout")
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
        raise

    yield first_chunk
    try:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


@app.route("/watch/<channel>")
def watch(channel):
    if channel not in CACHE:
        abort(404)
    
    # Use the direct stream URL (HLS) from CACHE
    video_url = f"/stream/{channel}"  # your streaming route

    html = f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Watching {channel.replace('_', ' ').title()}</title>
  <style>
    body {{
      background: #0b0b0b;
      color: #fff;
      font-family: system-ui, sans-serif;
      text-align: center;
      padding: 20px;
    }}
    video {{
      width: 100%;
      max-width: 800px;
      height: auto;
      margin-top: 20px;
      border-radius: 10px;
      background: #000;
    }}
    a {{
      display: inline-block;
      margin-top: 20px;
      padding: 10px 14px;
      border-radius: 8px;
      background: #0ff;
      color: #000;
      text-decoration: none;
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <h1>Watching: {channel.replace('_', ' ').title()}</h1>
  
  <!-- HTML5 video player (HLS) -->
  <video controls autoplay>
    <source src="{video_url}" type="application/vnd.apple.mpegurl">
    Your browser does not support HLS playback. Try Safari or Chrome.
  </video>

  <br>
  <a href="/">⬅ Back Home</a>
</body>
</html>
"""
    return html


@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logging.warning("Stream fetch error for %s: %s", channel, e)
        return f"Error fetching stream: {e}", 502
    return Response(r.iter_content(chunk_size=8192), content_type=r.headers.get("Content-Type", "application/vnd.apple.mpegurl"))


@app.route("/audio/<channel>")
def audio(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    def generate():
        try:
            for chunk in stream_audio_with_ffmpeg(url, timeout=6.0):
                yield chunk
        except RuntimeError as e:
            logging.warning("ffmpeg stream failed for %s: %s", channel, e)
            return

    return Response(generate(), mimetype="audio/mpeg")


@app.route("/convert", methods=["POST"])
def convert():
    url = request.form.get("url")
    if not url:
        return "No URL provided", 400

    filename = convert_to_mp3(url)
    if not filename:
        return "Conversion failed", 500

    return f"Saved: {filename} <br><a href='/'>Back</a>"


@app.route("/mp3/<file>")
def serve_mp3(file):
    safe_path = os.path.join(CACHE_DIR, file)
    if not os.path.isfile(safe_path):
        abort(404)
    return send_from_directory(CACHE_DIR, file, mimetype="audio/mpeg")


@app.route("/download/<file>")
def download(file):
    safe_path = os.path.join(CACHE_DIR, file)
    if not os.path.isfile(safe_path):
        abort(404)
    return send_from_directory(CACHE_DIR, file, as_attachment=True)



# -----------------------
# HOME PAGE (Auto Grid, big text, no thumbnails)
# -----------------------
@app.route("/")
def home():
    # only list live channels that are currently available
    live_youtube = [n for n, ok in LIVE_STATUS.items() if ok]
    files = sorted(os.listdir(CACHE_DIR), reverse=True)

    html = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Live + MP3</title>
  <style>
    :root{--bg:#0b0b0b;--card:#121212;--accent:#0ff;--muted:#9aa0a6}
    body{margin:0;font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial;color:#fff;background:var(--bg)}
    .tabs{display:flex;justify-content:center;gap:12px;padding:14px;background:#000}
    .tab{padding:12px 18px;border-radius:10px;background:#111;cursor:pointer;font-size:20px}
    .tab.active{background:var(--accent);color:#000;font-weight:700}
    .container{padding:16px;max-width:1100px;margin:0 auto}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:16px}
    .card{background:var(--card);padding:18px;border-radius:10px;text-align:center;font-size:20px}
    .bigbtn{display:inline-block;margin-top:10px;padding:10px 14px;border-radius:8px;background:transparent;border:1px solid var(--accent);color:var(--accent);text-decoration:none}
    form input{width:70%;padding:12px;font-size:18px;border-radius:8px;border:1px solid #333;background:#0b0b0b;color:#fff}
    form button{padding:12px 16px;font-size:18px;border-radius:8px;margin-left:8px;background:var(--accent);color:#000;border:none}
    h1{font-size:24px;margin:6px 0}
    small{color:var(--muted);display:block;margin-top:8px}
  </style>
  <script>
    function showTab(id){
      document.getElementById('live').style.display='none';
      document.getElementById('mp3').style.display='none';
      document.getElementById(id).style.display='block';
      document.getElementById('tab_live').classList.remove('active');
      document.getElementById('tab_mp3').classList.remove('active');
      document.getElementById('tab_'+id).classList.add('active');
    }
    window.onload=function(){ showTab('live'); }
  </script>
</head>
<body>
  <div class="tabs">
    <div id="tab_live" class="tab active" onclick="showTab('live')">▶ YouTube Live</div>
    <div id="tab_mp3" class="tab" onclick="showTab('mp3')">🎵 MP3 Converter</div>
  </div>

  <div class="container">
    <div id="live">
      <h1>Live Channels (only available ones)</h1>
      <div class="grid">
      {% if youtube_channels %}
        {% for ch in youtube_channels %}
          <div class="card">
            <div style="font-size:20px;font-weight:700">{{ ch.replace('_',' ').title() }}</div>
            <small>Live</small>
            <div style="margin-top:12px">
              <a class="bigbtn" href="/watch/{{ ch }}">▶ Watch</a>
              <a class="bigbtn" href="/audio/{{ ch }}">🎵 Audio</a>
            </div>
          </div>
        {% endfor %}
      {% else %}
        <div class="card">No live channels available right now.</div>
      {% endif %}
      </div>
    </div>

    <div id="mp3" style="display:none">
      <h1>MP3 Converter (40 kbps Mono)</h1>
      <form method="POST" action="/convert">
        <input name="url" placeholder="Paste YouTube link..." required />
        <button type="submit">Convert</button>
      </form>
      <small>Cached files are stored on the server.</small>

      <div class="grid" style="margin-top:18px">
        {% if files %}
          {% for f in files %}
            <div class="card">
              <div style="font-weight:700">{{ f }}</div>
              <div style="margin-top:12px">
                <a class="bigbtn" href="/mp3/{{ f }}">▶ Play</a>
                <a class="bigbtn" href="/download/{{ f }}">⬇ Download</a>
              </div>
            </div>
          {% endfor %}
        {% else %}
          <div class="card">No cached MP3 files yet.</div>
        {% endif %}
      </div>
    </div>
  </div>
</body>
</html>
"""
    available = [ch for ch in YOUTUBE_STREAMS.keys() if LIVE_STATUS.get(ch)]
    return render_template_string(html, youtube_channels=available, files=files)
# -----------------------
# RUN
# -----------------------
if __name__ == "__main__":
    logging.info("Starting Flask server on 0.0.0.0:8000")
    logging.info("Cookies file exists: %s", os.path.exists(COOKIES_FILE))
    app.run(host="0.0.0.0", port=8000, debug=False)
