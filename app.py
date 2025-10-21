import subprocess
import time
import threading
import os
import logging
from collections import deque
from flask import Flask, Response, request, make_response, render_template_string

# -----------------------
# Configure logging
# -----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# YouTube Live Streams
# -----------------------
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

# -----------------------
# Cache for direct stream URLs
# -----------------------
CACHE = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube audio URL
# -----------------------
def get_youtube_audio_url(youtube_url: str):
    """Get direct audio URL from YouTube live."""
    try:
        command = ["yt-dlp", "-f", "91", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            command.insert(1, "--cookies")
            command.insert(2, COOKIES_FILE)

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            logging.error(f"yt-dlp error for {youtube_url}: {result.stderr.strip()}")
            return None
    except Exception:
        logging.exception("Exception while extracting YouTube audio")
        return None

# -----------------------
# Refresh stream URLs every 60s
# -----------------------
def refresh_stream_urls():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube stream URLs...")
        now = time.time()
        for name, url in YOUTUBE_STREAMS.items():
            if name not in last_update or now - last_update[name] > 60:
                direct_url = get_youtube_audio_url(url)
                if direct_url:
                    CACHE[name] = direct_url
                    last_update[name] = now
                    logging.info(f"✅ Updated {name}")
                else:
                    logging.warning(f"❌ Failed to update {name}")
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Stream generator
# -----------------------
def generate_stream(station_name: str):
    """Yield MP3 chunks using FFmpeg with reconnect."""
    url = CACHE.get(station_name)
    if not url:
        logging.warning(f"No cached URL for {station_name}")
        return

    buffer = deque(maxlen=2000)  # ~2 min buffer
    while True:
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "10",
                "-timeout", "5000000",
                "-user_agent", "Mozilla/5.0",
                "-i", url,
                "-vn",
                "-ac", "1",
                "-b:a", "40k",
                "-bufsize", "1M",
                "-f", "mp3",
                "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096,
        )

        logging.info(f"🎵 Streaming {station_name}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                buffer.append(chunk)
                if buffer:
                    yield buffer.popleft()
                else:
                    time.sleep(0.05)
        except GeneratorExit:
            logging.info(f"❌ Client disconnected from {station_name}")
            process.terminate()
            process.wait()
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")

        logging.warning(f"⚠️ FFmpeg stopped for {station_name}, restarting...")
        process.terminate()
        process.wait()
        time.sleep(5)

# -----------------------
# Stream route (forces download)
# -----------------------
@app.route("/<station_name>")
def stream(station_name):
    url = CACHE.get(station_name)
    if not url:
        return "Station not found or not available", 404

    response = Response(generate_stream(station_name), mimetype="audio/mpeg")
    response.headers["Content-Disposition"] = f'attachment; filename="{station_name}.mp3"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response

# -----------------------
# Homepage
# -----------------------
@app.route("/")
def index():
    live_channels = {k: v for k, v in YOUTUBE_STREAMS.items() if k in CACHE and CACHE[k]}
    sorted_live = sorted(live_channels.keys())

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>YouTube Live Audio Streams</title>
      <style>
        body { font-family: sans-serif; padding: 10px; background: #fff; }
        a { display: block; margin: 5px 0; font-weight: bold; color: blue; text-decoration: underline; cursor: pointer; }
        a:hover { color: red; }
        .live { color: red; font-weight: bold; margin-left: 5px; }
      </style>
    </head>
    <body>
      <h3>🎵 Currently Live Streams</h3>
    """

    keypad_map = {}
    for idx, name in enumerate(sorted_live, 1):
        display_name = name.replace("_", " ").title()
        html += f"<a href='/{name}' download>{idx}. {display_name} <span class='live'>LIVE</span></a>\n"
        key = str(idx % 10)
        keypad_map[key] = name

    html += f"""
    <script>
    const streamMap = {keypad_map};
    document.addEventListener("keydown", function(e) {{
        if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
        const key = e.key;
        if (key in streamMap) {{
            window.location.href = '/' + streamMap[key];
        }}
    }});
    </script>
    </body></html>
    """
    return render_template_string(html)

# -----------------------
# Run Flask
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)