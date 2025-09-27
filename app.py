import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string, abort
from collections import deque

# -----------------------
# Configure logging
# -----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# Static TV (m3u8) Streams
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
}

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

CACHE = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube direct stream URL
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
        else:
            logging.error(f"yt-dlp error for {youtube_url}: {result.stderr.strip()}")
            return None
    except Exception:
        logging.exception("Exception while extracting YouTube stream")
        return None

# -----------------------
# Background thread to refresh YouTube URLs
# -----------------------
def refresh_stream_urls():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube stream URLs...")
        now = time.time()
        for name, url in YOUTUBE_STREAMS.items():
            if name not in last_update or now - last_update[name] > 60:
                direct_url = get_youtube_audio_url(url)
                if direct_url:
                    CACHE[name] = direct_url
                    last_update[name] = now
                    logging.info(f"✅ Updated {name}")
                else:
                    logging.warning(f"❌ Failed to update {name}")
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Stream generator (for YouTube audio)
# -----------------------
def generate_stream(station_name: str):
    url = CACHE.get(station_name)
    if not url:
        logging.warning(f"No cached URL for {station_name}")
        return
    buffer = deque(maxlen=2000)

    while True:
        process = subprocess.Popen(
            [
                "ffmpeg", "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10",
                "-timeout", "5000000", "-user_agent", "Mozilla/5.0",
                "-i", url, "-vn", "-ac", "1", "-b:a", "40k", "-bufsize", "1M",
                "-f", "mp3", "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=4096,
        )
        try:
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                buffer.append(chunk)
                if buffer:
                    yield buffer.popleft()
                else:
                    time.sleep(0.05)
        except GeneratorExit:
            process.terminate()
            process.wait()
            break
        except Exception as e:
            logging.error(f"Stream error: {e}")
        process.terminate()
        process.wait()
        time.sleep(5)

# -----------------------
# Routes
# -----------------------
@app.route("/")
def home():
    all_channels = list(TV_STREAMS.keys()) + list(YOUTUBE_STREAMS.keys())
    enumerated_channels = list(enumerate(all_channels, 1))  # enumerate in Python
    
    html = """<html>
<head>
<title>📺 Live TV & 🎵 YouTube</title>
<style>
body { font-family: sans-serif; text-align:center; background:#111; color:#fff; }
.grid { display:grid; grid-template-columns:repeat(2,1fr); gap:15px; margin:20px; }
.card { background:#222; padding:20px; border-radius:10px; }
a { color:#0f0; text-decoration:none; font-size:18px; }
</style>
</head>
<body>
<h2>📺 TV & 🎵 YouTube Live</h2>
<div class="grid" id="channelGrid">
{% for idx, key in channels %}
<div class="card">
<a href="/watch/{{ key }}">▶ {{ idx }}. {{ key.replace('_',' ').title() }}</a>
</div>
{% endfor %}
</div>

<script>
document.addEventListener("keydown", function(event) {
    let num = parseInt(event.key);
    if (!isNaN(num) && num > 0) {
        let links = document.querySelectorAll("#channelGrid a");
        if (num <= links.length) {
            window.location.href = links[num-1].href;
        }
    }
});
</script>
</body>
</html>"""
    return render_template_string(html, channels=enumerated_channels)

@app.route("/watch/<channel>")
def watch(channel):
    if channel in TV_STREAMS:
        stream_url = TV_STREAMS[channel]
        html = """
<html><body style="background:#000; color:#fff; text-align:center;">
<h2>{{ channel.replace('_',' ').title() }}</h2>
<video controls autoplay style="width:95%; max-width:700px;">
<source src="{{ url }}" type="application/x-mpegURL">
</video>
<p><a href="/">⬅ Back</a></p>
</body></html>
"""
        return render_template_string(html, channel=channel, url=stream_url)

    elif channel in YOUTUBE_STREAMS:
        if channel not in CACHE:
            return "YouTube stream not ready yet, try again.", 503
        html = f"""
<html><body style="background:#000; color:#fff; text-align:center;">
<h2>{channel.replace('_',' ').title()}</h2>
<audio controls autoplay style="width:95%; max-width:700px;">
<source src="/{channel}" type="audio/mpeg">
</audio>
<p><a href="/">⬅ Back</a></p>
</body></html>
"""
        return html

    else:
        abort(404)

@app.route("/<station_name>")
def stream(station_name):
    if station_name not in YOUTUBE_STREAMS or station_name not in CACHE:
        return "Station not found or not available", 404
    return Response(generate_stream(station_name), mimetype="audio/mpeg")

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)