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
    "al_masira": "https://live.cdnbridge.tv/Almasirah/Almasirah_all/playlist.m3u8",
    "mubashir": "https://live2.cdnbridge.tv/AlmasirahMubasher/Mubasher_All/playlist.m3u8",
    
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
    # TV Logos
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
    "al_masira": "https://i.imgur.com/V055t5e.png",
    "mubashir": "https://i.imgur.com/0xHb3XM.jpg",

    # Default YouTube logo (replace with per-channel icons if available)
    **{key: "https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg" for key in YOUTUBE_STREAMS}
}

CACHE = {}        # Stores direct YouTube live URLs
LIVE_STATUS = {}  # Tracks which YouTube streams are currently live
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

    html = """
<html>
<head>
<title>📺 TV & YouTube Live</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: sans-serif; background:#111; color:#fff; margin:0; padding:20px; }
h2 { font-size:24px; text-align:center; margin-bottom:15px; }
.mode { text-align:center; font-size:18px; margin-bottom:10px; color:#0ff; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); gap:15px; }
.card { background:#222; border-radius:10px; padding:10px; text-align:center; }
.card img { width:100%; height:80px; object-fit:contain; margin-bottom:8px; }
.card span { display:block; font-size:14px; color:#0f0; }
.card a { text-decoration:none; color:inherit; }
.card:hover { background:#333; }
.hidden { display:none; }
</style>
<script>
let currentTab = "tv"; // default TV

function showTab(tabName) {
    document.getElementById("tv").classList.add("hidden");
    document.getElementById("youtube").classList.add("hidden");
    document.getElementById(tabName).classList.remove("hidden");
    currentTab = tabName;
    document.getElementById("mode").innerText = (tabName === "tv" ? "📺 TV Mode" : "▶ YouTube Mode");
}

document.addEventListener("keydown", function(e) {
    if (e.key === "#") {
        // toggle between TV and YouTube
        showTab(currentTab === "tv" ? "youtube" : "tv");
    } else if (!isNaN(e.key)) {
        let grid = document.getElementById(currentTab);
        let links = grid.querySelectorAll("a[data-index]");
        if (e.key === "0") {
            let rand = Math.floor(Math.random() * links.length);
            if (links[rand]) window.location.href = links[rand].href;
        } else {
            let index = parseInt(e.key) - 1;
            if (index >= 0 && index < links.length) {
                window.location.href = links[index].href;
            }
        }
    }
});

// default TV
window.onload = () => showTab("tv");
</script>
</head>
<body>
<h2>📺 Live Channels</h2>
<div id="mode" class="mode">📺 TV Mode</div>

<div id="tv" class="grid">
{% for key in tv_channels %}
<div class="card">
  <a href="/watch/{{ key }}" data-index="{{ loop.index0 }}">
    {% if logos.get(key) %}
      <img src="{{ logos.get(key) }}" alt="{{ key }}">
    {% endif %}
    <span>[{{ loop.index }}] {{ key.replace('_',' ').title() }}</span>
  </a>
</div>
{% endfor %}
</div>

<div id="youtube" class="grid hidden">
{% for key in youtube_channels %}
<div class="card">
  <a href="/watch/{{ key }}" data-index="{{ loop.index0 }}">
    {% if logos.get(key) %}
      <img src="{{ logos.get(key) }}" alt="{{ key }}">
    {% endif %}
    <span>[{{ loop.index }}] {{ key.replace('_',' ').title() }}</span>
  </a>
</div>
{% endfor %}
</div>

</body>
</html>"""
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

@app.route("/watch/<channel>")
def watch(channel):
    tv_channels = list(TV_STREAMS.keys())
    live_youtube = [name for name, live in LIVE_STATUS.items() if live]
    all_channels = tv_channels + live_youtube

    if channel not in all_channels:
        abort(404)

    if channel in TV_STREAMS:
        video_url = TV_STREAMS[channel]
    else:
        video_url = f"/stream/{channel}"

    current_index = all_channels.index(channel)
    prev_channel = all_channels[(current_index - 1) % len(all_channels)]
    next_channel = all_channels[(current_index + 1) % len(all_channels)]

    html = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel.replace('_',' ').title()}</title>
<style>
body {{ background:#000; color:#fff; text-align:center; padding:10px; }}
video {{ width:95%; max-width:700px; }}
a {{ color:#0f0; display:inline-block; margin:10px; font-size:20px; text-decoration:none; }}
</style>
<script>
document.addEventListener("keydown", function(e) {{
    let vid = document.querySelector("video");
    if (e.key === "4") {{
        window.location.href = "/watch/{prev_channel}";
    }}
    if (e.key === "6") {{
        window.location.href = "/watch/{next_channel}";
    }}
    if (e.key === "0") {{
        window.location.href = "/";
    }}
    if (e.key === "5" && vid) {{
        if (vid.paused) {{
            vid.play();
        }} else {{
            vid.pause();
        }}
    }}
    if (e.key === "9") {{
        window.location.reload();
    }}
}});

// Auto reload if stream stops or errors
window.addEventListener("load", function() {{
    let vid = document.querySelector("video");
    if (!vid) return;
    vid.addEventListener("error", function() {{
        console.log("⚠️ Video error, reloading...");
        setTimeout(() => window.location.reload(), 3000);
    }});
    vid.addEventListener("ended", function() {{
        console.log("⚠️ Video ended, reloading...");
        setTimeout(() => window.location.reload(), 3000);
    }});
}});
</script>
</head>
<body>
<h2>{channel.replace('_',' ').title()}</h2>
<video controls autoplay>
<source src="{video_url}" type="application/vnd.apple.mpegurl">
</video>
<div style="margin-top:20px;">
  <a href='/'>⬅ Back</a>
  <a href='/watch/{channel}' style="color:#0ff;">🔄 Refresh</a>
</div>
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
