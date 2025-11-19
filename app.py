import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort, stream_with_context, request
import subprocess, os, requests
import signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (direct m3u8)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "bloomberg_tv": "https://bloomberg-bloomberg-3-br.samsung.wurl.tv/manifest/playlist.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
    "aqsa_tv": "http://167.172.161.13/hls/feedspare/6udfi7v8a3eof6nlps6e9ovfrs65c7l7.m3u8",
    "mult": "http://stv.mediacdn.ru/live/cdn/mult/playlist.m3u8",
    "yemen_today": "https://video.yementdy.tv/hls/yementoday.m3u8",
    "yemen_shabab": "https://starmenajo.com/hls/yemenshabab/index.m3u8",
    "al_sahat": "https://assahat.b-cdn.net/Assahat/assahatobs/index.m3u8",
}

# -----------------------
# YouTube Live Channels
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
    "kas_ranker": "https://www.youtube.com/@freepscclasses/live",
}

# -----------------------
# Channel Logos
# -----------------------
CHANNEL_LOGOS = {
    "safari_tv": "https://i.imgur.com/dSOfYyh.png",
    "victers_tv": "https://i.imgur.com/kj4OEsb.png",
    "bloomberg_tv": "https://i.imgur.com/OuogLHx.png",
    "france_24": "https://upload.wikimedia.org/wikipedia/commons/c/c1/France_24_logo_%282013%29.svg",
    "aqsa_tv": "https://i.imgur.com/Z2rfrQ8.png",
    "mazhavil_manorama": "https://i.imgur.com/fjgzW20.png",
    "dd_malayalam": "https://i.imgur.com/ywm2dTl.png",
    "dd_sports": "https://i.imgur.com/J2Ky5OO.png",
    "mult": "https://i.imgur.com/xi351Fx.png",
    "yemen_today": "https://i.imgur.com/8TzcJu5.png",
    "yemen_shabab": "https://i.imgur.com/H5Oi2NS.png",
    "al_sahat": "https://i.imgur.com/UVndAta.png",
    **{k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
}

CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube HLS URL (unchanged)
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
    except Exception:
        pass
    return None

# -----------------------
# Background refresh thread (unchanged)
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
# Home Page (with visible tabs) - unchanged
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [n for n, live in LIVE_STATUS.items() if live]

    html = """
<html>
<head>
<title>📺 TV & YouTube Live</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family:sans-serif; background:#111; color:#fff; margin:0; padding:0; }
h2 { text-align:center; margin:10px 0; }
.tabs { display:flex; justify-content:center; background:#000; padding:10px; }
.tab { padding:10px 20px; cursor:pointer; background:#222; color:#0ff; border-radius:10px; margin:0 5px; transition:0.2s; }
.tab.active { background:#0ff; color:#000; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); gap:12px; padding:10px; }
.card { background:#222; border-radius:10px; padding:10px; text-align:center; transition:0.2s; }
.card:hover { background:#333; }
.card img { width:100%; height:80px; object-fit:contain; margin-bottom:8px; }
.card span { font-size:14px; color:#0f0; }
.hidden { display:none; }
</style>
<script>
function showTab(tab){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.grid').forEach(g=>g.classList.add('hidden'));
  document.getElementById(tab).classList.remove('hidden');
  document.getElementById('tab_'+tab).classList.add('active');
}
window.onload=()=>showTab('tv');
</script>
</head>
<body>
<div class="tabs">
  <div class="tab active" id="tab_tv" onclick="showTab('tv')">📺 TV</div>
  <div class="tab" id="tab_youtube" onclick="showTab('youtube')">▶ YouTube</div>
</div>

<div id="tv" class="grid">
{% for key in tv_channels %}
<div class="card">
    <img src="{{ logos.get(key) }}">
    <span>{{ key.replace('_',' ').title() }}</span><br>
    <a href="/watch/{{ key }}" style="color:#0ff;">▶ Watch</a> |
    <a href="/audio/{{ key }}" style="color:#ff0;">🎵 Audio</a>
</div>
{% endfor %}
</div>

<div id="youtube" class="grid hidden">
{% for key in youtube_channels %}
<div class="card">
    <img src="{{ logos.get(key) }}">
    <span>{{ key.replace('_',' ').title() }}</span><br>
    <a href="/watch/{{ key }}" style="color:#0ff;">▶ Watch</a> |
    <a href="/audio/{{ key }}" style="color:#ff0;">🎵 Audio</a>
</div>
{% endfor %}
</div>
</body>
</html>
"""
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

# -----------------------
# Watch Route
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]
    all_channels = tv_channels + live_youtube

    if channel not in all_channels:
        abort(404)

    video_url = f"/stream240/{channel}"
    current_index = all_channels.index(channel)
    prev_channel = all_channels[(current_index - 1) % len(all_channels)]
    next_channel = all_channels[(current_index + 1) % len(all_channels)]

    # NOTE: we now point the <video> directly at /stream240 which serves fragmented MP4
    html = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel.replace('_',' ').title()}</title>
<style>
body {{ background:#000; color:#fff; text-align:center; margin:0; padding:10px; }}
video {{ width:95%; max-width:720px; height:auto; background:#000; border:1px solid #333; }}
a {{ color:#0f0; text-decoration:none; margin:10px; display:inline-block; font-size:18px; }}
</style>
<script>
document.addEventListener("keydown", function(e) {{
  const v=document.getElementById("player");
  if(e.key==="4")window.location.href="/watch/{prev_channel}";
  if(e.key==="6")window.location.href="/watch/{next_channel}";
  if(e.key==="0")window.location.href="/";
  if(e.key==="5"&&v){{v.paused?v.play():v.pause();}}
  if(e.key==="9")window.location.reload();
}});
window.addEventListener('load', function() {{
  const video = document.getElementById('player');
  // Use direct fMP4 source
  video.src = "{video_url}";
  video.setAttribute('playsinline', '');
  video.autoplay = true;
  // Attempt to play on load
  video.play().catch(()=>{{/* autoplay might be blocked until user gesture */}});
}});
</script>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video id="player" controls></video>
<div style="margin-top:15px;">
  <a href="/">⬅ Home</a>
  <a href="/watch/{prev_channel}">⏮ Prev</a>
  <a href="/watch/{next_channel}">⏭ Next</a>
  <a href="/watch/{channel}" style="color:#0ff;">🔄 Reload</a>
</div>
</body>
</html>"""
    return html

# -----------------------
# Proxy Stream (m3u8 passthrough) - unchanged
# -----------------------
@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return f"Error fetching stream: {e}", 502

    content_type = r.headers.get("Content-Type", "application/vnd.apple.mpegurl")
    return Response(r.content, content_type=content_type)

# -----------------------
# Audio-only (unchanged)
# -----------------------
@app.route("/audio/<channel>")
def audio_only(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    filename = f"{channel}.mp3"

    def generate():
        cmd = [
            "ffmpeg", "-i", url,
            "-vn",               # no video
            "-ac", "1",          # mono
            "-b:a", "40k",       # 40kbps
            "-f", "mp3",
            "pipe:1"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                data = proc.stdout.read(4096)
                if not data:
                    break
                yield data
        finally:
            proc.terminate()

    return Response(
        generate(),
        mimetype="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# -----------------------
# 240p Transcoding Stream (FIXED)
# -----------------------
@app.route("/stream240/<channel>")
def stream240(channel):
    url = TV_STREAMS.get(channel) or CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    # Build FFmpeg command optimized for low-latency fragmented MP4 (fMP4)
    def generate():
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "info",

            # input
            "-re",               # read input at native rate (helps with some live sources)
            "-i", url,

            # video: scale and encode
            "-vf", "scale=426:240:flags=bicubic",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-profile:v", "baseline",
            "-level", "3.0",
            "-b:v", "300k",
            "-maxrate", "300k",
            "-bufsize", "600k",

            # audio: aac (widely supported)
            "-c:a", "aac",
            "-ac", "1",
            "-ar", "44100",
            "-b:a", "48k",

            # muxer: fragmented mp4 for streaming over HTTP
            "-movflags", "frag_keyframe+empty_moov+default_base_moof+faststart",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-max_muxing_queue_size", "9999",

            # format and pipe
            "-f", "mp4",
            "pipe:1"
        ]

        logging.info("Starting ffmpeg: " + " ".join(ffmpeg_cmd))
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            preexec_fn=os.setsid  # allow killing the whole process group
        )

        # start thread to read and log stderr (non-blocking)
        def stderr_reader():
            for raw in proc.stderr:
                try:
                    line = raw.decode(errors="ignore").rstrip()
                except Exception:
                    line = str(raw)
                logging.info("[FFMPEG] " + line)
        t = threading.Thread(target=stderr_reader, daemon=True)
        t.start()

        try:
            # read and yield in reasonably sized chunks (32KB)
            while True:
                chunk = proc.stdout.read(32 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            # try to terminate ffmpeg gracefully, then force kill if needed
            try:
                logging.info("Terminating ffmpeg (pid=%s)", proc.pid)
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                # give it a moment
                proc.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass

    # Use stream_with_context so Flask closes generator on client disconnect
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        # Transfer-Encoding often set by WSGI server; explicit doesn't hurt here
        "Transfer-Encoding": "chunked",
    }

    return Response(
        stream_with_context(generate()),
        mimetype="video/mp4",
        headers=headers,
        direct_passthrough=True
    )

# -----------------------
# Run Server
# -----------------------
if __name__ == "__main__":
    # reduce Werkzeug log spam
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    app.run(host="0.0.0.0", port=8000, debug=False)