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
    
    "france_24": "https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_500.m3u8",
    
    "mult": "http://stv.mediacdn.ru/live/cdn/mult/playlist.m3u8",

"radio_jornal": "https://player-ne10-radiojornal-app.stream.uol.com.br/live/radiojornalrecifeapp.m3u8",

"star_sports1": "http://87.255.35.150:18828/",


"star_sports2": "http://116.90.120.149:8000/play/a0ba/index.m3u8,

"star_sports3": "http://116.90.120.149:8000/play/a0bv/index.m3u8,

"star_sports4": "http://116.90.120.149:8000/play/a0cs/index.m3u8",

star_sports5": "http://87.255.35.150:18804/",


     
}



# -----------------------
# YouTube Live Channels
# -----------------------
YOUTUBE_STREAMS = {

"entri_degree": "https://www.youtube.com/@EntriDegreeLevelExams/live",

"kas_ranker": "https://www.youtube.com/@freepscclasses/live",

    "asianet_news": "https://www.youtube.com/@asianetnews/live",

    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",

"suprabhatam": "https://www.youtube.com/@suprabhaatham_online/live",

    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
    
    
    "eft_guru": "https://www.youtube.com/@EFTGuru-ql8dk/live",
    
    "aljazeera_english": "https://www.youtube.com/@AlJazeeraEnglish/live",
    
    


}

# -----------------------
# Channel Logos
# -----------------------
CHANNEL_LOGOS = {

"star_sports": "https://imgur.com/5En7pOI.png",


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
# Extract YouTube HLS URL
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
# Background refresh thread
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
# Home Page (with visible tabs)
# -----------------------
@app.route("/")
def home():
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [n for n, live in LIVE_STATUS.items() if live]

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📺 Live TV & YouTube Channels</title>
<style>
body {
  font-family: system-ui, sans-serif;
  background: #0e0e0e;
  color: #fff;
  margin: 0;
  padding: 0;
}
h1 {
  text-align: center;
  font-size: 1.8rem;
  margin: 20px 0 10px;
}
.tabs {
  display: flex;
  justify-content: center;
  background: #111;
  padding: 10px;
  border-bottom: 1px solid #222;
}
.tab {
  padding: 10px 20px;
  cursor: pointer;
  border-radius: 10px;
  background: #222;
  color: #0ff;
  margin: 0 6px;
  font-weight: 600;
  transition: all 0.25s ease;
}
.tab.active {
  background: #0ff;
  color: #000;
  transform: scale(1.05);
}
.search-container {
  text-align: center;
  margin: 12px 0;
}
.search-container input {
  width: 80%;
  max-width: 400px;
  padding: 10px 12px;
  font-size: 1rem;
  border-radius: 8px;
  border: none;
  outline: none;
  background: #1b1b1b;
  color: #0ff;
  text-align: center;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 18px;
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.card {
  background: #1b1b1b;
  border-radius: 18px;
  text-align: center;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 3px 8px rgba(0, 255, 255, 0.1);
  position: relative;
}
.card:hover {
  transform: scale(1.06);
  box-shadow: 0 5px 15px rgba(0,255,255,0.4);
}
.card img {
  width: 100%;
  height: 100px;
  object-fit: contain;
  background: #111;
  padding: 10px;
  transition: transform 0.3s ease;
  border-bottom: 1px solid #222;
}
.card:hover img {
  transform: scale(1.1);
}
.card span {
  display: block;
  font-size: 0.95rem;
  margin-top: 8px;
  font-weight: 600;
  color: #fff;
}
.links {
  margin: 10px 0 14px;
}
.links a {
  color: #0ff;
  margin: 0 6px;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.2s;
}
.links a:hover {
  color: #ff0;
}
.live-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #ff1744;
  color: white;
  font-size: 0.75rem;
  padding: 3px 6px;
  border-radius: 6px;
  font-weight: bold;
  letter-spacing: 0.5px;
}
.hidden { display: none; }
</style>

<script>
function showTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.grid').forEach(g => g.classList.add('hidden'));
  document.getElementById(tab).classList.remove('hidden');
  document.getElementById('tab_' + tab).classList.add('active');
  document.getElementById("search").value = "";
  filterChannels(""); // reset search
}

function filterChannels(value) {
  const term = value.toLowerCase();
  document.querySelectorAll('.card').forEach(card => {
    const name = card.getAttribute('data-name');
    if (!term || name.includes(term)) card.style.display = '';
    else card.style.display = 'none';
  });
}

window.onload = () => showTab('tv');
</script>
</head>

<body>
  <h1>📡 Live TV & YouTube Streams</h1>

  <div class="tabs">
    <div class="tab active" id="tab_tv" onclick="showTab('tv')">📺 TV Channels</div>
    <div class="tab" id="tab_youtube" onclick="showTab('youtube')">▶ YouTube Live</div>
  </div>

  <div class="search-container">
    <input type="text" id="search" onkeyup="filterChannels(this.value)" placeholder="🔍 Search channels...">
  </div>

  <div id="tv" class="grid">
  {% for key in tv_channels %}
    <div class="card" data-name="{{ key.replace('_',' ').lower() }}">
      <img src="{{ logos.get(key) }}" alt="{{ key }}">
      <span>{{ key.replace('_',' ').title() }}</span>
      <div class="links">
        <a href="/watch/{{ key }}">▶ Watch</a>
        <a href="/audio/{{ key }}">🎵 Audio</a>
      </div>
    </div>
  {% endfor %}
  </div>

  <div id="youtube" class="grid hidden">
  {% for key in youtube_channels %}
    <div class="card" data-name="{{ key.replace('_',' ').lower() }}">
      <div class="live-badge">LIVE 🔴</div>
      <img src="{{ logos.get(key) }}" alt="{{ key }}">
      <span>{{ key.replace('_',' ').title() }}</span>
      <div class="links">
        <a href="/watch/{{ key }}">▶ Watch</a>
        <a href="/audio/{{ key }}">🎵 Audio</a>
      </div>
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

    video_url = TV_STREAMS.get(channel, f"/stream/{channel}")
    current_index = all_channels.index(channel)
    prev_channel = all_channels[(current_index - 1) % len(all_channels)]
    next_channel = all_channels[(current_index + 1) % len(all_channels)]

    html = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel.replace('_',' ').title()}</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
body {{ background:#000; color:#fff; text-align:center; margin:0; padding:10px; }}
video {{ width:95%; max-width:720px; height:auto; background:#000; border:1px solid #333; }}
a {{ color:#0f0; text-decoration:none; margin:10px; display:inline-block; font-size:18px; }}
</style>
<script>
document.addEventListener("DOMContentLoaded", function() {{
  const video = document.getElementById("player");
  const src = "{video_url}";
  if (video.canPlayType("application/vnd.apple.mpegurl")) {{
    video.src = src;
  }} else if (Hls.isSupported()) {{
    const hls = new Hls({{lowLatencyMode:true}});
    hls.loadSource(src);
    hls.attachMedia(video);
  }} else {{
    alert("⚠️ Browser cannot play HLS stream.");
  }}
}});
document.addEventListener("keydown", function(e) {{
  const v=document.getElementById("player");
  if(e.key==="4")window.location.href="/watch/{prev_channel}";
  if(e.key==="6")window.location.href="/watch/{next_channel}";
  if(e.key==="0")window.location.href="/";
  if(e.key==="5"&&v){{v.paused?v.play():v.pause();}}
  if(e.key==="9")window.location.reload();
}});
</script>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video id="player" controls autoplay playsinline></video>
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
# Proxy Stream
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
            "-b:a", "40k",       # 64kbps
            "-f", "mp3",
            "pipe:1"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                data = proc.stdout.read(1024)
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
# Run Server
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)