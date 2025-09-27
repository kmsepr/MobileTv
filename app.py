import subprocess
import time
import threading
import os
import logging
from flask import Flask, Response, render_template_string, abort

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (m3u8)
# -----------------------
TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
}

# -----------------------
# YouTube Live Streams
# -----------------------
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
}

CACHE = {}  # Stores direct YouTube live URLs
COOKIES_FILE = "/mnt/data/cookies.txt"  # optional for age-restricted channels

# -----------------------
# Extract YouTube Live URL (video+audio)
# -----------------------
def get_youtube_live_url(youtube_url: str):
    try:
        cmd = [
            "yt-dlp",
            "-f", "best[height<=480]/best",  # best quality <=480p
            "-g",
            youtube_url
        ]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(1, "--cookies")
            cmd.insert(2, COOKIES_FILE)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logging.error(f"yt-dlp error for {youtube_url}: {result.stderr.strip()}")
        return None
    except Exception:
        logging.exception("Exception while extracting YouTube live URL")
        return None

# -----------------------
# Background thread to refresh URLs
# -----------------------
def refresh_stream_urls():
    last_update = {}
    while True:
        logging.info("🔄 Refreshing YouTube live URLs...")
        now = time.time()
        for name, url in YOUTUBE_STREAMS.items():
            if name not in last_update or now - last_update[name] > 60:
                direct_url = get_youtube_live_url(url)
                if direct_url:
                    CACHE[name] = direct_url
                    last_update[name] = now
                    logging.info(f"✅ Updated {name}")
                else:
                    logging.warning(f"❌ Failed to update {name}")
        time.sleep(60)

threading.Thread(target=refresh_stream_urls, daemon=True).start()

# -----------------------
# Generate 3GP AAC 240p
# -----------------------
def generate_3gp_video(url: str):
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "10",
            "-i", url,
            "-vf", "scale=-2:240",  # 240p
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "64k",
            "-f", "mp4",  # 3GP container can be mp4 for simplicity
            "-"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=10**6,
    )
    try:
        for chunk in iter(lambda: process.stdout.read(4096), b""):
            yield chunk
    except GeneratorExit:
        process.terminate()
        process.wait()
    except Exception as e:
        logging.error(f"Video stream error: {e}")
        process.terminate()
        process.wait()

# -----------------------
# Home Route (Vertical List)
# -----------------------
@app.route("/")
def home():
    all_channels = list(TV_STREAMS.keys()) + list(YOUTUBE_STREAMS.keys())
    enumerated_channels = list(enumerate(all_channels, 1))
    html = """<html>
<head>
<title>📺 TV & YouTube Live 3GP</title>
<style>
body { font-family: sans-serif; text-align:center; background:#111; color:#fff; }
ul { list-style:none; padding:0; margin:20px auto; max-width:400px; }
li { background:#222; margin:10px 0; padding:15px; border-radius:8px; }
a { color:#0f0; text-decoration:none; font-size:18px; display:block; }
</style>
</head>
<body>
<h2>📺 TV & YouTube Live 3GP</h2>
<ul id="channelList">
{% for idx, key in channels %}
<li>
<a href="/watch/{{ key }}">▶ {{ idx }}. {{ key.replace('_',' ').title() }}</a>
</li>
{% endfor %}
</ul>
<script>
document.addEventListener("keydown", function(event) {
    let num = parseInt(event.key);
    if (!isNaN(num) && num > 0) {
        let links = document.querySelectorAll("#channelList a");
        if (num <= links.length) window.location.href = links[num-1].href;
    }
});
</script>
</body></html>"""
    return render_template_string(html, channels=enumerated_channels)

# -----------------------
# Watch Route
# -----------------------
@app.route("/watch/<channel>")
def watch(channel):
    if channel in TV_STREAMS:
        stream_url = TV_STREAMS[channel]
    elif channel in YOUTUBE_STREAMS:
        if channel not in CACHE:
            return "YouTube stream not ready yet, try again.", 503
        stream_url = CACHE[channel]
    else:
        abort(404)

    html = f"""
<html><body style="background:#000; color:#fff; text-align:center;">
<h2>{channel.replace('_',' ').title()} (3GP AAC)</h2>
<video controls autoplay style="width:95%; max-width:700px;">
<source src="/stream/{channel}" type="video/mp4">
</video>
<p><a href='/'>⬅ Back</a></p>
</body></html>"""
    return html

# -----------------------
# Stream Route
# -----------------------
@app.route("/stream/<channel>")
def stream(channel):
    if channel in TV_STREAMS:
        url = TV_STREAMS[channel]
    elif channel in YOUTUBE_STREAMS:
        if channel not in CACHE:
            return "YouTube stream not ready yet", 503
        url = CACHE[channel]
    else:
        return "Channel not found", 404

    return Response(generate_3gp_video(url), mimetype="video/mp4")

# -----------------------
# Run App
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)