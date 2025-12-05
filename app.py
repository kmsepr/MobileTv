from flask import Flask, Response, request, send_from_directory, render_template_string
import subprocess, os, time, threading, json, yt_dlp, requests

app = Flask(__name__)

# ========================
#   CONFIG
# ========================

CACHE_DIR = "/mnt/data/mp3_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

COOKIES_FILE = "/mnt/data/cookies.txt"

YOUTUBE_STREAMS = {

 "unacademy_neet": "https://www.youtube.com/uaneetenglish/live",

"samastha": "https://youtube.com/@samasthaonlineoffical/live",

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
    "kas_ranker": "https://www.youtube.com/@freepscclasses/live",
}

CHANNEL_LOGOS = {
    "ndtv": "https://i.imgur.com/5iOgvOe.png",
    "aajtak": "https://i.imgur.com/lqsO1sU.png",
    "abp_news": "https://i.imgur.com/8vDqdBM.png",
}

LIVE_URLS = {}

# ========================
#   BACKGROUND REFRESH
# ========================

def refresh_streams():
    while True:
        for key, url in YOUTUBE_STREAMS.items():
            try:
                ydl_opts = {
                    "quiet": True,
                    "cookies": COOKIES_FILE,
                    "format": "best",
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    LIVE_URLS[key] = info["url"]
            except:
                pass
        time.sleep(3600)


threading.Thread(target=refresh_streams, daemon=True).start()

# ========================
#        ROUTES
# ========================

@app.route("/")
def home():
    files = sorted(os.listdir(CACHE_DIR), reverse=True)

    html = """
<html>
<head>
<title>Live + MP3</title>
<style>
body { background:#000; color:#fff; font-family:Arial; }
.tabs { display:flex; }
.tab {
    padding:12px; cursor:pointer; background:#222;
    margin-right:10px; border-radius:10px;
}
.active { background:#444; }
.grid { display:grid; grid-template-columns:repeat(2,1fr); gap:15px; }
.card { padding:10px; background:#111; border-radius:10px; text-align:center; }
.hidden { display:none; }
img { width:100px; border-radius:10px; }
</style>

<script>
function showTab(x){
    document.getElementById("youtube").style.display="none";
    document.getElementById("mp3").style.display="none";
    document.getElementById(x).style.display="grid";

    document.getElementById("tab_youtube").classList.remove("active");
    document.getElementById("tab_mp3").classList.remove("active");

    document.getElementById("tab_"+x).classList.add("active");
}
</script>
</head>

<body>

<div class="tabs">
    <div class="tab active" id="tab_youtube" onclick="showTab('youtube')">▶ YouTube Live</div>
    <div class="tab" id="tab_mp3" onclick="showTab('mp3')">🎵 MP3 Converter</div>
</div>


<div id="youtube" class="grid">
{% for key in youtube_channels %}
<div class="card">
    <img src="{{ logos.get(key) }}">
    <div>{{ key.replace('_',' ').title() }}</div>
    <a style="color:#0ff;" href="/watch/{{ key }}">▶ Watch</a> |
    <a style="color:#ff0;" href="/audio/{{ key }}">🎵 Audio</a>
</div>
{% endfor %}
</div>


<div id="mp3" class="hidden">

<h3>🎵 Convert YouTube → MP3 (40 kbps Mono)</h3>

<form method="POST" action="/convert">
    <input name="url" placeholder="Paste YouTube link..." style="width:70%;padding:10px;">
    <button type="submit" style="padding:10px;">Convert</button>
</form>

<h3>📀 Cached MP3 Files</h3>

{% if files %}
    {% for f in files %}
    <div class="card">
        {{ f }} <br>
        <a href="/mp3/{{ f }}" style="color:#0ff;">▶ Play</a> |
        <a href="/download/{{ f }}" style="color:#ff0;">⬇ Download</a>
    </div>
    {% endfor %}
{% else %}
<p>No mp3 yet.</p>
{% endif %}
</div>

</body>
</html>
"""

    return render_template_string(html,
        youtube_channels=YOUTUBE_STREAMS.keys(),
        logos=CHANNEL_LOGOS,
        files=files
    )

# ========================
#   WATCH VIDEO
# ========================

@app.route("/watch/<channel>")
def watch(channel):
    if channel not in LIVE_URLS:
        return "Stream not available", 404
    return f"<video src='{LIVE_URLS[channel]}' controls autoplay></video>"

# ========================
#   STREAM 40 kbps MONO LIVE AUDIO
# ========================

@app.route("/audio/<channel>")
def audio(channel):
    if channel not in LIVE_URLS:
        return "Not available", 404

    url = LIVE_URLS[channel]

    def generate():
        cmd = [
            "ffmpeg",
            "-i", url,
            "-vn",
            "-ac", "1",
            "-b:a", "40k",
            "-f", "mp3",
            "pipe:1"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        while True:
            data = p.stdout.read(1024)
            if not data:
                break
            yield data

    return Response(generate(), mimetype="audio/mpeg")

# ========================
#   MP3 CONVERTER (40 kbps MONO)
# ========================

@app.route("/convert", methods=["POST"])
def convert():
    url = request.form.get("url")
    if not url:
        return "No URL", 400

    out = os.path.join(CACHE_DIR, f"{int(time.time())}.mp3")

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "40K",
        "--postprocessor-args", "ffmpeg:-ac 1 -b:a 40k",
        "-o", out,
        url,
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return f"Error: {r.stderr}"

    return f"Saved: {out}<br><a href='/'>Back</a>"

# ========================
#   MP3 SERVE + DOWNLOAD
# ========================

@app.route("/mp3/<file>")
def serve_mp3(file):
    return send_from_directory(CACHE_DIR, file, mimetype="audio/mpeg")

@app.route("/download/<file>")
def download(file):
    return send_from_directory(CACHE_DIR, file, as_attachment=True)


# ========================
#   MAIN
# ========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)