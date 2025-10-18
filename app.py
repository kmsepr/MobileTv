import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort, stream_with_context
import subprocess, os, requests
import re # Import re for sanitizing channel name for filename

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

CACHE = {}        # Cached YouTube direct HLS URLs
LIVE_STATUS = {}  # Live status
COOKIES_FILE = "/mnt/data/cookies.txt"

# -----------------------
# Extract YouTube HLS URL
# -----------------------
def get_youtube_live_url(youtube_url: str):
    try:
        # Use yt-dlp to get the direct stream URL, prioritizing low-resolution video stream
        cmd = ["yt-dlp", "-f", "best[height<=360]", "-g", youtube_url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        logging.error(f"Error getting YouTube URL for {youtube_url}: {e}")
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
                # If cached URL exists, keep it in case of transient failure, but mark as potentially offline
                if name not in CACHE:
                     LIVE_STATUS[name] = False
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# --- AUDIO STREAMING FUNCTION ---
def generate_audio_stream(source_url, channel_name):
    """Generates an audio stream (MP3, 40kbps, mono) from a video source using FFmpeg."""
    logging.info(f"Starting FFmpeg for audio stream: {channel_name} (Source: {source_url})")
    
    # FFmpeg command: -i {source_url} -vn -c:a libmp3lame -b:a 40k -ac 1 -f mp3 pipe:1
    ffmpeg_command = [
        "ffmpeg", 
        "-loglevel", "error", 
        "-i", source_url, 
        "-vn", 
        "-c:a", "libmp3lame", 
        "-b:a", "40k", 
        "-ac", "1", 
        "-f", "mp3", 
        "pipe:1"
    ]
    
    try:
        process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        for chunk in iter(lambda: process.stdout.read(4096), b''):
            if not chunk:
                break
            yield chunk
            
        process.wait()
        stderr_output = process.stderr.read().decode('utf-8')
        
        if process.returncode != 0:
            logging.error(f"FFmpeg failed for {channel_name} (Return Code: {process.returncode}): {stderr_output}")
        else:
            logging.info(f"FFmpeg stream finished for {channel_name} gracefully.")

    except FileNotFoundError:
        logging.critical("FFmpeg is not installed or not in PATH.")
        raise
    except Exception as e:
        logging.error(f"Error during audio stream generation for {channel_name}: {e}")
        
# -----------------------
# Flask Routes
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
body { font-family:sans-serif; background:#111; color:#fff; margin:0; padding:20px; }
h2 { text-align:center; margin-bottom:10px; }
.mode { text-align:center; color:#0ff; margin-bottom:10px; font-size:18px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); gap:12px; margin-bottom: 20px;}
.card { background:#222; border-radius:10px; padding:10px; text-align:center; transition:0.2s; }
.card:hover { background:#333; }
.card img { width:100%; height:80px; object-fit:contain; margin-bottom:8px; }
.card span { font-size:14px; color:#0f0; }
.action-links { margin-top: 5px; font-size: 12px; }
.action-links a { color: #f0f; margin: 0 5px; text-decoration: underline; display: inline; }
.hidden { display:none; }
</style>
<script>
let currentTab="tv";
function showTab(tab){
  // Now only update the mode indicator, since both grids are always visible
  // The 'tab' system is maintained for the key navigation logic below
  document.getElementById("mode").innerText=(tab==="tv"?"📺 TV Mode - TV Channels":"▶ YouTube Mode - Live Channels");
  currentTab=tab;
}
document.addEventListener("keydown",function(e){
  // Switching between TV and YouTube for the key navigation context
  if(e.key==="#"){showTab(currentTab==="tv"?"youtube":"tv");}
  else if(!isNaN(e.key)){
    let grid_id = currentTab;
    // Special case to allow key navigation for both on the first load without pressing #
    if(e.key==="1" && currentTab==="tv"){
        // Check if the first channel is in the TV list
        let tv_links = document.getElementById("tv").querySelectorAll("a[data-index]");
        if(tv_links.length > 0) {
            window.location.href=tv_links[0].href;
            return;
        }
    }
    
    let grid=document.getElementById(grid_id);
    let links=grid.querySelectorAll("a[data-index]");
    if(e.key==="0"){let r=Math.floor(Math.random()*links.length);if(links[r])window.location.href=links[r].href;}
    else{let i=parseInt(e.key)-1;if(i>=0&&i<links.length)window.location.href=links[i].href;}
  }
});
window.onload=()=>showTab("tv");
</script>
</head>
<body>
<h2>📺 Live Channels</h2>
<div id="mode" class="mode">📺 TV Mode - TV Channels</div>

<h3>TV Channels</h3>
<div id="tv" class="grid">
{% for key in tv_channels %}
<div class="card">
  <a href="/watch/{{ key }}" data-index="{{ loop.index0 }}">
    <img src="{{ logos.get(key) }}">
    <span>[{{ loop.index }}] {{ key.replace('_',' ').title() }}</span>
  </a>
  <div class="action-links">
    <a href="/audio/{{ key }}">🎧 Audio</a>
  </div>
</div>
{% endfor %}
</div>

<h3>YouTube Live</h3>
<div id="youtube" class="grid"> {% for key in youtube_channels %}
<div class="card">
  <a href="/watch/{{ key }}" data-index="{{ loop.index0 }}">
    <img src="{{ logos.get(key) }}">
    <span>[{{ loop.index }}] {{ key.replace('_',' ').title() }}</span>
  </a>
  <div class="action-links">
    <a href="/audio/{{ key }}">🎧 Audio</a>
  </div>
</div>
{% endfor %}
</div>
</body>
</html>"""
    return render_template_string(html, tv_channels=tv_channels, youtube_channels=live_youtube, logos=CHANNEL_LOGOS)

# -----------------------
# Watch Route (HLS.js Player)
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
  <a href="/audio/{channel}" style="color:#f0f;">🎧 Audio</a>
</div>
</body>
</html>"""
    return html

# -----------------------
# Proxy Stream (YouTube)
# -----------------------
@app.route("/stream/<channel>")
def stream(channel):
    url = CACHE.get(channel)
    if not url:
        return "Channel not ready", 503

    # Directly proxy the YouTube HLS stream
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    try:
        r = requests.get(url, headers=headers, timeout=10, stream=True)
        r.raise_for_status()
    except Exception as e:
        logging.error(f"Error fetching YouTube HLS proxy: {e}")
        return f"Error fetching stream: {e}", 502

    content_type = r.headers.get("Content-Type", "application/vnd.apple.mpegurl")
    return Response(stream_with_context(r.iter_content(chunk_size=4096)), content_type=content_type)

# -----------------------
# Audio Stream Route (40kbps Mono MP3)
# -----------------------
@app.route("/audio/<channel>")
def audio_stream(channel):
    # Determine the source URL
    if channel in TV_STREAMS:
        source_url = TV_STREAMS[channel]
    elif channel in YOUTUBE_STREAMS:
        # For YouTube, use the cached direct HLS URL
        source_url = CACHE.get(channel)
        if not source_url:
            if LIVE_STATUS.get(channel, False) is False:
                 return f"YouTube channel '{channel.replace('_',' ').title()}' is not currently live or URL not cached.", 503
            else:
                 return f"YouTube channel '{channel.replace('_',' ').title()}' URL not cached yet. Try again in a minute.", 503
    else:
        abort(404)

    # Sanitize channel name for Content-Disposition filename
    sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '', channel)
    
    # Use stream_with_context to ensure Flask's request context is maintained
    return Response(
        stream_with_context(generate_audio_stream(source_url, channel)),
        mimetype="audio/mpeg", 
        headers={
            "Content-Type": "audio/mpeg",
            "Content-Disposition": f"attachment; filename={sanitized_name}.mp3"
        }
    )

# -----------------------
# Run Server
# -----------------------
if __name__ == "__main__":
    if 'time' not in globals():
        import time 
        
    app.run(host="0.0.0.0", port=8000, debug=False)
