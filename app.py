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
# TV Audio Streams (direct URLs)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
    
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
    try:
        command = ["yt-dlp", "-f", "91", "-g", youtube_url]

        if os.path.exists(COOKIES_FILE):
            command.insert(1, "--cookies")
            command.insert(2, COOKIES_FILE)

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        logging.error(result.stderr.strip())
        return None

    except Exception:
        logging.exception("YouTube extraction error")
        return None

# -----------------------
# Refresh YouTube streams
# -----------------------
def refresh_stream_urls():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube streams")
        now = time.time()
        for name, url in YOUTUBE_STREAMS.items():
            if name not in last_update or now - last_update[name] > 60:
                direct = get_youtube_audio_url(url)
                if direct:
                    CACHE[name] = direct
                    last_update[name] = now
                    logging.info(f"✅ {name}")
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Stream generator (YT + TV)
# -----------------------
def generate_stream(station_name: str):
    if station_name in TV_STREAMS:
        source_url = TV_STREAMS[station_name]
        logging.info(f"📺 TV audio: {station_name}")
    else:
        source_url = CACHE.get(station_name)
        if not source_url:
            return
        logging.info(f"🎵 YouTube audio: {station_name}")

    while True:
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "10",
                "-user_agent", "Mozilla/5.0",
                "-i", source_url,
                "-vn",
                "-ac", "1",
                "-b:a", "40k",
                "-f", "mp3",
                "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096,
        )

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
        except GeneratorExit:
            process.terminate()
            break
        except Exception:
            process.terminate()
            time.sleep(3)

# -----------------------
# Stream route
# -----------------------
@app.route("/<station_name>")
def stream(station_name):
    if station_name not in CACHE and station_name not in TV_STREAMS:
        return "Station not found", 404
    return Response(generate_stream(station_name), mimetype="audio/mpeg")

# -----------------------
# Homepage
# -----------------------
@app.route("/")
def index():
    yt_live = [k for k in YOUTUBE_STREAMS if k in CACHE]
    tv_live = list(TV_STREAMS.keys())

    html = """
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body { font-family:sans-serif; padding:10px }
      a { display:block; margin:6px 0; font-weight:bold }
      .live { color:red }
    </style>
    </head>
    <body>
    """

    keypad = {}
    idx = 1

    html += "<h3>🎵 YouTube Live Audio</h3>"
    for name in yt_live:
        html += f"<a href='/{name}'>{idx}. {name.replace('_',' ').title()} <span class='live'>LIVE</span></a>"
        keypad[str(idx % 10)] = name
        idx += 1

    html += "<h3>📺 TV Audio</h3>"
    for name in tv_live:
        html += f"<a href='/{name}'>{idx}. {name.replace('_',' ').title()}</a>"
        keypad[str(idx % 10)] = name
        idx += 1

    html += f"""
    <script>
    const map = {keypad};
    document.addEventListener("keydown", e => {{
        if (e.key in map) location.href='/' + map[e.key];
    }});
    </script>
    </body></html>
    """

    return render_template_string(html)

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)