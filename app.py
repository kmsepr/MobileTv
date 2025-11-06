import time
import threading
import logging
import subprocess
import os
import requests
from flask import Flask, Response, render_template_string, abort, jsonify

# =========================================================
# 🔧 Basic setup
# =========================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# =========================================================
# 📺 Direct TV Streams
# =========================================================
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
    "dd_malayalam": "https://d3eyhgoylams0m.cloudfront.net/v1/manifest/93ce20f0f52760bf38be911ff4c91ed02aa2fd92/ed7bd2c7-8d10-4051-b397-2f6b90f99acb/562ee8f9-9950-48a0-ba1d-effa00cf0478/2.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/chunks.m3u8",
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
}

# =========================================================
# ▶ YouTube Live Channels
# =========================================================
YOUTUBE_STREAMS = {
    "entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",
    "kas_ranker": "https://www.youtube.com/@freepscclasses/live",
    "asianet_news": "https://www.youtube.com/@asianetnews/live",
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "suprabhaatham": "https://www.youtube.com/@suprabhaatham_online/live",
}

# =========================================================
# 🖼 Channel Logos
# =========================================================
CHANNEL_LOGOS = {
    "safari_tv": "https://i.imgur.com/dSOfYyh.png",
    "victers_tv": "https://i.imgur.com/kj4OEsb.png",
    "france_24": "https://upload.wikimedia.org/wikipedia/commons/c/c1/France_24_logo_%282013%29.svg",
    "mazhavil_manorama": "https://i.imgur.com/fjgzW20.png",
    "dd_malayalam": "https://i.imgur.com/ywm2dTl.png",
    "dd_sports": "https://i.imgur.com/J2Ky5OO.png",
    **{k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
}

CACHE, LIVE_STATUS = {}, {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# =========================================================
# 🌍 IPTV ORG Data
# =========================================================
COUNTRIES_URL = "https://iptv-org.github.io/api/countries.json"
CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
IPTV_COUNTRIES, IPTV_CHANNELS = [], {}

def fetch_iptv_data():
    global IPTV_COUNTRIES, IPTV_CHANNELS
    try:
        c = requests.get(COUNTRIES_URL, timeout=10).json()
        ch = requests.get(CHANNELS_URL, timeout=60).json()
        IPTV_COUNTRIES = sorted(c, key=lambda x: x["name"])
        IPTV_CHANNELS = {}
        for x in ch:
            code = x.get("country")
            if not code or not x.get("url"):
                continue
            IPTV_CHANNELS.setdefault(code, []).append(x)
        logging.info(f"✅ IPTV loaded: {len(IPTV_COUNTRIES)} countries, {len(ch)} channels")
    except Exception as e:
        logging.error(f"⚠️ IPTV fetch failed: {e}")

threading.Thread(target=fetch_iptv_data, daemon=True).start()

# =========================================================
# 🧩 YouTube live HLS extraction
# =========================================================
def get_youtube_live_url(youtube_url: str):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None

def refresh_streams():
    while True:
        logging.info("🔁 Refreshing YouTube URLs...")
        for n, u in YOUTUBE_STREAMS.items():
            url = get_youtube_live_url(u)
            if url:
                CACHE[n] = url
                LIVE_STATUS[n] = True
            else:
                LIVE_STATUS[n] = False
        time.sleep(180)

threading.Thread(target=refresh_streams, daemon=True).start()

# =========================================================
# 🏠 Main Page
# =========================================================
@app.route("/")
def index():
    html = """
<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>📡 IPTV & YouTube Player</title>
<style>
body{font-family:sans-serif;background:#000;color:#fff;margin:0}
.tabs{display:flex;justify-content:center;background:#111}
.tab{padding:10px 16px;margin:3px;cursor:pointer;border-radius:8px;background:#222;color:#0ff}
.tab.active{background:#0ff;color:#000}
.grid{display:flex;flex-wrap:wrap;justify-content:center;padding:10px}
.card{width:150px;background:#111;margin:6px;padding:6px;border-radius:10px;text-align:center}
.card img{width:100%;height:90px;object-fit:contain;background:#fff;border-radius:6px}
button{background:#0ff;color:#000;border:none;border-radius:8px;padding:5px 10px;margin-top:6px;cursor:pointer}
.hidden{display:none}
</style>
<script>
function showTab(id){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.grid').forEach(g=>g.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
  document.getElementById('tab_'+id).classList.add('active');
}
async function loadCountry(code){
  showTab('channels');
  const r=await fetch('/api/country/'+code);
  const d=await r.json();
  const g=document.getElementById('channels');
  g.innerHTML='<h3>'+d.country+'</h3>';
  d.channels.forEach(c=>{
    g.innerHTML+=`
    <div class='card'>
      <img src='${c.logo||"https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg"}'>
      <div>${c.name}</div>
      <button onclick="window.open('/watch_url?url=${encodeURIComponent(c.url)}')">▶ Play</button>
    </div>`;});
}
window.onload=()=>showTab('tv');
</script></head>
<body>
<h2 style="text-align:center">📡 Live IPTV & YouTube</h2>
<div class="tabs">
  <div class="tab active" id="tab_tv" onclick="showTab('tv')">⭐Favourites</div>
  <div class="tab" id="tab_youtube" onclick="showTab('youtube')">▶ YouTube</div>
  <div class="tab" id="tab_country" onclick="showTab('country')">🌍 IPTV</div>
</div>

<div id="tv" class="grid">
{% for k,v in tv.items() %}
  <div class="card">
    <img src="{{ logos.get(k) }}">
    <div>{{ k.replace('_',' ').title() }}</div>
    <button onclick="window.open('/watch/{{ k }}')">▶ Watch</button>
  </div>
{% endfor %}
</div>

<div id="youtube" class="grid hidden">
{% for k in youtube %}
  <div class="card">
    <img src="{{ logos.get(k) }}">
    <div>{{ k.replace('_',' ').title() }}</div>
    <button onclick="window.open('/watch/{{ k }}')">▶ Watch</button>
  </div>
{% endfor %}
</div>

<div id="country" class="grid hidden">
{% for c in countries %}
  <div class="card" onclick="loadCountry('{{ c['code'] }}')">
    <img src="https://flagcdn.com/w80/{{ c['code']|lower }}.png">
    <div>{{ c['name'] }}</div>
  </div>
{% endfor %}
</div>

<div id="channels" class="grid hidden"></div>

</body></html>
"""
    return render_template_string(html, tv=TV_STREAMS, youtube=[k for k,v in LIVE_STATUS.items() if v], logos=CHANNEL_LOGOS, countries=IPTV_COUNTRIES)

# =========================================================
# ▶ API: IPTV by country
# =========================================================
@app.route("/api/country/<code>")
def country_api(code):
    chs = IPTV_CHANNELS.get(code.upper(), [])
    return jsonify({
        "country": next((c["name"] for c in IPTV_COUNTRIES if c["code"] == code.upper()), code),
        "channels": [{"name": c["name"], "logo": c.get("logo"), "url": c["url"]} for c in chs][:100]
    })

# =========================================================
# ▶ Watch route for all URLs
# =========================================================
@app.route("/watch_url")
def watch_url():
    url = request.args.get("url")
    if not url:
        abort(400)
    return f"""
<html><head><script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script></head>
<body style='background:black;text-align:center'>
<video id='v' controls autoplay style='width:95%;max-width:720px'></video>
<script>
const v=document.getElementById('v');const u="{url}";
if(v.canPlayType('application/vnd.apple.mpegurl'))v.src=u;
else if(Hls.isSupported()){{const h=new Hls();h.loadSource(u);h.attachMedia(v);}}
</script>
</body></html>"""

@app.route("/watch/<ch>")
def watch_channel(ch):
    url = TV_STREAMS.get(ch) or CACHE.get(ch)
    if not url:
        return "Not available", 503
    return watch_url.__wrapped__({"url": url})  # reuse logic

# =========================================================
# 🎧 Audio proxy
# =========================================================
@app.route("/audio/<ch>")
def audio_proxy(ch):
    url = TV_STREAMS.get(ch) or CACHE.get(ch)
    if not url:
        abort(404)
    def generate():
        cmd = ["ffmpeg", "-loglevel", "quiet", "-i", url, "-vn", "-ac", "1", "-ar", "44100", "-b:a", "40k", "-f", "mp3", "pipe:1"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        for chunk in iter(lambda: p.stdout.read(1024), b""):
            yield chunk
        p.terminate()
    return Response(generate(), mimetype="audio/mpeg")

# =========================================================
# 🚀 Run
# =========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)