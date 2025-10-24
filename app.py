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
    "🕌 Religious": "https://iptv-org.github.io/iptv/categories/religious.m3u",
    "📰 News": "https://iptv-org.github.io/iptv/categories/news.m3u",
    "⚽ Sports": "https://iptv-org.github.io/iptv/categories/sports.m3u",
    "🎬 Entertainment": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",
    "🎓 Education": "https://iptv-org.github.io/iptv/categories/education.m3u",
    "🎵 Music": "https://iptv-org.github.io/iptv/categories/music.m3u",
    "🎥 Movies": "https://iptv-org.github.io/iptv/categories/movies.m3u",
    "🧒 Kids": "https://iptv-org.github.io/iptv/categories/kids.m3u",
    # Countries handled specially (loads many country m3u files)
    "🌍 Countries": "https://iptv-org.github.io/api/countries.json"
}

TV_STREAMS = {}         # category_name -> {channel_key: info}
COUNTRY_STREAMS = {}    # country_code -> {channel_key: info}
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

CHANNEL_LOGOS = {k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# UTIL: parse .m3u file into channels dict
# -----------------------
def parse_m3u_text(text, prefix_key=None):
    channels = {}
    name, link, logo = None, None, None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            parts = line.split(",")
            name = parts[-1].strip()
            # capture tvg-logo if present
            if 'tvg-logo=' in line:
                try:
                    logo = line.split('tvg-logo="')[1].split('"')[0]
                except Exception:
                    logo = None
        elif line.startswith("http") or line.startswith("rtmp") or line.startswith("udp://") or line.startswith("mms://"):
            link = line
            if name:
                base_key = name.lower().replace(" ", "_").replace("/", "_")
                key = f"{prefix_key}_{base_key}" if prefix_key else base_key
                channels[key] = {"name": name, "url": link, "logo": logo}
                name, link, logo = None, None, None
    return channels

# -----------------------
# Load IPTV channels for a single URL
# -----------------------
def load_iptv_channels(url, prefix_key=None):
    channels = {}
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200 and resp.text:
            channels = parse_m3u_text(resp.text, prefix_key=prefix_key)
            logging.info(f"✅ Loaded {len(channels)} channels from {url}")
        else:
            logging.warning(f"⚠️ Empty/Bad response from {url} status={resp.status_code}")
    except Exception as e:
        logging.error(f"❌ IPTV load failed from {url}: {e}")
    return channels

# -----------------------
# Refresh IPTV (categories + countries)
# -----------------------
def refresh_iptv():
    global TV_STREAMS, COUNTRY_STREAMS, CACHE
    all_categories = {}
    countries_map = {}

    # load normal categories (except Countries)
    for group, url in IPTV_SOURCES.items():
        if group == "🌍 Countries":
            continue
        all_categories[group] = load_iptv_channels(url)

    # load countries list JSON from iptv-org API
    try:
        api_url = IPTV_SOURCES.get("🌍 Countries")
        if api_url:
            resp = requests.get(api_url, timeout=20)
            if resp.status_code == 200:
                countries = resp.json()  # list of country objects
                # For each country, attempt to load its country m3u by country code
                for c in countries:
                    code = c.get("iso2") or c.get("code") or c.get("id")
                    cname = c.get("name") or code
                    if not code:
                        continue
                    m3u_url = f"https://iptv-org.github.io/iptv/countries/{code.lower()}.m3u"
                    chs = load_iptv_channels(m3u_url, prefix_key=code.lower())
                    if chs:
                        countries_map[code.upper()] = {"country": cname, "channels": chs}
            else:
                logging.warning("⚠️ Could not fetch countries.json; status=%s", resp.status_code)
    except Exception as e:
        logging.error("❌ Error loading countries: %s", e)

    TV_STREAMS = all_categories
    COUNTRY_STREAMS = countries_map
    # cache both
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump({"tv": TV_STREAMS, "countries": COUNTRY_STREAMS}, f)
    except Exception:
        logging.exception("Failed writing cache")
    logging.info("📡 IPTV cache updated (categories + countries)")

# Load cached if available
if os.path.exists(CACHE_PATH):
    try:
        with open(CACHE_PATH, "r") as f:
            raw = json.load(f)
            TV_STREAMS = raw.get("tv", {})
            COUNTRY_STREAMS = raw.get("countries", {})
            logging.info("Loaded IPTV cache from disk")
    except Exception:
        logging.exception("Failed to load cache file; refreshing")
        refresh_iptv()
else:
    refresh_iptv()

# Periodic refresh (every 12 hours)
def periodic_refresh():
    while True:
        try:
            refresh_iptv()
        except Exception:
            logging.exception("Periodic refresh failed")
        time.sleep(12 * 3600)

threading.Thread(target=periodic_refresh, daemon=True).start()

# -----------------------
# YouTube Live Refresh
# -----------------------
def get_youtube_live_url(youtube_url):
    try:
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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
# HOME PAGE (grid-based)
# -----------------------
@app.route("/")
def home():
    html = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📺 IPTV + YouTube Live (Grids)</title>
<style>
:root{--bg:#0b0b0b;--panel:#1a1a1a;--accent:#0ff;--muted:#888;--gap:14px}
body{background:var(--bg);color:#fff;font-family:system-ui;margin:0;padding:10px}
h1{color:var(--accent);text-align:center;margin:6px 0 14px}
.section{margin-bottom:22px}
.section h2{margin:0 0 8px;font-size:1.05rem;color:var(--accent);display:flex;align-items:center;gap:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:var(--gap);padding:8px}
.card{background:var(--panel);border-radius:12px;overflow:hidden;text-align:center;padding-bottom:8px;position:relative;box-shadow:0 0 6px rgba(0,255,255,0.06);transition:transform .16s}
.card:hover{transform:scale(1.03)}
.card img{width:100%;height:80px;object-fit:contain;background:#000;padding:8px}
.card .title{padding:6px;font-size:0.9rem}
.card .links{padding:0 6px}
.links a{color:var(--accent);margin:0 6px;text-decoration:none;font-weight:bold}
.fav{position:absolute;top:8px;right:8px;font-size:18px;cursor:pointer}
.fav.active{color:#ff0}
.header-controls{display:flex;gap:8px;align-items:center;justify-content:center;margin-bottom:10px}
.search input{padding:8px 12px;width:70%;max-width:520px;background:#222;border:none;color:var(--accent);border-radius:8px}
.collapsible{background:transparent;border:none;color:var(--muted);cursor:pointer;font-size:0.95rem}
.country-meta{display:flex;gap:8px;align-items:center;font-size:0.95rem;color:var(--muted)}
.small{font-size:0.85rem;color:var(--muted)}
@media (max-width:420px){.search input{width:92%}}
</style>
<script>
function toggleFav(key){
  let favs = JSON.parse(localStorage.getItem('favs')||'[]');
  if(favs.includes(key)) favs = favs.filter(x=>x!==key);
  else favs.push(key);
  localStorage.setItem('favs', JSON.stringify(favs));
  updateFavIcons();
  renderFavourites();
}

function updateFavIcons(){
  const favs = JSON.parse(localStorage.getItem('favs')||'[]');
  document.querySelectorAll('.fav').forEach(el=>{
    const key = el.getAttribute('data-key');
    el.classList.toggle('active', favs.includes(key));
  });
}

function renderFavourites(){
  const favs = JSON.parse(localStorage.getItem('favs')||'[]');
  const favGrid = document.getElementById('section_favourites_grid');
  if(!favGrid) return;
  favGrid.innerHTML = '';
  // clone visible cards from the whole document
  document.querySelectorAll('.card[data-key]').forEach(c=>{
    const key = c.getAttribute('data-key');
    if(favs.includes(key)){
      favGrid.appendChild(c.cloneNode(true));
    }
  });
  if(favGrid.children.length===0){
    favGrid.innerHTML = '<p class="small" style="text-align:center;color:#888">No favourites yet ⭐</p>';
  }
  // reattach onclicks for cloned fav cards (watch/audio/fav)
  favGrid.querySelectorAll('.card').forEach(card=>{
    const btn = card.querySelector('.fav');
    if(btn){
      btn.onclick = function(){ toggleFav(card.getAttribute('data-key')) };
    }
  });
}

function searchAll(term){
  term = term.toLowerCase();
  document.querySelectorAll('.card').forEach(card=>{
    const name = (card.getAttribute('data-name')||'').toLowerCase();
    card.style.display = name.includes(term) ? '' : 'none';
  });
  renderFavourites();
}

function toggleCollapse(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.style.display = (el.style.display === 'none') ? '' : 'none';
}

window.addEventListener('DOMContentLoaded', ()=>{
  updateFavIcons();
  renderFavourites();
  const lastQuery = localStorage.getItem('lastSearch') || '';
  const searchInput = document.getElementById('search_input');
  if(searchInput){ searchInput.value = lastQuery; searchAll(lastQuery); }
  // delegate click re-attach for cloned elements (if any)
  document.body.addEventListener('click', function(e){
    if(e.target && e.target.matches && e.target.matches('.watch-link')){
      // nothing special; link will navigate
    }
  });
});

function onSearchInput(el){
  const v = el.value || '';
  localStorage.setItem('lastSearch', v);
  searchAll(v);
}
</script>
</head>
<body>
<h1>📺 IPTV + YouTube Live</h1>

<div class="header-controls">
  <div class="search"><input id="search_input" placeholder="🔍 Search channels across all grids..." oninput="onSearchInput(this)"></div>
</div>

<!-- FAVOURITES SECTION -->
<div class="section" id="section_favourites">
  <h2>⭐ Favourites</h2>
  <div id="section_favourites_grid" class="grid"></div>
</div>

<!-- YOUTUBE SECTION -->
<div class="section" id="section_youtube">
  <h2>▶ YouTube Live</h2>
  <div class="grid">
    {% for key in youtube_live %}
    <div class="card" data-key="{{ key }}" data-name="{{ key }}">
      <div class="fav" data-key="{{ key }}" onclick="toggleFav('{{ key }}')">⭐</div>
      <img src="{{ logos.get(key) }}" alt="{{ key }}">
      <div class="title">{{ key.replace('_',' ').title() }}</div>
      <div class="links">
        <a class="watch-link" href="/watch/{{ key }}">▶ Watch</a>
        <a href="/audio/{{ key }}">🎵 Audio</a>
      </div>
    </div>
    {% endfor %}
    {% if youtube_live|length == 0 %}
      <p class="small">No live YouTube streams detected right now.</p>
    {% endif %}
  </div>
</div>

<!-- NORMAL CATEGORIES -->
{% for group, channels in tv_streams.items() %}
  <div class="section" id="section_{{ loop.index }}">
    <h2>{{ group }} <button class="collapsible" onclick="toggleCollapse('grid_{{ loop.index }}')">[toggle]</button></h2>
    <div id="grid_{{ loop.index }}" class="grid">
      {% if channels %}
        {% for key, info in channels.items() %}
        <div class="card" data-key="{{ key }}" data-name="{{ key }}">
          <div class="fav" data-key="{{ key }}" onclick="toggleFav('{{ key }}')">⭐</div>
          <img src="{{ info.logo or 'https://i.imgur.com/BsC6z9S.png' }}" alt="{{ info.name }}">
          <div class="title">{{ info.name }}</div>
          <div class="links">
            <a class="watch-link" href="/watch/{{ key }}">▶ Watch</a>
            <a href="/audio/{{ key }}">🎵 Audio</a>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <p class="small">No channels in this category.</p>
      {% endif %}
    </div>
  </div>
{% endfor %}

<!-- COUNTRIES: show each country as its own small section under the Countries header -->
<div class="section" id="section_countries">
  <h2>🌍 Countries <button class="collapsible" onclick="toggleCollapse('countries_container')">[toggle]</button></h2>
  <div id="countries_container">
    {% if countries %}
      {% for cc, meta in countries.items() %}
        <div class="section">
          <div style="display:flex;align-items:center;justify-content:space-between">
            <div class="country-meta">
              <div style="font-size:1.05rem">{{ meta.country }} <span class="small">({{ cc }})</span></div>
            </div>
            <div><button class="collapsible" onclick="toggleCollapse('country_grid_{{ cc }}')">[toggle]</button></div>
          </div>
          <div id="country_grid_{{ cc }}" class="grid" style="margin-top:8px">
            {% for key, info in meta.channels.items() %}
            <div class="card" data-key="{{ key }}" data-name="{{ key }}">
              <div class="fav" data-key="{{ key }}" onclick="toggleFav('{{ key }}')">⭐</div>
              <img src="{{ info.logo or 'https://i.imgur.com/BsC6z9S.png' }}" alt="{{ info.name }}">
              <div class="title">{{ info.name }}</div>
              <div class="links">
                <a class="watch-link" href="/watch/{{ key }}">▶ Watch</a>
                <a href="/audio/{{ key }}">🎵 Audio</a>
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
      {% endfor %}
    {% else %}
      <p class="small">No country channels available.</p>
    {% endif %}
  </div>
</div>

</body>
</html>
"""
    # tv_streams passed as-is; countries uses COUNTRY_STREAMS
    return render_template_string(html,
                                  tv_streams=TV_STREAMS,
                                  countries=COUNTRY_STREAMS,
                                  youtube_live=[k for k,v in LIVE_STATUS.items() if v],
                                  logos=CHANNEL_LOGOS)

# -----------------------
# Helper to find a channel URL by key within categories and countries
# -----------------------
def find_channel_url(channel_key):
    # search categories
    for group, chs in TV_STREAMS.items():
        if channel_key in chs:
            return chs[channel_key]["url"]
    # search countries
    for cc, meta in COUNTRY_STREAMS.items():
        chs = meta.get("channels", {})
        if channel_key in chs:
            return chs[channel_key]["url"]
    # fallback to CACHE (for youtube urls stored by refresh_youtube)
    if channel_key in CACHE:
        return CACHE[channel_key]
    return None

# -----------------------
# Watch endpoint (works for categories, countries, youtube)
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    url = find_channel_url(channel)
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
# Audio Proxy (works for categories, countries, youtube)
# -----------------------
@app.route("/audio/<channel>")
def audio(channel):
    url = find_channel_url(channel)
    if not url:
        return "Not ready", 503

    def generate():
        # ffmpeg will read input URL and output mp3 stream
        cmd = ["ffmpeg", "-i", url, "-vn", "-ac", "1", "-b:a", "40k", "-f", "mp3", "pipe:1"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                data = p.stdout.read(1024)
                if not data:
                    break
                yield data
        finally:
            try:
                p.terminate()
            except Exception:
                pass

    return Response(generate(), mimetype="audio/mpeg")

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)