import time
import threading
import os
import logging
import subprocess
from flask import Flask, Response, render_template_string

# ------------------------------------------------
# Configure logging
# ------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

    # Malayalam full movie channel example
    "movie_kalyanaraman": "https://www.youtube.com/watch?v=e_bMbcZt9b4"
}

# ------------------------------------------------
# 🌐 Cache for storing direct stream URLs
# ------------------------------------------------
CACHE = {}


def get_youtube_live_url(youtube_url: str):
    """
    Extract direct playable URL from a YouTube Live channel.
    Prioritizes low-bitrate audio for stability.
    """
    try:
        # Prefer audio-only m4a (lightweight), fallback to best
        cmd = [
            "yt-dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio/best",
            "-g",
            "--no-warnings",
            "--geo-bypass",
            "--live-from-start",
            youtube_url,
        ]

        if os.path.exists(COOKIES_FILE):
            cmd[1:1] = ["--cookies", COOKIES_FILE]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)

        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            # yt-dlp sometimes returns multiple lines (audio+video); take the first
            if "\n" in url:
                url = url.split("\n")[0].strip()
            logging.info(f"✅ Extracted YouTube stream URL: {url[:80]}...")
            return url
        else:
            err = result.stderr.strip()
            logging.warning(f"⚠️ yt-dlp failed for {youtube_url}: {err}")
    except subprocess.TimeoutExpired:
        logging.error(f"⏳ yt-dlp timeout for {youtube_url}")
    except Exception as e:
        logging.error(f"❌ Exception while fetching YouTube URL for {youtube_url}: {e}")

    return None


def refresh_stream_urls():
    """Refresh all stream URLs every 30 minutes."""
    last_update = {}

    while True:
        logging.info("🔄 Refreshing stream URLs...")

        for name, yt_url in YOUTUBE_STREAMS.items():
            now = time.time()
            if name not in last_update or now - last_update[name] > 1800:
                url = get_youtube_audio_url(yt_url)
                if url:
                    CACHE[name] = url
                    last_update[name] = now
                    logging.info(f"✅ Updated {name}: {url}")
                else:
                    logging.warning(f"❌ Failed to update {name}")

        time.sleep(60)  # Check every minute


# ------------------------------------------------
# Start background thread
# ------------------------------------------------
threading.Thread(target=refresh_stream_urls, daemon=True).start()


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

        logging.info(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
                time.sleep(0.02)
        except GeneratorExit:
            logging.info("❌ Client disconnected. Stopping FFmpeg process...")
            process.terminate()
            process.wait()
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")

        logging.warning("⚠️ FFmpeg stopped, restarting stream...")
        process.terminate()
        process.wait()
        time.sleep(5)


# ------------------------------------------------
# 📄 Homepage route
# ------------------------------------------------
@app.route("/")
def home():
    html = """
    <html>
    <head>
        <title>🎧 YouTube Live Audio Streams</title>
        <style>
            body { font-family: Arial; background: #111; color: #fff; text-align: center; }
            h1 { color: #00ff99; margin-top: 20px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; padding: 20px; }
            a { display: block; background: #222; color: #00ffcc; text-decoration: none; padding: 10px; border-radius: 10px; border: 1px solid #333; transition: 0.3s; }
            a:hover { background: #00ffcc; color: #000; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🎧 YouTube Live Audio Streams</h1>
        <div class="grid">
            {% for name in streams %}
                <a href="/{{ name }}" target="_blank">{{ name.replace('_', ' ').title() }}</a>
            {% endfor %}
        </div>
        <p style="color:#888;">Click a station to start streaming audio.</p>
    </body>
    </html>
    """
    return render_template_string(html, streams=YOUTUBE_STREAMS.keys())


# ------------------------------------------------
# 🎙️ Stream endpoint
# ------------------------------------------------
@app.route("/<station_name>")
def stream(station_name):
    """Serve the requested station as a live stream."""
    url = CACHE.get(station_name)

    if not url:
        return "Station not found or not available", 404

    return Response(generate_stream(url), mimetype="audio/mpeg")


# ------------------------------------------------
# Run app
# ------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)