import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort
import subprocess, os, requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (direct m3u8)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
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
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube Live URL
# -----------------------
def get_youtube_live_url(youtube_url: str):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception:
        return None

# -----------------------
# Refresh YouTube URLs
# -----------------------
def refresh_stream_urls():
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
            else:
                LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Proxy YouTube HLS
# -----------------------
def stream_proxy(url: str):
    try:
        with requests.get(url, stream=True, timeout=10) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk
    except Exception:
        yield b""

# -----------------------
# Flask Routes
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]
    all_channels = tv_channels + live_youtube

    html = """
<html>
<head>
<title>📺 Live Channels</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: sans-serif; background:#000; color:#0f0; padding:15px; text-align:center; }
h2 { font-size:26px; margin-bottom:20px; }
a { color:#0f0; display:block; margin:10px 0; font-size:22px; padding:10px; background:#111; border-radius:8px; text-decoration:none; }
a:hover { background:#222; }
</style>
</head>
<body>
<h2>📺 Live Channels</h2>
{% for key in channels %}
<a href="/watch/{{ key }}">[{{ loop.index }}] ▶ {{ key.replace('_',' ').title() }}</a>
{% endfor %}

<script>
// Keypad shortcuts
document.addEventListener("keydown", function(e) {
    let links = document.querySelectorAll("a");
    if (e.key >= "1" && e.key <= "9") {
        let idx = parseInt(e.key, 10) - 1;
        if (idx < links.length) window.location.href = links[idx].href;
    }
    if (e.key === "0") {
        window.location.href = "/";
    }
});
</script>

</body>
</html>"""
    return render_template_string(html, channels=all_channels)

@app.route("/watch/<channel>")
def watch(channel):
    if channel not in TV_STREAMS and channel not in CACHE:
        abort(404)
    if channel in TV_STREAMS:
        video_url = TV_STREAMS[channel]
    else:
        video_url = f"/stream/{channel}"

    html = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel.replace('_',' ').title()}</title>
<style>
body {{ background:#000; color:#0f0; text-align:center; padding:10px; }}
video {{ width:95%; max-width:700px; border:2px solid #0f0; border-radius:10px; }}
a {{ color:#0f0; display:block; margin-top:20px; font-size:20px; text-decoration:none; }}
</style>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video controls autoplay>
<source src="{video_url}" type="application/vnd.apple.mpegurl">
</video>
<a href='/'>⬅ Back (Press 0)</a>

<script>
document.addEventListener("keydown", function(e) {
    if (e.key === "0") {
        window.location.href = "/";
    }
});
</script>

</body>
</html>"""
    return html

@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503
    return Response(stream_proxy(url), mimetype="application/vnd.apple.mpegurl")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)