import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# 📡 YouTube Live Streams
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

# 🌐 Cache: {station_name: {'url': str or None, 'live': bool}}
CACHE = {}

def get_youtube_audio_url(youtube_url):
    """Extract direct audio stream URL."""
    try:
        command = ["/usr/local/bin/yt-dlp", "--force-generic-extractor", "-f", "91", "-g", youtube_url]
        if os.path.exists("/mnt/data/cookies.txt"):
            command.insert(2, "--cookies")
            command.insert(3, "/mnt/data/cookies.txt")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logging.error(f"Error extracting from {youtube_url}: {result.stderr}")
            return None
    except Exception:
        logging.exception("Exception while extracting audio URL")
        return None

def refresh_stream_urls():
    """Refresh all stream URLs every 30 minutes."""
    while True:
        logging.info("🔄 Refreshing all stream URLs...")
        for name, yt_url in YOUTUBE_STREAMS.items():
            url = get_youtube_audio_url(yt_url)
            if url:
                CACHE[name] = {"url": url, "live": True}
                logging.info(f"✅ {name} is LIVE: {url}")
            else:
                CACHE[name] = {"url": None, "live": False}
                logging.warning(f"❌ {name} appears OFFLINE")
        time.sleep(1800)

# 🧵 Start background thread
threading.Thread(target=refresh_stream_urls, daemon=True).start()

def generate_stream(url):
    """Stream audio from YouTube using FFmpeg."""
    while True:
        start_time = time.time()
        process = subprocess.Popen(
            [
                "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
                "-timeout", "5000000", "-user_agent", "Mozilla/5.0",
                "-i", url, "-vn", "-ac", "1", "-ar", "22050", "-b:a", "40k",
                "-bufsize", "64k", "-f", "mp3", "-"
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096
        )

        logging.info(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
                time.sleep(0.02)
                if time.time() - start_time > 1800:
                    logging.info("⏰ Restarting FFmpeg after 30 minutes")
                    break
        except GeneratorExit:
            logging.info("❌ Client disconnected")
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
        logging.warning("⚠️ FFmpeg process ended, restarting in 5s...")
        time.sleep(5)

@app.route("/<station_name>")
def stream(station_name):
    data = CACHE.get(station_name)
    if not data or not data.get("url"):
        return "Station not found or not live", 404
    return Response(generate_stream(data["url"]), mimetype="audio/mpeg")

@app.route("/")
def index():
    stream_keys = list(YOUTUBE_STREAMS.keys())
    keypad_map = {}
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>YouTube Live Audio Streams</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: sans-serif;
            padding: 10px;
            background: #fff;
        }
        a {
            display: block;
            padding: 10px;
            margin: 6px 0;
            text-decoration: none;
            color: #000;
            background: #e0e0e0;
            border: 1px solid #bbb;
            border-radius: 6px;
            font-size: 18px;
            font-weight: bold;
        }
        h3 {
            font-size: 22px;
        }
    </style>
</head>
<body>
    <h3>🔊 YouTube Live (Audio only)</h3>
"""

    for idx, name in enumerate(stream_keys):
        display_name = name.replace('_', ' ').title()
        key = (idx + 1) % 10
        data = CACHE.get(name, {})
        live_icon = "🔴" if data.get("live") else "⚪"
        html += f'<a href="/{name}">[{key}] {live_icon} {display_name}</a>\n'
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

@app.route("/stations.json")
def stations_json():
    return jsonify({name: {
        "url": f"/{name}",
        "live": data.get("live", False)
    } for name, data in CACHE.items()})

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)