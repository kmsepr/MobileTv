from flask import Flask, render_template_string, Response
import subprocess

app = Flask(__name__)

# ✅ Your YouTube live channels
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "kairali_we": "https://www.youtube.com/@KairaliTV/live",
    "victers_tv": "https://www.youtube.com/@itsvicters/live",
    "safari_tv": "https://www.youtube.com/@safaritvonline/live",
    "aljazeera_english": "https://www.youtube.com/@aljazeeraenglish/live",
    "aljazeera_arabic": "https://www.youtube.com/@aljazeeraarabic/live",
}

# ---------- HTML TEMPLATES ----------
HOME_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>TV Grid</title>
  <style>
    body { font-family: sans-serif; background: #111; color: #eee; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; padding: 20px; }
    .card { background: #222; padding: 20px; text-align: center; border-radius: 10px; }
    .card a { color: #0ff; text-decoration: none; }
  </style>
</head>
<body>
  <h2 style="text-align:center;">📺 Live TV</h2>
  <div class="grid">
    {% for key, url in streams.items() %}
      <div class="card">
        <a href="/yt/{{ key }}">{{ key.replace('_',' ').title() }}</a>
      </div>
    {% endfor %}
  </div>
</body>
</html>
"""

PLAYER_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ name }}</title>
  <style>
    body { margin:0; background:black; display:flex; flex-direction:column; height:100vh; }
    video { flex:1; width:100%; height:100%; background:black; }
    a { padding:10px; text-align:center; display:block; color:#0ff; background:#111; text-decoration:none; }
  </style>
</head>
<body>
  <video controls autoplay>
    <source src="{{ url }}" type="video/mp4">
    Your browser does not support video playback.
  </video>
  <a href="/">⬅ Back</a>
</body>
</html>
"""

# ---------- ROUTES ----------

@app.route("/")
def home():
    return render_template_string(HOME_HTML, streams=YOUTUBE_STREAMS)

@app.route("/yt/<station>")
def yt(station):
    if station not in YOUTUBE_STREAMS:
        return "Channel not found", 404

    yt_url = YOUTUBE_STREAMS[station]

    # 🔹 Use yt-dlp to extract the best playable stream URL
    cmd = ["yt-dlp", "-f", "bestaudio[ext=m4a]/best", "-g", yt_url]
    result = subprocess.run(cmd, capture_output=True, text=True)

    stream_url = result.stdout.strip()
    if not stream_url:
        return f"Stream unavailable: {result.stderr}", 503

    # Instead of raw stream, embed in a player
    return render_template_string(PLAYER_HTML, name=station.replace("_"," ").title(), url=stream_url)

# ---------- MAIN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)