import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# 📡 List of YouTube Live Streams
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
    "voice_rahmani": "https://www.youtube.com/@voiceofrahmaniyya5828/live"
}

# 🌐 Cache for storing direct stream URLs
CACHE = {}

def get_youtube_audio_url(youtube_url):
    """Extracts direct audio stream URL from YouTube Live."""
    try:
        command = ["/usr/local/bin/yt-dlp", "--force-generic-extractor", "-f", "91", "-g", youtube_url]

        if os.path.exists("/mnt/data/cookies.txt"):
            command.insert(2, "--cookies")
            command.insert(3, "/mnt/data/cookies.txt")

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logging.error(f"Error extracting YouTube audio: {result.stderr}")
            return None
    except Exception as e:
        logging.exception("Exception while extracting YouTube audio")
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

# Start background thread
threading.Thread(target=refresh_stream_urls, daemon=True).start()

def generate_stream(url):
    """Streams audio using FFmpeg and auto-reconnects."""
    while True:
        process = subprocess.Popen(
            [
    "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
    "-timeout", "5000000", "-user_agent", "Mozilla/5.0",
    "-i", url,
    "-vn",                   # no video
    "-ac", "1",              # mono audio
    "-ar", "22050",          # lower sample rate (optional for more compression)
    "-b:a", "20k",           # reduced audio bitrate
    "-bufsize", "64k",       # smaller buffer for low-speed links
    "-f", "mp3", "-"
],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096
        )

        logging.info(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
                time.sleep(0.02)  # Slight delay helps reduce CPU spikes and avoid buffer overrun
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

@app.route("/<station_name>")
def stream(station_name):
    """Serve the requested station as a live stream."""
    url = CACHE.get(station_name)

    if not url:
        return "Station not found or not available", 404

    return Response(generate_stream(url), mimetype="audio/mpeg")

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <title>Live Audio Streams</title>
        <style>
            body {
                font-family: sans-serif;
                background: #ffffff;
                margin: 0;
                padding: 10px;
                color: #000000;
            }
            h2 {
                text-align: center;
                margin-bottom: 20px;
                font-size: 1.2rem;
            }
            .list {
                display: flex;
                flex-direction: column;
                gap: 10px;
                align-items: stretch;
                max-width: 100%;
            }
            .card {
                background: #f2f2f2;
                border-radius: 6px;
                padding: 12px;
                text-align: center;
                color: #000000;
                font-weight: bold;
                font-size: 1rem;
                text-decoration: none;
                border: 1px solid #ccc;
            }
            .card:active {
                background: #e6e6e6;
            }
        </style>
    </head>
    <body>
        <h2>🔊 Available Streams</h2>
        <div class="list">
    """

    for name in YOUTUBE_STREAMS:
        display_name = name.replace('_', ' ').title()
        html += f'<a href="/{name}" class="card">{display_name}</a>'

    html += """
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)