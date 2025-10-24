import os
import time
import threading
import logging
import subprocess
import requests
import json
from flask import Flask, Response, render_template_string, abort

# -----------------------
# CONFIG
# -----------------------
LOG_PATH = "/mnt/data/tv.log"
CACHE_PATH = "/mnt/data/iptv_cache.json"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

# -----------------------
# IPTV Categories to Load
# -----------------------
IPTV_SOURCES = {
    "🇮🇳 India": "https://iptv-org.github.io/iptv/countries/in.m3u",
    "🗣️ Malayalam": "https://iptv-org.github.io/iptv/languages/mal.m3u",
    "🕌 Islamic": "https://iptv-org.github.io/iptv/categories/religious.m3u",
    "📰 News": "https://iptv-org.github.io/iptv/categories/news.m3u",
    "⚽ Sports": "https://iptv-org.github.io/iptv/categories/sports.m3u",
    "🎬 Entertainment": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",
    "🎓 Education": "https://iptv-org.github.io/iptv/categories/education.m3u",
    "📚 Infotainment": "https://iptv-org.github.io/iptv/categories/infotainment.m3u",
    "🎵 Music": "https://iptv-org.github.io/iptv/categories/music.m3u",
    "🎥 Movies": "https://iptv-org.github.io/iptv/categories/movies.m3u",
    "🧒 Kids": "https://iptv-org.github.io/iptv/categories/kids.m3u",
    "🌍 World": "https://iptv-org.github.io/iptv/index.m3u"
}

TV_STREAMS = {}
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    "entri_app": "https://www.youtube.com/@entriapp/live",
}

CHANNEL_LOGOS = {k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Load IPTV Channels
# -----------------------
def load_iptv_channels(url):
    channels = {}
    try:
        data = requests.get(url, timeout=15).text.splitlines()
        name, link, logo = None, None, None
        for line in data:
            if line.startswith("#EXTINF"):
                parts = line.split(",")
                name = parts[-1].strip()
                if 'tvg-logo=' in line:
                    logo = line.split('tvg-logo="')[1].split('"')[0]
            elif line.startswith("http"):
                link = line.strip()
                if name:
                    key = name.lower().replace(" ", "_")
                    channels[key] = {"name": name, "url": link, "logo": logo}
                    name, link, logo = None, None, None
        logging.info(f"✅ Loaded {len(channels)} from {url}")
    except Exception as e:
        logging.error(f"❌ IPTV load failed from {url}: {e}")
    return channels

def refresh_iptv():
    global TV_STREAMS
    all_channels = {}
    for group, url in IPTV_SOURCES.items():
        all_channels[group] = load_iptv_channels(url)
    TV_STREAMS.clear()
    TV_STREAMS.update(all_channels)
    with open(CACHE_PATH, "w") as f:
        json.dump(all_channels, f)
    logging.info("📡 IPTV cache updated")

# Load cached if available
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r") as f:
        TV_STREAMS = json.load(f)
else:
    refresh_iptv()

# Refresh IPTV every 12 hours
threading.Thread(target=lambda: (time.sleep(5), refresh_iptv()), daemon=True).start()

# -----------------------
# YouTube Live Refresh
# -----------------------
def get_youtube_live_url(youtube_url):
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

def refresh_youtube():
    while True:
        for name, url in YOUTUBE_STREAMS.items():
            live_url = get_youtube_live_url(url)
            if live_url:
                CACHE[name] = live_url
                LIVE_STATUS[name] = True
            else:
                LIVE_STATUS[name] = False
        time.sleep(300)

threading.Thread(target=refresh_youtube, daemon=True).start()

# -----------------------
# HOME PAGE
# -----------------------
@app.route("/")
def home():
    html = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌐 IPTV + YouTube Live</title>
<style>
body { background:#0b0b0b; color:white; font-family:system-ui; margin:0; }
h1 { text-align:center; margin:15px 0; color:#0ff; }
.tabs { display:flex; overflow-x:auto; background:#111; border-bottom:2px solid #0ff; }
.tab { flex:1; padding:10px; text-align:center; cursor:pointer; color:#0ff; font-weight:bold; white-space:nowrap; }
.tab.active { background:#0ff; color:#000; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(130px,1fr)); gap:15px; padding:15px; }
.card { background:#1a1a1a; border-radius:12px; text-align:center; overflow:hidden; box-shadow:0 0 5px rgba(0,255,255,0.3); transition:0.3s; position:relative; }
.card:hover { transform:scale(1.05); }
.card img { width:100%; height:80px; object-fit:contain; background:#000; }
.card span { display:block; padding:6px; font-size:0.9rem; }
.links a { color:#0ff; margin:0 4px; text-decoration:none; font-weight:bold; }
.hidden { display:none; }
.search { text-align:center; margin:10px; }
.search input { padding:8px 12px; width:80%; max-width:400px; background:#222; border:none; color:#0ff; border-radius:8px; }
.fav { position:absolute; top:6px; right:6px; cursor:pointer; font-size:18px; }
.fav.active { color:#ff0; }
</style>
<script>
function showTab(tab){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.grid').forEach(g=>g.classList.add('hidden'));
  document.getElementById(tab).classList.remove('hidden');
  document.getElementById('tab_'+tab).classList.add('active');
  localStorage.setItem('lastTab', tab);
}

function filter(v){
  const term=v.toLowerCase();
  document.querySelectorAll('.card').forEach(c=>{
    const n=c.getAttribute('data-name');
    c.style.display = n.includes(term)?'':'none';
  });
}

function toggleFav(key){
  let favs = JSON.parse(localStorage.getItem('favs')||'[]');
  if(favs.includes(key)){
    favs = favs.filter(x=>x!==key);
  }else{
    favs.push(key);
  }
  localStorage.setItem('favs', JSON.stringify(favs));
  renderFavs();
}

function renderFavs(){
  const favs = JSON.parse(localStorage.getItem('favs')||'[]');
  document.querySelectorAll('.fav').forEach(f=>{
    const key=f.getAttribute('data-key');
    f.classList.toggle('active', favs.includes(key));
  });
  const favGrid=document.getElementById('favourites');
  if(!favGrid)return;
  favGrid.innerHTML='';
  document.querySelectorAll('.card').forEach(c=>{
    if(favs.includes(c.getAttribute('data-name'))){
      favGrid.appendChild(c.cloneNode(true));
    }
  });
  if(favs.length===0){
    favGrid.innerHTML='<p style="text-align:center;color:#888;">No favourites yet ⭐</p>';
  }
}

window.addEventListener('DOMContentLoaded',()=>{
  const last = localStorage.getItem('lastTab') || 'g1';
  showTab(last);
  renderFavs();
});
</script>
</head>
<body>
<h1>📺 IPTV + YouTube Live</h1>
<div class="tabs">
  {% for group in tv_groups %}
    <div class="tab" id="tab_g{{ loop.index }}" onclick="showTab('g{{ loop.index }}')">{{ group }}</div>
  {% endfor %}
  <div class="tab" id="tab_youtube" onclick="showTab('youtube')">▶ YouTube</div>
  <div class="tab" id="tab_favourites" onclick="showTab('favourites')">⭐ Favourites</div>
</div>
<div class="search"><input type="text" onkeyup="filter(this.value)" placeholder="🔍 Search channels..."></div>

{% for group, channels in tv_streams.items() %}
<div class="grid {% if not loop.first %}hidden{% endif %}" id="g{{ loop.index }}">
  {% for key, info in channels.items() %}
  <div class="card" data-name="{{ key }}">
    <div class="fav" data-key="{{ key }}" onclick="toggleFav('{{ key }}')">⭐</div>
    <img src="{{ info.logo or 'https://i.imgur.com/BsC6z9S.png' }}" alt="{{ info.name }}">
    <span>{{ info.name }}</span>
    <div class="links">
      <a href="/watch/{{ key }}">▶</a>
      <a href="/audio/{{ key }}">🎵</a>
    </div>
  </div>
  {% endfor %}
</div>
{% endfor %}

<div class="grid hidden" id="youtube">
  {% for key in youtube_live %}
  <div class="card" data-name="{{ key }}">
    <div class="fav" data-key="{{ key }}" onclick="toggleFav('{{ key }}')">⭐</div>
    <img src="{{ logos.get(key) }}" alt="{{ key }}">
    <span>{{ key.replace('_',' ').title() }}</span>
    <div class="links">
      <a href="/watch/{{ key }}">▶</a>
      <a href="/audio/{{ key }}">🎵</a>
    </div>
  </div>
  {% endfor %}
</div>

<div class="grid hidden" id="favourites"></div>
</body>
</html>
"""
    return render_template_string(html, tv_streams=TV_STREAMS, tv_groups=list(TV_STREAMS.keys()),
                                  youtube_live=[k for k,v in LIVE_STATUS.items() if v],
                                  logos=CHANNEL_LOGOS)

# -----------------------
# Watch
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    for group, chs in TV_STREAMS.items():
        if channel in chs:
            url = chs[channel]["url"]
            break
    else:
        url = CACHE.get(channel)
        if not url:
            abort(404)
    html = f"""
<html><head><meta name='viewport' content='width=device-width,initial-scale=1.0'>
<title>{channel}</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>body{{background:#000;color:#0ff;text-align:center;}}video{{width:96%;max-width:720px;}}</style>
<script>
document.addEventListener("DOMContentLoaded",function(){{
const v=document.getElementById("v");
const s="{url}";
if(v.canPlayType("application/vnd.apple.mpegurl"))v.src=s;
else if(Hls.isSupported()){{const h=new Hls();h.loadSource(s);h.attachMedia(v);}}
}});
</script></head>
<body><h3>{channel.replace('_',' ').title()}</h3><video id="v" controls autoplay></video>
<p><a href="/">🏠 Home</a></p></body></html>"""
    return html

# -----------------------
# Audio Proxy
# -----------------------
@app.route("/audio/<channel>")
def audio(channel):
    for group, chs in TV_STREAMS.items():
        if channel in chs:
            url = chs[channel]["url"]
            break
    else:
        url = CACHE.get(channel)
        if not url:
            return "Not ready", 503

    def generate():
        cmd = ["ffmpeg", "-i", url, "-vn", "-ac", "1", "-b:a", "40k", "-f", "mp3", "pipe:1"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                data = p.stdout.read(1024)
                if not data: break
                yield data
        finally:
            p.terminate()
    return Response(generate(), mimetype="audio/mpeg")
    
# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)