import time
import threading
import os
import logging
import subprocess
from flask import Flask, Response, render_template_string

# ------------------------------------------------
# Logging setup
# ------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

# ------------------------------------------------
# 📡 List of YouTube Live Streams
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
    "movie_kalyanaraman": "https://www.youtube.com/watch?v=e_bMbcZt9b4"
}

CACHE = {}
last_update = {}


def get_youtube_audio_url(youtube_url):
    """Extracts direct audio stream URL from YouTube Live."""
    try:
        command = ["/usr/local/bin/yt-dlp", "-f", "91", "-g", youtube_url]
        if os.path.exists("/mnt/data/cookies.txt"):
            command.insert(2, "--cookies")
            command.insert(3, "/mnt/data/cookies.txt")

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logging.error(f"yt-dlp error: {result.stderr}")
            return None
    except Exception as e:
        logging.exception("Exception extracting YouTube audio")
        return None


def refresh_stream_urls():
    """Background thread: refreshes all streams every 30 minutes."""
    global CACHE, last_update
    while True:
        logging.info("🔄 Refreshing all YouTube audio URLs...")
        for name, yt_url in YOUTUBE_STREAMS.items():
            now = time.time()
            if name not in last_update or now - last_update[name] > 1800:
                url = get_youtube_audio_url(yt_url)
                if url:
                    CACHE[name] = url
                    last_update[name] = now
                    logging.info(f"✅ {name} refreshed.")
                else:
                    logging.warning(f"❌ Could not refresh {name}")
        time.sleep(60)


def init_cache():
    """Populate cache once at startup."""
    logging.info("⚙️ Initializing YouTube audio URLs...")
    for name, yt_url in YOUTUBE_STREAMS.items():
        url = get_youtube_audio_url(yt_url)
        if url:
            CACHE[name] = url
            last_update[name] = time.time()
            logging.info(f"✅ Loaded {name}")
        else:
            logging.warning(f"⚠️ Failed initial load: {name}")


def generate_stream(url):
    """Streams audio using FFmpeg and auto-reconnects."""
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
            bufsize=4096
        )

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
                time.sleep(0.02)
        except GeneratorExit:
            process.terminate()
            process.wait()
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")

        process.terminate()
        process.wait()
        time.sleep(5)


@app.route("/")
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Live Audio Streams</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: sans-serif; background:#111; color:#eee; text-align:center; margin:0; }
            h1 { color:#0ff; margin-top:20px; }
            .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; padding:20px; }
            a { display:block; padding:10px; background:#222; border-radius:10px; color:#0ff; text-decoration:none; transition:0.2s; }
            a:hover { background:#0ff; color:#111; }
            footer { margin:20px; font-size:14px; color:#777; }
        </style>
    </head>
    <body>
        <h1>📡 YouTube Live Audio Streams</h1>
        <div class="grid">
            {% for name in streams %}
                <a href="/{{ name }}" target="_blank">{{ name.replace('_', ' ').title() }}</a>
            {% endfor %}
        </div>
        <footer>Powered by Flask + FFmpeg + yt-dlp</footer>
    </body>
    </html>
    """
    return render_template_string(html, streams=YOUTUBE_STREAMS.keys())


@app.route("/<station_name>")
def stream(station_name):
    """Serve station stream."""
    url = CACHE.get(station_name)
    if not url:
        logging.warning(f"URL missing for {station_name}, retrying...")
        yt_url = YOUTUBE_STREAMS.get(station_name)
        if yt_url:
            url = get_youtube_audio_url(yt_url)
            if url:
                CACHE[station_name] = url
            else:
                return "Stream temporarily unavailable. Try again later.", 503
        else:
            return "Station not found", 404
    return Response(generate_stream(url), mimetype="audio/mpeg")


if __name__ == "__main__":
    init_cache()  # 👈 Ensure CACHE is populated before start
    threading.Thread(target=refresh_stream_urls, daemon=True).start()
    app.run(host="0.0.0.0", port=8000, debug=False)