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
    if channel not in CACHE:
        abort(404)
    video_url = f"/stream/{channel}"
    html = f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{channel}</title></head><body>
    <h1>Watching {channel}</h1>
    <video controls autoplay><source src="{video_url}" type="application/vnd.apple.mpegurl"></video>
    <br><a href='/'>⬅ Back Home</a></body></html>"""
    return html

@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url: return "Channel not ready", 503
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, stream=True, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return f"Error fetching stream: {e}", 502
    return Response(r.iter_content(chunk_size=8192), content_type=r.headers.get("Content-Type","application/vnd.apple.mpegurl"))

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
    html = """..."""  # Keep your previous home page HTML template with tabs (Live + MP3)
    return render_template_string(html, youtube_channels=live_youtube, files=files)

# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    logging.info("Starting Flask server on 0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000, debug=False)