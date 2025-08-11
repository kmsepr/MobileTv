import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string

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
        time.sleep(1800)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

def generate_stream(url):
    """Streams audio using FFmpeg, restarts instantly if it crashes/drops."""
    while True:
        process = subprocess.Popen([
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-reconnect_at_eof", "1",
            "-rw_timeout", "15000000",  # 15 seconds
            "-probesize", "64k",
            "-analyzeduration", "500000",  # 0.5s
            "-user_agent", "Mozilla/5.0",
            "-i", url,
            "-vn", "-ac", "1", "-b:a", "24k", "-bufsize", "64k",
            "-f", "mp3", "-"
        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=4096)

        logging.info(f"🎵 Streaming from: {url}")

        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
        except GeneratorExit:
            logging.info("❌ Client disconnected. Stopping FFmpeg...")
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")

        # Clean up process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

        logging.warning("⚠️ FFmpeg stopped, restarting stream in 2s...")
        time.sleep(2)  # Prevent rapid restart loop

@app.route("/<station_name>")
def stream(station_name):
    url = CACHE.get(station_name)
    if not url:
        return "Station not found or not available", 404
    return Response(generate_stream(url), mimetype="audio/mpeg")

@app.route("/")
def index():
    html = """
    <h3>🔊 YouTube Live</h3>
    """
    live_channels = {k: v for k, v in YOUTUBE_STREAMS.items() if k in CACHE and CACHE[k]}
    sorted_live = sorted(live_channels.keys())
    sorted_other = sorted(set(YOUTUBE_STREAMS.keys()) - set(live_channels.keys()))
    sorted_keys = sorted_live + sorted_other
    for idx, name in enumerate(sorted_keys):
        display_name = name.replace('_', ' ').title()
        badge = '<span style="color:white;background:red;padding:2px 4px;">LIVE</span>' if name in live_channels else ''
        html += f'<a href="/{name}">{display_name} {badge}</a><br>'
    return render_template_string(html)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)