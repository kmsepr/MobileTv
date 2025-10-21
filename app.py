import subprocess
import time
import threading
import os
import logging
from collections import deque
from flask import Flask, Response, render_template_string

# ------------------------------------------------
# Logging & Flask setup
# ------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# ------------------------------------------------
# YouTube live stream list
# ------------------------------------------------
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
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

# ------------------------------------------------
# Cache and configuration
# ------------------------------------------------
CACHE = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# ------------------------------------------------
# Extract direct audio URL
# ------------------------------------------------
def get_youtube_audio_url(youtube_url: str):
    """Get direct YouTube live audio URL."""
    try:
        command = ["yt-dlp", "-f", "91", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            command.insert(1, "--cookies")
            command.insert(2, COOKIES_FILE)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logging.error(f"yt-dlp error for {youtube_url}: {result.stderr.strip()}")
    except Exception:
        logging.exception("Failed extracting stream URL")
    return None

# ------------------------------------------------
# Background refresh (every 5 minutes)
# ------------------------------------------------
def refresh_stream_urls():
    while True:
        logging.info("🔄 Checking YouTube live URLs...")
        for name, yurl in YOUTUBE_STREAMS.items():
            direct = get_youtube_audio_url(yurl)
            if direct:
                CACHE[name] = direct
                logging.info(f"✅ Cached {name}")
            else:
                logging.warning(f"⚠️ Could not refresh {name}")
        time.sleep(300)  # 5 minutes

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# ------------------------------------------------
# Continuous FFmpeg stream generator
# ------------------------------------------------
def generate_stream(station):
    """Continuously yield MP3 audio chunks with FFmpeg reconnect logic."""
    while True:
        url = CACHE.get(station)
        if not url:
            logging.warning(f"❌ No URL cached for {station}, waiting...")
            time.sleep(10)
            continue

        cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_at_eof", "1",
            "-rw_timeout", "5000000",
            "-user_agent", "Mozilla/5.0",
            "-i", url,
            "-vn",
            "-ac", "1",
            "-b:a", "48k",
            "-bufsize", "512k",
            "-f", "mp3",
            "-"
        ]

        logging.info(f"▶️ Starting FFmpeg for {station}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)
        buffer = deque(maxlen=4000)

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                if chunk:
                    buffer.append(chunk)
                    yield buffer.popleft()
                else:
                    time.sleep(0.05)
        except GeneratorExit:
            process.terminate()
            break
        except Exception as e:
            logging.error(f"Stream error for {station}: {e}")

        logging.warning(f"⚠️ Restarting FFmpeg for {station}")
        process.terminate()
        process.wait()
        time.sleep(3)

# ------------------------------------------------
# Flask Routes
# ------------------------------------------------
@app.route("/<station>")
def stream(station):
    if station not in YOUTUBE_STREAMS:
        return "Invalid station name", 404
    return Response(generate_stream(station), mimetype="audio/mpeg",
                    headers={"Cache-Control": "no-cache",
                             "Connection": "keep-alive",
                             "Transfer-Encoding": "chunked"})

@app.route("/")
def index():
    live = sorted(YOUTUBE_STREAMS.keys())
    html = """
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Live Radio</title></head>
    <body style="font-family:sans-serif;padding:10px">
    <h3>🎧 Continuous YouTube Live Audio Streams</h3>
    """
    for i, name in enumerate(live, 1):
        disp = name.replace("_", " ").title()
        html += f"<a href='/{name}' style='display:block;margin:6px 0'>{i}. {disp} 🔴</a>"
    html += "</body></html>"
    return render_template_string(html)

# ------------------------------------------------
# Run Server
# ------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)