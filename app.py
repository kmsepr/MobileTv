import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string

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
    "aljazeera_arabic": "https://www.youtube.com/@aljazeera/live",
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
}

# -----------------------
# TV Audio Streams (direct m3u8)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
}

# -----------------------
# Cache
# -----------------------
CACHE = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube Audio URL
# -----------------------
def get_youtube_audio_url(youtube_url: str):
    try:
        cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "--no-playlist",
            "-g",
            youtube_url
        ]

        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        logging.error(result.stderr)
        return None

    except Exception:
        logging.exception("YouTube extraction failed")
        return None

# -----------------------
# Background refresh
# -----------------------
def refresh_streams():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube audio URLs")
        now = time.time()

        for name, url in YOUTUBE_STREAMS.items():
            if name not in last_update or now - last_update[name] > 120:
                direct = get_youtube_audio_url(url)
                if direct:
                    CACHE[name] = direct
                    last_update[name] = now
                    logging.info(f"✅ {name} updated")

        time.sleep(60)

threading.Thread(target=refresh_streams, daemon=True).start()

# -----------------------
# AAC Stream Generator
# -----------------------
def generate_stream(station_name: str):
    if station_name in TV_STREAMS:
        source_url = TV_STREAMS[station_name]
        logging.info(f"📺 TV AAC: {station_name}")
    else:
        source_url = CACHE.get(station_name)
        if not source_url:
            return
        logging.info(f"🎵 YT AAC: {station_name}")

    while True:
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-loglevel", "error",

                "-fflags", "+genpts+nobuffer",
                "-flags", "low_delay",

                "-rw_timeout", "15000000",
                "-max_delay", "5000000",

                "-reconnect", "1",
                "-reconnect_at_eof", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",

                "-user_agent", "Mozilla/5.0",
                "-i", source_url,

                "-vn",
                "-ac", "1",
                "-ar", "22050",

                "-c:a", "aac",
                "-b:a", "24k",
                "-profile:a", "aac_low",

                "-flush_packets", "1",
                "-f", "adts",
                "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=8192,
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
    return Response(generate_stream(station_name), mimetype="audio/aac")

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
    app.run(host="0.0.0.0", port=8000, threaded=True)