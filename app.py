import time
import threading
import os
import logging
import subprocess
from flask import Flask, Response, render_template_string, abort

# ----------------------------------
# CONFIGURE LOGGING & APP
# ----------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# ----------------------------------
# TV STREAMS (Direct m3u8)
# ----------------------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safaritv/d0dbe04ecf5cf88407dc69930f3a3878.sdp/playlist.m3u8",
    "media_one_tv": "https://ythls.armelin.one/channel/UCqmfDdQz8Se797TOpEyHzAg.m3u8",
}

# ----------------------------------
# YOUTUBE AUDIO STREAMS
# ----------------------------------
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
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    "xylem_psc": "https://www.youtube.com/@XylemPSC/live",
    "entri_app": "https://www.youtube.com/@entriapp/live",
}

# ----------------------------------
# CACHE
# ----------------------------------
CACHE = {}

# ----------------------------------
# GET YOUTUBE AUDIO URL
# ----------------------------------
def get_youtube_audio_url(youtube_url):
    """Extract direct audio URL via yt-dlp (format 91 for low bitrate)."""
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
        logging.exception("Error extracting YouTube audio URL")
        return None

# ----------------------------------
# REFRESH STREAM URLs
# ----------------------------------
def refresh_stream_urls():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube stream URLs...")
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
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# ----------------------------------
# GENERATE STREAM (Stable FFmpeg proxy)
# ----------------------------------
def generate_stream(url, is_audio=False):
    """FFmpeg streaming with reconnect & buffer control."""
    while True:
        cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-timeout", "5000000",
            "-user_agent", "Mozilla/5.0",
            "-i", url,
        ]

        if is_audio:
            cmd += ["-vn", "-ac", "1", "-b:a", "40k", "-bufsize", "512k", "-f", "mp3", "-"]
        else:
            cmd += ["-c", "copy", "-f", "mpegts", "-"]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)
        logging.info(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
                if is_audio:
                    time.sleep(0.015)  # smooth pacing for audio
        except GeneratorExit:
            process.terminate()
            process.wait()
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")
        finally:
            process.terminate()
            process.wait()
            logging.warning("⚠️ Restarting stream...")
            time.sleep(5)

# ----------------------------------
# ROUTES
# ----------------------------------

@app.route("/")
def home():
    html = """
    <!doctype html>
    <html>
    <head>
        <title>📻 Live TV & YouTube Audio</title>
        <style>
            body { font-family: sans-serif; background: #111; color: #eee; text-align: center; }
            h1 { color: #6cf; }
            a { color: #0f0; text-decoration: none; display: block; margin: 8px; }
            .section { background: #222; border-radius: 12px; padding: 10px; margin: 15px; }
        </style>
    </head>
    <body>
        <h1>📡 Live Streams</h1>
        <div class="section">
            <h2>🎬 TV Channels</h2>
            {% for name in tv %}
                <a href="/tv/{{name}}" target="_blank">{{name}}</a>
            {% endfor %}
        </div>
        <div class="section">
            <h2>🎧 YouTube Audio (Radio)</h2>
            {% for name in yt %}
                <a href="/yt/{{name}}" target="_blank">{{name}}</a>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, tv=TV_STREAMS.keys(), yt=YOUTUBE_STREAMS.keys())

@app.route("/tv/<name>")
def tv_stream(name):
    """Stream direct TV channel (m3u8)."""
    url = TV_STREAMS.get(name)
    if not url:
        abort(404)
    return Response(generate_stream(url, is_audio=False), mimetype="video/mp2t")

@app.route("/yt/<name>")
def youtube_audio(name):
    """Stream YouTube audio channel."""
    url = CACHE.get(name)
    if not url:
        return f"❌ {name} not found or not ready", 404
    return Response(generate_stream(url, is_audio=True), mimetype="audio/mpeg")

# ----------------------------------
# MAIN
# ----------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)