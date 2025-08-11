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
    "asianet_news": "https://www.youtube.com/@asianetnews/live",
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
    "eft_guru": "https://www.youtube.com/@EFTGuru-ql8dk/live",
    "unacademy_ias": "https://www.youtube.com/@UnacademyIASEnglish/live",
    "entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",
    "entri_ias": "https://www.youtube.com/@EntriIAS/live",
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
    except Exception:
        logging.exception("Exception while extracting YouTube audio")
        return None

def refresh_stream_urls():
    """Refresh all stream URLs every 30 minutes."""
    while True:
        logging.info("🔄 Refreshing all stream URLs...")

        for name, yt_url in YOUTUBE_STREAMS.items():
            url = get_youtube_audio_url(yt_url)
            if url:
                CACHE[name] = url
                logging.info(f"✅ Updated {name}: {url}")
            else:
                logging.warning(f"❌ Failed to update {name}")

        time.sleep(1800)  # Refresh all every 30 minutes

# Start background thread
threading.Thread(target=refresh_stream_urls, daemon=True).start()

def generate_stream(url):
    """Streams audio using FFmpeg and auto-restarts every 30 minutes."""
    while True:
        start_time = time.time()

        process = subprocess.Popen([
                "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
                "-timeout", "5000000", "-user_agent", "Mozilla/5.0",
                "-i", url, "-vn", "-ac", "1", "-b:a", "40k", "-bufsize", "1M",
                "-f", "mp3", "-"
            ],stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)

        logging.info(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
                time.sleep(0.02)
                if time.time() - start_time > 1800:
                    logging.info("⏰ Restarting FFmpeg after 30 minutes")
                    break
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
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Live Audio Streams</title>
    <style>
        body {
            font-family: sans-serif;
            font-size: 18px;
            padding: 10px;
            background-color: #ffffff;
        }
        a {
            display: block;
            padding: 10px;
            margin: 5px 0;
            color: #000000;
            background-color: #e0e0e0;
            text-decoration: none;
            border: 1px solid #aaa;
            font-weight: bold;
        }
        h3 {
            font-size: 20px;
        }
        .live-badge {
            background-color: red;
            color: white;
            font-size: 12px;
            padding: 2px 5px;
            border-radius: 4px;
            margin-left: 8px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h3>🔊 YouTube Live</h3>
"""

    # Live channels are those with a working cached URL
    live_channels = {k: v for k, v in YOUTUBE_STREAMS.items() if k in CACHE and CACHE[k]}
    other_channels = {k: v for k, v in YOUTUBE_STREAMS.items() if k not in live_channels}

    # Sort both alphabetically
    sorted_live = sorted(live_channels.keys())
    sorted_other = sorted(other_channels.keys())

    # Merge so live are on top
    sorted_keys = sorted_live + sorted_other

    keypad_map = {}
    for idx, name in enumerate(sorted_keys):
        display_name = name.replace('_', ' ').title()
        key = (idx + 1) % 10  # 1–9 then 0
        badge = '<span class="live-badge">LIVE</span>' if name in live_channels else ''
        html += f'<a href="/{name}">[{key}] {display_name} {badge}</a>\n'
        keypad_map[str(key)] = name

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

</body>
</html>
"""
    return render_template_string(html)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)