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
    "kas_ranker": "https://www.youtube.com/@freepscclasses/live",
}

# -----------------------
# Hardcoded Channel Logos
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
    **{key: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for key in YOUTUBE_STREAMS}
}

CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube Live URL (raw HLS)
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
# Background refresher thread
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
# Proxy HLS
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
# Main UI
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]

    html = """
<html>
<head>
<title>SPB TV Style</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { background:#222; color:#fff; font-family:sans-serif; margin:0; padding:0; text-align:center; }
.container { width:320px; height:240px; margin:20px auto; border:2px solid #444; background:#111; display:flex; flex-direction:column; border-radius:10px; overflow:hidden; }
.video-box { flex:3; background:#000; }
iframe { width:100%; height:100%; border:none; }
.info-bar { flex:0.8; background:#036; font-size:13px; display:flex; align-items:center; justify-content:center; color:#fff; }
.channel-bar { flex:1.2; background:#ddd; overflow-x:auto; white-space:nowrap; }
.channel-btn { display:inline-block; width:60px; text-align:center; padding:5px; background:#fff; border-right:1px solid #aaa; }
.channel-btn img { width:40px; height:30px; object-fit:contain; }
.channel-btn span { display:block; font-size:10px; color:#000; }
.hidden { display:none; }
.mode { text-align:center; font-size:16px; color:#0ff; margin-bottom:8px; }
</style>
<script>
let tv_channels = {{ tv_channels|tojson }};
let yt_channels = {{ youtube_channels|tojson }};
let mode = "tv";
let current = 0;

function showMode(m) {
  mode = m;
  document.getElementById("tv_box").classList.add("hidden");
  document.getElementById("yt_box").classList.add("hidden");
  document.getElementById(m + "_box").classList.remove("hidden");
  document.getElementById("mode").innerText = (m === "tv" ? "📺 TV Mode" : "▶ YouTube Mode");
  playChannel(0);
}

function playChannel(i) {
  current = i;
  let arr = (mode === "tv" ? tv_channels : yt_channels);
  let name = arr[i];
  let iframe = document.getElementById("player");
  iframe.src = "/watch_inline/" + name;
  document.getElementById("info").innerText = name.replaceAll("_"," ").toUpperCase();
}

document.addEventListener("keydown", e=>{
  let arr = (mode === "tv" ? tv_channels : yt_channels);
  if(e.key === "#"){ showMode(mode === "tv" ? "yt" : "tv"); }
  if(e.key === "4"){ playChannel((current-1+arr.length)%arr.length); }
  if(e.key === "6"){ playChannel((current+1)%arr.length); }
  if(!isNaN(e.key)){ playChannel(parseInt(e.key)%arr.length); }
});

window.onload = ()=>showMode("tv");
</script>
</head>
<body>
<h2 id="mode" class="mode">📺 TV Mode</h2>
<div class="container">
  <div class="video-box"><iframe id="player"></iframe></div>
  <div id="info" class="info-bar">Loading...</div>

  <div id="tv_box" class="channel-bar">
  {% for key in tv_channels %}
    <div class="channel-btn" onclick="playChannel({{ loop.index0 }})">
      <img src="{{ logos.get(key) }}">
      <span>{{ loop.index }}</span>
    </div>
  {% endfor %}
  </div>

  <div id="yt_box" class="channel-bar hidden">
  {% for key in youtube_channels %}
    <div class="channel-btn" onclick="playChannel({{ loop.index0 }})">
      <img src="{{ logos.get(key) }}">
      <span>{{ loop.index }}</span>
    </div>
  {% endfor %}
  </div>
</div>
</body>
</html>
"""
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

# -----------------------
# Inline player
# -----------------------
@app.route("/watch_inline/<channel>")
def watch_inline(channel):
    if channel in TV_STREAMS:
        src = TV_STREAMS[channel]
    elif channel in CACHE:
        src = f"/stream/{channel}"
    else:
        return "Not live", 503
    return f"<video controls autoplay width='100%' height='100%'><source src='{src}' type='application/vnd.apple.mpegurl'></video>"

# -----------------------
# Stream proxy for YouTube
# -----------------------
@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503
    return Response(stream_proxy(url), mimetype="application/vnd.apple.mpegurl")

# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)