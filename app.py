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
    # Countries special (API to get list)
    "🌍 Countries": "https://iptv-org.github.io/api/countries.json"
}

TV_STREAMS = {}         # category_name -> {channel_key: info}
COUNTRY_STREAMS = {}    # country_code -> {country: name, channels: {...}}
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",

"asianet_news": "https://www.youtube.com/@asianetnews/live",

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
    "kas_ranker": "https://www.youtube.com/@kasrankerofficial/live",
}

CHANNEL_LOGOS = {k: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for k in YOUTUBE_STREAMS}
CACHE = {}
LIVE_STATUS = {}
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# UTIL: parse .m3u text into channels dict
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
# Refresh IPTV categories + countries
# -----------------------
def refresh_iptv():
    global TV_STREAMS, COUNTRY_STREAMS
    all_categories = {}
    countries_map = {}
    # load normal categories
    for group, url in IPTV_SOURCES.items():
        if group == "🌍 Countries":
            continue
        all_categories[group] = load_iptv_channels(url)
    # load countries list and per-country m3u
    try:
        api_url = IPTV_SOURCES.get("🌍 Countries")
        if api_url:
            resp = requests.get(api_url, timeout=20)
            if resp.status_code == 200:
                countries = resp.json()
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
    # cache
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump({"tv": TV_STREAMS, "countries": COUNTRY_STREAMS}, f)
    except Exception:
        logging.exception("Failed writing cache")
    logging.info("📡 IPTV cache updated (categories + countries)")

# Load cache if exists
if os.path.exists(CACHE_PATH):
    try:
        with open(CACHE_PATH, "r") as f:
            raw = json.load(f)
            TV_STREAMS = raw.get("tv", {})
            COUNTRY_STREAMS = raw.get("countries", {})
            logging.info("Loaded IPTV cache from disk")
    except Exception:
        logging.exception("Failed to load cache; refreshing")
        refresh_iptv()
else:
    refresh_iptv()

# Periodic refresh thread
def periodic_refresh():
    while True:
        try:
            refresh_iptv()
        except Exception:
            logging.exception("Periodic refresh failed")
        time.sleep(12 * 3600)

threading.Thread(target=periodic_refresh, daemon=True).start()

# -----------------------
# YouTube Live refresh (same as before)
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
# Home: main grid of categories (SVG icons) and inline expansion
# -----------------------
@app.route("/")
def home():
    # mapping of categories to simple inline SVG icons (you can replace with more detailed svgs)
    category_svgs = {
        "⭐ Favourites": """<svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 17.3l6.16 3.24-1.64-7.03L21 9.24l-7.19-.62L12 2 10.19 8.62 3 9.24l4.48 4.27L5.84 20.54 12 17.3z" fill="currentColor"/></svg>""",
        "▶ YouTube": """<svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 15l5.2-3L10 9v6z" fill="currentColor"/><path d="M21 7s-.2-1.4-.8-2c-.8-.8-1.7-.8-2.1-.9C15.4 4 12 4 12 4s-3.5 0-5.9.1c-.4 0-1.3 0-2.1.9C3.2 5.6 3 7 3 7S2.9 9.1 2.9 11.2v1.6C2.9 15 3 17 3 17s.2 1.4.8 2c.8.8 1.9.8 2.4.9 1.8.2 7.9.2 7.9.2s3.5 0 5.9-.1c.4 0 1.3 0 2.1-.9.6-.6.8-2 .8-2s.1-2.1.1-4.2v-1.6C21.1 9.1 21 7 21 7z" fill="currentColor"/></svg>""",
        "🇮🇳 India": """<svg width="40" height="40" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="4" fill="currentColor"/></svg>""",
        "🗣️ Malayalam": """<svg width="40" height="40" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/></svg>""",
        "🕌 Religious": """<svg width="40" height="40" viewBox="0 0 24 24"><path d="M12 2 L2 7v7c0 5 5 8 10 8s10-3 10-8V7l-10-5z" fill="currentColor"/></svg>""",
        "📰 News": """<svg width="40" height="40" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2" fill="currentColor"/></svg>""",
        "⚽ Sports": """<svg width="40" height="40" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>""",
        "🎬 Entertainment": """<svg width="40" height="40" viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="2" fill="currentColor"/></svg>""",
        "🎓 Education": """<svg width="40" height="40" viewBox="0 0 24 24"><path d="M12 2 L2 7l10 5 10-5-10-5z" fill="currentColor"/></svg>""",
        "🎵 Music": """<svg width="40" height="40" viewBox="0 0 24 24"><path d="M9 17V5l10-2v12" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>""",
        "🎥 Movies": """<svg width="40" height="40" viewBox="0 0 24 24"><rect x="3" y="6" width="14" height="12" rx="2" fill="currentColor"/></svg>""",
        "🧒 Kids": """<svg width="40" height="40" viewBox="0 0 24 24"><circle cx="12" cy="8" r="3" fill="currentColor"/><rect x="7" y="13" width="10" height="6" rx="3" fill="currentColor"/></svg>""",
        "🌍 Countries": """<svg width="40" height="40" viewBox="0 0 24 24"><path d="M12 2a10 10 0 100 20 10 10 0 000-20z" fill="currentColor"/></svg>"""
    }

    # build a list of top-level categories (put favourites and youtube first)
    categories = ["⭐ Favourites", "▶ YouTube"] + [g for g in IPTV_SOURCES.keys() if g != "🌍 Countries"] + ["🌍 Countries"]

    html = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📺 IPTV - Categories</title>
<style>
:root{--bg:#0b0b0b;--panel:#121212;--accent:#0ff;--muted:#888;--gap:12px}
body{background:var(--bg);color:#fff;font-family:system-ui;margin:0;padding:12px}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
h1{margin:0;color:var(--accent);font-size:1.05rem}
.search input{padding:8px 12px;width:220px;background:#161616;border-radius:8px;border:0;color:var(--accent)}
.main-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px}
.tile{background:var(--panel);border-radius:12px;padding:14px;text-align:center;cursor:pointer;box-shadow:0 0 8px rgba(0,255,255,0.03);transition:transform .12s}
.tile:hover{transform:translateY(-4px)}
.tile .icon{width:48px;height:48px;margin:0 auto 8px;color:var(--accent)}
.tile .title{font-size:0.95rem;margin-bottom:4px}
.tile .sub{font-size:0.82rem;color:var(--muted)}
.backbtn{background:transparent;border:0;color:var(--accent);cursor:pointer;margin-bottom:10px}
.section{margin-top:14px}
.subgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.card{background:#0f0f0f;border-radius:10px;padding:8px;text-align:center;position:relative}
.card img{width:100%;height:70px;object-fit:contain;background:#000;padding:6px;border-radius:6px}
.card .title{font-size:0.86rem;padding:6px}
.card .links{font-size:0.85rem;padding-bottom:6px}
.fav{position:absolute;top:8px;right:8px;font-size:16px;cursor:pointer}
.fav.active{color:#ff0}
.small{font-size:0.82rem;color:var(--muted)}
.country-tile{display:flex;align-items:center;gap:10px;justify-content:space-between;padding:10px;background:#111;border-radius:10px}
.country-tile .left{display:flex;gap:10px;align-items:center}
.country-tile .code{font-size:0.85rem;color:var(--muted)}
.hide{display:none}
</style>
<script>
// We'll render categories -> subgrids entirely client-side using data embedded in the page.
let TV_STREAMS = {{ tv_streams | tojson }};
let COUNTRY_STREAMS = {{ countries | tojson }};
let YOUTUBE_LIVE = {{ youtube_live | tojson }};
let LOGOS = {{ logos | tojson }};

function createSVG(svgStr){
  const wrapper = document.createElement('div');
  wrapper.innerHTML = svgStr;
  return wrapper.firstElementChild;
}

function onCategoryClick(cat){
  // show category view and hide home grid
  document.getElementById('home_view').classList.add('hide');
  document.getElementById('category_view').classList.remove('hide');
  document.getElementById('category_title').innerText = cat;
  document.getElementById('category_subtitle').innerText = '';
  // render
  const container = document.getElementById('category_container');
  container.innerHTML = '';
  if(cat === '⭐ Favourites'){
    renderFavouritesGrid(container);
    return;
  }
  if(cat === '▶ YouTube'){
    renderYouTubeGrid(container);
    return;
  }
  if(cat === '🌍 Countries'){
    renderCountriesList(container);
    return;
  }
  // normal category from TV_STREAMS by matching key exactly
  const channels = TV_STREAMS[cat] || {};
  if(Object.keys(channels).length === 0){
    container.innerHTML = '<p class="small">No channels found in this category.</p>';
    return;
  }
  renderChannels(container, channels);
}

function backHome(){
  document.getElementById('category_view').classList.add('hide');
  document.getElementById('home_view').classList.remove('hide');
  // reset search filter
  const s = document.getElementById('search_input'); if(s) s.value = '';
  searchAll('');
}

function renderChannels(container, channels){
  const grid = document.createElement('div'); grid.className = 'subgrid';
  Object.entries(channels).forEach(([key, info])=>{
    const c = document.createElement('div'); c.className = 'card'; c.setAttribute('data-key', key); c.setAttribute('data-name', info.name || key);
    const fav = document.createElement('div'); fav.className = 'fav'; fav.setAttribute('data-key', key); fav.innerText = '⭐'; fav.onclick = ()=>toggleFav(key);
    c.appendChild(fav);
    const img = document.createElement('img'); img.src = info.logo || 'https://i.imgur.com/BsC6z9S.png';
    c.appendChild(img);
    const title = document.createElement('div'); title.className = 'title'; title.innerText = info.name || key;
    c.appendChild(title);
    const links = document.createElement('div'); links.className = 'links';
    const a1 = document.createElement('a'); a1.href = '/watch/' + key; a1.className='watch-link'; a1.innerText = '▶ Watch';
    const a2 = document.createElement('a'); a2.href = '/audio/' + key; a2.innerText = ' 🎵 Audio'; a2.style.marginLeft='8px';
    links.appendChild(a1); links.appendChild(a2);
    c.appendChild(links);
    grid.appendChild(c);
  });
  container.appendChild(grid);
  updateFavIcons();
}

function renderYouTubeGrid(container){
  const grid = document.createElement('div'); grid.className='subgrid';
  YOUTUBE_LIVE.forEach(key=>{
    const c = document.createElement('div'); c.className='card'; c.setAttribute('data-key', key); c.setAttribute('data-name', key);
    const fav = document.createElement('div'); fav.className='fav'; fav.setAttribute('data-key', key); fav.innerText='⭐'; fav.onclick = ()=>toggleFav(key);
    c.appendChild(fav);
    const img = document.createElement('img'); img.src = LOGOS[key] || 'https://i.imgur.com/BsC6z9S.png';
    c.appendChild(img);
    const title = document.createElement('div'); title.className='title'; title.innerText = key.replace(/_/g,' ');
    c.appendChild(title);
    const links = document.createElement('div'); links.className='links';
    const a1 = document.createElement('a'); a1.href = '/watch/' + key; a1.innerText = '▶ Watch';
    const a2 = document.createElement('a'); a2.href = '/audio/' + key; a2.innerText = ' 🎵 Audio'; a2.style.marginLeft='8px';
    links.appendChild(a1); links.appendChild(a2);
    c.appendChild(links);
    grid.appendChild(c);
  });
  container.appendChild(grid);
  updateFavIcons();
}

function renderFavouritesGrid(container){
  const favs = JSON.parse(localStorage.getItem('favs') || '[]');
  if(favs.length === 0){
    container.innerHTML = '<p class="small">No favourites yet. Add by tapping ⭐ on any channel.</p>';
    return;
  }
  const grid = document.createElement('div'); grid.className='subgrid';
  // attempt to find channel info from categories & countries
  favs.forEach(key=>{
    // search TV_STREAMS
    let info = findChannelInfo(key);
    if(info){
      const c = document.createElement('div'); c.className='card'; c.setAttribute('data-key', key); c.setAttribute('data-name', info.name || key);
      const fav = document.createElement('div'); fav.className='fav active'; fav.setAttribute('data-key', key); fav.innerText='⭐'; fav.onclick = ()=>toggleFav(key);
      c.appendChild(fav);
      const img = document.createElement('img'); img.src = info.logo || 'https://i.imgur.com/BsC6z9S.png';
      c.appendChild(img);
      const title = document.createElement('div'); title.className='title'; title.innerText = info.name || key;
      c.appendChild(title);
      const links = document.createElement('div'); links.className='links';
      const a1 = document.createElement('a'); a1.href = '/watch/' + key; a1.innerText = '▶ Watch';
      const a2 = document.createElement('a'); a2.href = '/audio/' + key; a2.innerText = ' 🎵 Audio'; a2.style.marginLeft='8px';
      links.appendChild(a1); links.appendChild(a2);
      c.appendChild(links);
      grid.appendChild(c);
    }
  });
  container.appendChild(grid);
}

function renderCountriesList(container){
  // show a list of country tiles (name + code). clicking opens the country's channels
  const fragment = document.createElement('div');
  fragment.className='section';
  const keys = Object.keys(COUNTRY_STREAMS).sort();
  if(keys.length === 0){
    fragment.innerHTML = '<p class="small">No countries available.</p>';
    container.appendChild(fragment);
    return;
  }
  // countries grid: simple list
  const list = document.createElement('div'); list.style.display='grid'; list.style.gap='8px';
  keys.forEach(cc=>{
    const meta = COUNTRY_STREAMS[cc];
    const t = document.createElement('div'); t.className='country-tile';
    const left = document.createElement('div'); left.className='left';
    const icon = document.createElement('div'); icon.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>'; icon.style.color='#0ff';
    const name = document.createElement('div'); name.innerHTML = `<div style="font-weight:600">${meta.country}</div><div class="code">${cc}</div>`;
    left.appendChild(icon); left.appendChild(name);
    const openBtn = document.createElement('button'); openBtn.innerText='Open'; openBtn.onclick = ()=>{ openCountryChannels(cc, meta.country); };
    t.appendChild(left); t.appendChild(openBtn);
    list.appendChild(t);
  });
  fragment.appendChild(list);
  container.appendChild(fragment);
}

function openCountryChannels(cc, cname){
  // show channels for a single country in the same category_view container
  document.getElementById('category_title').innerText = cname + ' (' + cc + ')';
  const container = document.getElementById('category_container');
  container.innerHTML = '';
  const meta = COUNTRY_STREAMS[cc];
  if(!meta || !meta.channels){
    container.innerHTML = '<p class="small">No channels for this country.</p>';
    return;
  }
  renderChannels(container, meta.channels);
}

function findChannelInfo(key){
  // search categories
  for(const g in TV_STREAMS){
    if(TV_STREAMS[g] && TV_STREAMS[g][key]) return TV_STREAMS[g][key];
  }
  // search countries
  for(const cc in COUNTRY_STREAMS){
    const chs = COUNTRY_STREAMS[cc].channels || {};
    if(chs[key]) return chs[key];
  }
  // check if it's a youtube key (we treat youtube keys as simple names)
  if(LOGOS[key] !== undefined){
    return {"name": key, "logo": LOGOS[key], "url": null};
  }
  return null;
}

function toggleFav(key){
  let favs = JSON.parse(localStorage.getItem('favs') || '[]');
  if(favs.includes(key)){
    favs = favs.filter(x=>x!==key);
  } else {
    favs.push(key);
  }
  localStorage.setItem('favs', JSON.stringify(favs));
  updateFavIcons();
}

function updateFavIcons(){
  const favs = JSON.parse(localStorage.getItem('favs') || '[]');
  document.querySelectorAll('.fav').forEach(el=>{
    const key = el.getAttribute('data-key');
    if(favs.includes(key)) el.classList.add('active'); else el.classList.remove('active');
  });
}

// search across home tiles and visible cards
function searchAll(term){
  term = (term || '').toLowerCase();
  // hide tiles that don't match (in home view)
  document.querySelectorAll('.tile').forEach(t=>{
    const name = (t.getAttribute('data-name')||'').toLowerCase();
    t.style.display = name.includes(term) ? '' : 'none';
  });
  // also hide channel cards if any open
  document.querySelectorAll('.card').forEach(c=>{
    const nm = (c.getAttribute('data-name')||'').toLowerCase();
    c.style.display = nm.includes(term) ? '' : 'none';
  });
}

</script>
</head>
<body>
<div class="header">
  <h1>📺 IPTV — Categories</h1>
  <div class="search"><input id="search_input" placeholder="Search categories or channels..." oninput="searchAll(this.value)"></div>
</div>

<!-- HOME GRID (categories as tiles) -->
<div id="home_view">
  <div class="main-grid">
    {% for cat in categories %}
      <div class="tile" onclick="onCategoryClick('{{ cat }}')" data-name="{{ cat }}">
        <div class="icon">{{ category_svgs.get(cat, '')|safe }}</div>
        <div class="title">{{ cat }}</div>
        <div class="sub small">
          {% if cat == '⭐ Favourites' %}Your starred channels{% elif cat == '▶ YouTube' %}Live YouTube streams{% elif cat == '🌍 Countries' %}Browse by country{% else %}Open category{% endif %}
        </div>
      </div>
    {% endfor %}
  </div>
</div>

<!-- CATEGORY VIEW (hidden by default) -->
<div id="category_view" class="hide">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
    <button class="backbtn" onclick="backHome()">🔙 Back</button>
    <div>
      <div id="category_title" style="font-weight:700"></div>
      <div id="category_subtitle" class="small"></div>
    </div>
  </div>
  <div id="category_container"></div>
</div>

</body>
</html>
"""
    return render_template_string(html,
                                  tv_streams=TV_STREAMS,
                                  countries=COUNTRY_STREAMS,
                                  youtube_live=[k for k,v in LIVE_STATUS.items() if v],
                                  logos=CHANNEL_LOGOS,
                                  category_svgs=category_svgs,
                                  categories=["⭐ Favourites", "▶ YouTube"] + [g for g in IPTV_SOURCES.keys() if g != "🌍 Countries"] + ["🌍 Countries"])

# -----------------------
# Helper: find channel URL
# -----------------------
def find_channel_url(channel_key):
    for group, chs in TV_STREAMS.items():
        if channel_key in chs:
            return chs[channel_key]["url"]
    for cc, meta in COUNTRY_STREAMS.items():
        chs = meta.get("channels", {})
        if channel_key in chs:
            return chs[channel_key]["url"]
    if channel_key in CACHE:
        return CACHE[channel_key]
    return None

# -----------------------
# Watch endpoint (works across categories and countries and youtube)
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    stream_url = f"/stream/{channel}"  # proxy always works
    html = f"""
<html>
<head>
<meta name='viewport' content='width=device-width,initial-scale=1.0'>
<title>{channel}</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script src="https://cdn.dashjs.org/latest/dash.all.min.js"></script>
<style>
  body {{
    background:#000;
    color:#0ff;
    text-align:center;
    font-family:sans-serif;
  }}
  video {{
    width:96%;
    max-width:720px;
    height:auto;
    background:#000;
  }}
  a {{
    color:#0ff;
    text-decoration:none;
  }}
</style>
</head>
<body>
<h3>{channel.replace('_',' ').title()}</h3>
<video id="v" controls autoplay></video>
<p><a href="/">🏠 Home</a></p>

<script>
document.addEventListener("DOMContentLoaded", function() {{
  const v = document.getElementById("v");
  const s = "{stream_url}";
  if (s.endsWith(".m3u8")) {{
    if (v.canPlayType("application/vnd.apple.mpegurl")) v.src = s;
    else if (Hls.isSupported()) {{
      const h = new Hls();
      h.loadSource(s);
      h.attachMedia(v);
    }}
  }} else if (s.endsWith(".mpd")) {{
    const player = dashjs.MediaPlayer().create();
    player.initialize(v, s, true);
  }} else {{
    v.src = s; // proxy mp4/mp3 stream
  }}
}});
</script>
</body>
</html>"""
    return html
# -----------------------
# Audio proxy (ffmpeg)
# -----------------------
@app.route("/audio/<channel>")
def audio(channel):
    url = find_channel_url(channel)
    if not url:
        return "Not ready", 503

    def generate():
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
