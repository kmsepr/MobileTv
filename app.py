import time
import threading
import logging
import subprocess
import os

from flask import Flask, Response, render_template_string, abort, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# ======================================================
# STREAM SOURCES
# ======================================================
TV_STREAMS = {
    "kairali_we": "https://cdn-3.pishow.tv/live/1530/master.m3u8",
    "amrita_tv": "https://ddash74r36xqp.cloudfront.net/master.m3u8",
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "dd_sports": "https://cdn-6.pishow.tv/live/13/master.m3u8",
}

# ======================================================
# STORAGE (NOT TEMP)
# ======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOW_HLS_DIR = os.path.join(BASE_DIR, "lowhls")
os.makedirs(LOW_HLS_DIR, exist_ok=True)

# ======================================================
# LOW VIDEO LIVE TRANSCODER (VIDEO ONLY ~40 KBPS)
# ======================================================
def launch_low_hls(channel, src_url):
    channel_dir = os.path.join(LOW_HLS_DIR, channel)
    os.makedirs(channel_dir, exist_ok=True)

    # Kill old FFmpeg if running
    old_proc = getattr(launch_low_hls, f"{channel}_proc", None)
    if old_proc and old_proc.poll() is None:
        old_proc.terminate()
        old_proc.wait(timeout=2)
        logging.info(f"🛑 Old FFmpeg stopped for {channel}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", src_url,

        # ❌ NO AUDIO
        "-an",

        # 🎥 240px VIDEO
        "-vf", "scale=240:160",
        "-r", "6",

        "-c:v", "libx264",
        "-profile:v", "baseline",
        "-preset", "ultrafast",
        "-tune", "zerolatency",

        # 🎯 ~40 kbps VIDEO
        "-b:v", "40k",
        "-maxrate", "40k",
        "-bufsize", "80k",

        # 🟢 LIVE HLS
        "-f", "hls",
        "-hls_time", "1",
        "-hls_list_size", "3",
        "-hls_flags", "delete_segments+omit_endlist",
        "-hls_segment_filename",
        os.path.join(channel_dir, "seg_%03d.ts"),

        os.path.join(channel_dir, "index.m3u8")
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    setattr(launch_low_hls, f"{channel}_proc", proc)

    logging.info(f"🚀 LIVE VIDEO-ONLY 40kbps started for {channel}")

# ======================================================
# HOME PAGE
# ======================================================
@app.route("/")
def home():
    html = """
    <html>
    <head>
    <title>📺 Live TV</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body { background:#111; color:#fff; font-family:sans-serif; }
    .card { background:#222; padding:12px; margin:10px; border-radius:10px; }
    a { color:#0ff; text-decoration:none; font-size:22px; }
    </style>
    </head>
    <body>
    <h2>📺 Live TV</h2>
    {% for k in channels %}
      <div class="card">
        {{ k.replace('_',' ').title() }}<br><br>
        <a href="/watch/{{k}}">▶ Normal</a> |
        <a href="/lowvideo/{{k}}">🔽 Low</a>
      </div>
    {% endfor %}
    </body>
    </html>
    """
    return render_template_string(html, channels=TV_STREAMS.keys())

# ======================================================
# NORMAL PLAY (RAW HLS)
# ======================================================
@app.route("/watch/<channel>")
def watch(channel):
    url = TV_STREAMS.get(channel)
    if not url:
        abort(404)

    return f"""
    <html>
    <head>
    <title>{channel}</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    </head>
    <body>
    <h3>{channel}</h3>
    <video id="v" controls autoplay playsinline style="width:95%"></video>
    <script>
      var v=document.getElementById('v');
      var src="{url}";
      if(Hls.isSupported()) {{
        var h=new Hls(); h.loadSource(src); h.attachMedia(v);
      }} else {{
        v.src=src;
      }}
    </script>
    </body>
    </html>
    """

# ======================================================
# LOW VIDEO PAGE
# ======================================================
@app.route("/lowvideo/<channel>")
def lowvideo(channel):
    url = TV_STREAMS.get(channel)
    if not url:
        abort(404)

    launch_low_hls(channel, url)

    return f"""
    <html>
    <head>
    <title>{channel} Low</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    </head>
    <body>
    <h3>{channel} (240px • 40kbps)</h3>
    <video id="v" controls autoplay playsinline style="width:95%"></video>
    <script>
      var v=document.getElementById('v');
      var src="/lowhls/{channel}/index.m3u8";
      if(Hls.isSupported()) {{
        var h=new Hls(); h.loadSource(src); h.attachMedia(v);
      }} else {{
        v.src=src;
      }}
    </script>
    </body>
    </html>
    """

# ======================================================
# SERVE HLS FILES
# ======================================================
@app.route("/lowhls/<channel>/<path:filename>")
def serve_lowhls(channel, filename):
    return send_from_directory(os.path.join(LOW_HLS_DIR, channel), filename)

# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)