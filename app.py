# -----------------------
# Imports
# -----------------------
import os, time, threading, logging, subprocess, requests, select
from flask import Flask, Response, render_template_string, request, abort, send_from_directory

# -----------------------
# Logging
# -----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# -----------------------
# Flask App
# -----------------------
app = Flask(__name__)

# -----------------------
# Config
# -----------------------
CACHE_DIR = "/mnt/data/mp3_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
COOKIES_FILE = "/mnt/data/cookies.txt"

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

CHANNEL_LOGOS = {k: "" for k in YOUTUBE_STREAMS.keys()}

# -----------------------
# Runtime caches
# -----------------------
CACHE = {}        # channel -> direct HLS URL
LIVE_STATUS = {}  # channel -> True/False

# -----------------------
# Helper: check live page
# -----------------------
def is_live_page_reachable(url: str) -> bool:
    try:
        r = requests.get(url, timeout=4)
        return r.status_code == 200
    except Exception:
        return False

# -----------------------
# Helper: get direct HLS URL from YouTube
# -----------------------
def get_youtube_live_url(youtube_url: str):
    if not is_live_page_reachable(youtube_url):
        return None
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = result.stdout.strip()
        err = result.stderr.lower()
        if "sign in to confirm" in err or "unable to extract" in err:
            return None
        if result.returncode == 0 and out:
            return out.splitlines()[0]
    except Exception:
        return None
    return None

# -----------------------
# Background thread: refresh YouTube live URLs
# -----------------------
def refresh_stream_urls():
    while True:
        logging.info("Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
            else:
                LIVE_STATUS[name] = False
                if name in CACHE:
                    del CACHE[name]
        time.sleep(60)  # refresh every 60s

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# MP3 converter
# -----------------------
def convert_to_mp3(url: str):
    try:
        cmd_id = ["yt-dlp", "--get-id", url]
        if os.path.exists(COOKIES_FILE):
            cmd_id.insert(1, "--cookies")
            cmd_id.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd_id, capture_output=True, text=True, timeout=20)
        video_id = result.stdout.strip() or str(int(time.time()))
    except Exception:
        video_id = str(int(time.time()))
    out_template = os.path.join(CACHE_DIR, f"{video_id}.%(ext)s")
    cmd_convert = [
        "yt-dlp", "--extract-audio", "--audio-format", "mp3",
        "--audio-quality", "40K", "--postprocessor-args", "ffmpeg:-ac 1 -b:a 40k -map_metadata -1",
        "-o", out_template, url
    ]
    if os.path.exists(COOKIES_FILE):
        cmd_convert.insert(1, "--cookies")
        cmd_convert.insert(2, COOKIES_FILE)
    subprocess.run(cmd_convert, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    mp3_file = os.path.join(CACHE_DIR, f"{video_id}.mp3")
    return f"{video_id}.mp3" if os.path.exists(mp3_file) else None

# -----------------------
# FFmpeg stream generator
# -----------------------
def stream_audio_with_ffmpeg(input_url: str, timeout: float = 6.0):
    cmd = ["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-i",input_url,"-vn","-ac","1","-b:a","40k","-f","mp3","pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start = time.time()
    first_chunk = b""
    try:
        while True:
            if proc.poll() is not None:
                raise RuntimeError("ffmpeg exited early")
            rlist, _, _ = select.select([proc.stdout.fileno()], [], [], 0.2)
            if rlist:
                first_chunk = proc.stdout.read(1024)
                if first_chunk: break
            if time.time() - start > timeout:
                proc.terminate()
                raise RuntimeError("ffmpeg timeout")
    except Exception:
        proc.terminate()
        raise
    yield first_chunk
    try:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk: break
            yield chunk
    finally:
        proc.terminate()

# -----------------------
# Routes
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]

    if channel not in live_youtube:
        abort(404)

    video_url = CACHE.get(channel)
    if not video_url:
        return "Channel not ready", 503

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
    if (video.canPlayType("application/vnd.apple.mpegurl")) {{
        video.src = src;
    }} else if (Hls.isSupported()) {{
        const hls = new Hls({{ lowLatencyMode: true }});
        hls.loadSource(src);
        hls.attachMedia(video);
    }} else {{
        alert("⚠️ Browser cannot play HLS stream.");
    }}
}});
</script>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video id="player" controls autoplay playsinline></video>
<div style="margin-top:15px;">
  <a href="/">⬅ Home</a>
</div>
</body>
</html>
"""
    return html

@app.route("/audio/<channel>")
def audio(channel):
    url = CACHE.get(channel)
    if not url: return "Channel not ready", 503
    return Response(stream_audio_with_ffmpeg(url), mimetype="audio/mpeg")

@app.route("/convert", methods=["POST"])
def convert():
    url = request.form.get("url")
    if not url: return "No URL provided", 400
    filename = convert_to_mp3(url)
    return f"Saved: {filename} <br><a href='/'>Back</a>" if filename else "Conversion failed", 500

@app.route("/mp3/<file>")
def serve_mp3(file):
    safe_path = os.path.join(CACHE_DIR, file)
    if not os.path.isfile(safe_path): abort(404)
    return send_from_directory(CACHE_DIR, file, mimetype="audio/mpeg")

@app.route("/download/<file>")
def download(file):
    safe_path = os.path.join(CACHE_DIR, file)
    if not os.path.isfile(safe_path): abort(404)
    return send_from_directory(CACHE_DIR, file, as_attachment=True)

@app.route("/")
def home():
    live_youtube = [ch for ch in YOUTUBE_STREAMS.keys() if LIVE_STATUS.get(ch)]
    files = sorted(os.listdir(CACHE_DIR), reverse=True)

    html = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Live YouTube + MP3</title>
  <style>
    body{margin:0;font-family:system-ui,Segoe UI,Roboto;color:#fff;background:#0b0b0b}
    .tabs{display:flex;justify-content:center;gap:12px;padding:14px;background:#000}
    .tab{padding:12px 18px;border-radius:10px;background:#111;cursor:pointer;font-size:20px}
    .tab.active{background:#0ff;color:#000;font-weight:700}
    .container{padding:16px;max-width:1100px;margin:0 auto}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:16px}
    .card{background:#121212;padding:18px;border-radius:10px;text-align:center;font-size:20px}
    .bigbtn{display:inline-block;margin-top:10px;padding:10px 14px;border-radius:8px;background:transparent;border:1px solid #0ff;color:#0ff;text-decoration:none}
    form input{width:70%;padding:12px;font-size:18px;border-radius:8px;border:1px solid #333;background:#0b0b0b;color:#fff}
    form button{padding:12px 16px;font-size:18px;border-radius:8px;margin-left:8px;background:#0ff;color:#000;border:none}
    h1{font-size:24px;margin:6px 0}
    small{color:#9aa0a6;display:block;margin-top:8px}
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
      <h1>Live Channels</h1>
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
        <div class="card">No live channels available.</div>
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
    return render_template_string(html, youtube_channels=live_youtube, files=files)

# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    logging.info("Starting Flask server on 0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
