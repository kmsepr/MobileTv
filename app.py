import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string
from collections import deque

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
# Direct TV Streams (HLS links)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
}

# -----------------------
# Cache for direct stream URLs
# -----------------------
CACHE = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube video+audio URL
# -----------------------
def get_youtube_stream_url(youtube_url: str):
    """Get direct video+audio URL from YouTube live."""
    try:
        command = ["yt-dlp", "-f", "best[ext=mp4]/best", "-g", youtube_url]

        # Insert cookies if available
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
        logging.exception("Exception while extracting YouTube video")
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
                direct_url = get_youtube_stream_url(url)
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
    """Yield MP4 chunks (YouTube + TV) using FFmpeg with reconnect."""
    url = None

    if station_name in CACHE:       # YouTube (cached)
        url = CACHE.get(station_name)
    elif station_name in TV_STREAMS:  # Direct TV
        url = TV_STREAMS[station_name]

    if not url:
        logging.warning(f"No stream URL for {station_name}")
        return

    buffer = deque(maxlen=2000)

    while True:
        ffmpeg_cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-timeout", "5000000",
            "-user_agent", "Mozilla/5.0",
            "-i", url,
            "-c:v", "copy",   # keep video
            "-c:a", "aac",    # ensure audio compatibility
            "-f", "mp4",
            "-"
        ]

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096,
        )

        logging.info(f"▶️ Streaming {station_name} as MP4")

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
# Stream route
# -----------------------
@app.route("/<station_name>")
def stream(station_name):
    if station_name in CACHE or station_name in TV_STREAMS:
        return Response(generate_stream(station_name), mimetype="video/mp4")
    else:
        return "Station not found or not available", 404

# -----------------------
# Homepage
# -----------------------
@app.route("/")
def index():
    # Live YouTube (only if cached) + always-available TV streams
    live_channels = {k: v for k, v in YOUTUBE_STREAMS.items() if k in CACHE and CACHE[k]}
    live_channels.update(TV_STREAMS)

    sorted_live = sorted(live_channels.keys())

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Live MP4 Streams</title>
      <style>
        body { font-family: sans-serif; padding: 10px; background: #fff; }
        video { width: 100%; max-width: 500px; margin: 10px 0; border: 1px solid #ccc; border-radius: 8px; }
        h3 { margin-top: 20px; }
      </style>
    </head>
    <body>
      <h3>📺 Live YouTube + TV Streams</h3>
    """

    for idx, name in enumerate(sorted_live, 1):
        display_name = name.replace("_", " ").title()
        html += f"<p>{idx}. {display_name}</p>"
        html += f"<video controls autoplay src='/{name}'></video>\n"

    html += "</body></html>"
    return render_template_string(html)

# -----------------------
# Run Flask
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)