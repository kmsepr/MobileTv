import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort, stream_with_context
import subprocess, os, requests, re

# ------------------------------------------------
# LOGGING & APP SETUP
# ------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# ------------------------------------------------
# TV STREAMS (DIRECT M3U8)
# ------------------------------------------------
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

# ------------------------------------------------
# YOUTUBE LIVE CHANNELS
# ------------------------------------------------
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

# ------------------------------------------------
# LOGOS
# ------------------------------------------------
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

CACHE = {}        # Cached YouTube direct HLS URLs
LIVE_STATUS = {}  # Live status flags
COOKIES_FILE = "/mnt/data/cookies.txt"

# ------------------------------------------------
# Extract YouTube HLS URL
# ------------------------------------------------
def get_youtube_live_url(youtube_url: str):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd[1:1] = ["--cookies", COOKIES_FILE]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logging.error(f"Error getting YouTube URL for {youtube_url}: {e}")
    return None

# ------------------------------------------------
# Background refresh thread
# ------------------------------------------------
def refresh_stream_urls():
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        for name, url in YOUTUBE_STREAMS.items():
            direct_url = get_youtube_live_url(url)
            if direct_url:
                CACHE[name] = direct_url
                LIVE_STATUS[name] = True
            else:
                if name not in CACHE:
                    LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# ------------------------------------------------
# FFmpeg Audio Stream Generator
# ------------------------------------------------
def generate_audio_stream(source_url, channel_name):
    """Generate an MP3 audio stream (40 kbps mono) from the given source."""
    logging.info(f"Starting FFmpeg for {channel_name} audio stream.")

    ffmpeg_command = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",
        "-timeout", "5000000",
        "-user_agent", "Mozilla/5.0",
        "-i", source_url,
        "-vn",
        "-ac", "1",
        "-b:a", "40k",
        "-bufsize", "1M",
        "-f", "mp3",
        "-"
    ]

    try:
        process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for chunk in iter(lambda: process.stdout.read(4096), b''):
            if not chunk:
                break
            yield chunk
        process.wait()

        stderr_output = process.stderr.read().decode(errors="ignore")
        if process.returncode != 0:
            logging.error(f"FFmpeg failed for {channel_name}: {stderr_output}")
        else:
            logging.info(f"FFmpeg exited normally for {channel_name}.")

    except FileNotFoundError:
        logging.critical("FFmpeg not found in PATH.")
        raise
    except Exception as e:
        logging.error(f"Error streaming {channel_name}: {e}")

# ------------------------------------------------
# FLASK ROUTES
# ------------------------------------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [n for n, live in LIVE_STATUS.items() if live]

    html = """
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📺 Live Channels</title>
    <style>
    body{font-family:sans-serif;background:#111;color:#fff;margin:0;padding:20px;}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px;}
    .card{background:#222;border-radius:10px;padding:10px;text-align:center;}
    .card img{width:100%;height:80px;object-fit:contain;}
    a{color:#0f0;text-decoration:none;}
    </style>
    </head>
    <body>
    <h2>📺 TV Channels</h2>
    <div class="grid">
    {% for key in tv_channels %}
      <div class="card">
        <a href="/watch/{{ key }}"><img src="{{ logos.get(key) }}"><br>{{ key.replace('_',' ').title() }}</a>
        <br><a href="/audio/{{ key }}">🎧 Audio</a>
      </div>
    {% endfor %}
    </div>
    <h2>▶ YouTube Live</h2>
    <div class="grid">
    {% for key in youtube_channels %}
      <div class="card">
        <a href="/watch/{{ key }}"><img src="{{ logos.get(key) }}"><br>{{ key.replace('_',' ').title() }}</a>
        <br><a href="/audio/{{ key }}">🎧 Audio</a>
      </div>
    {% endfor %}
    </div>
    </body></html>
    """
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

@app.route("/watch/<channel>")
def watch(channel):
    all_channels = list(TV_STREAMS.keys()) + [n for n, live in LIVE_STATUS.items() if live]
    if channel not in all_channels:
        abort(404)
    src = TV_STREAMS.get(channel, f"/stream/{channel}")
    return f"""
    <html><head><meta name='viewport' content='width=device-width'>
    <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
    </head><body style='background:#000;color:#fff;text-align:center'>
    <h2>{channel}</h2>
    <video id='v' controls autoplay width='95%'></video>
    <script>
      const v=document.getElementById('v'),src='{src}';
      if(Hls.isSupported()){{const h=new Hls();h.loadSource(src);h.attachMedia(v);}}
      else v.src=src;
    </script></body></html>"""

@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503
    try:
        r = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        return Response(stream_with_context(r.iter_content(4096)), content_type=r.headers.get("Content-Type", "application/vnd.apple.mpegurl"))
    except Exception as e:
        logging.error(f"Proxy error: {e}")
        return f"Error fetching stream: {e}", 502

@app.route("/audio/<channel>")
def audio_stream(channel):
    if channel in TV_STREAMS:
        source_url = TV_STREAMS[channel]
    elif channel in YOUTUBE_STREAMS:
        source_url = CACHE.get(channel)
        if not source_url:
            if LIVE_STATUS.get(channel, False) is False:
                return f"{channel} is offline.", 503
            return f"{channel} not cached yet. Try again later.", 503
    else:
        abort(404)

    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', channel)
    return Response(
        stream_with_context(generate_audio_stream(source_url, channel)),
        mimetype="audio/mpeg",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.mp3"}
    )

# ------------------------------------------------
# RUN SERVER
# ------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)