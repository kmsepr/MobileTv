import time
import threading
import logging
from flask import Flask, Response, render_template_string, abort
import subprocess, os, requests, random

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

# -----------------------
# TV Streams (direct m3u8)
# -----------------------
TV_STREAMS = {
    
"safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",

"mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8

}

# -----------------------
# YouTube Live Streams
# -----------------------
YT_STREAMS = {
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
}

# -----------------------
# FFmpeg Proxy Generator
# -----------------------
def generate_stream(url):
    logging.info(f"Starting ffmpeg for: {url}")
    process = subprocess.Popen(
        [
            "ffmpeg", "-i", url, "-c", "copy", "-f", "mpegts", "-preset", "veryfast", "pipe:1"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    try:
        while True:
            data = process.stdout.read(1024)
            if not data:
                break
            yield data
    finally:
        process.kill()

# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <title>TV + YouTube Streams</title>
  <style>
    body { font-family: sans-serif; background: #111; color: #eee; text-align: center; margin: 0; }
    h2 { margin: 20px 0 10px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; padding: 10px; }
    .card { background: #222; border-radius: 8px; padding: 10px; cursor: pointer; }
    .card:hover { background: #444; }
    video { width: 100%; max-height: 70vh; background: black; }
  </style>
</head>
<body>
  <h1>📺 Live Streams</h1>

  <video id="player" controls autoplay></video>

  <h2>TV</h2>
  <div class="grid">
    {% for key, url in TV_STREAMS.items() %}
      <div class="card" onclick="playStream('{{key}}')">{{ key.replace('_',' ') }}</div>
    {% endfor %}
  </div>

  <h2>YouTube</h2>
  <div class="grid">
    {% for key, url in YT_STREAMS.items() %}
      <div class="card" onclick="playStream('{{key}}')">{{ key.replace('_',' ') }}</div>
    {% endfor %}
  </div>

  <script>
    const player = document.getElementById("player");
    const tv = {{ TV_STREAMS|tojson }};
    const yt = {{ YT_STREAMS|tojson }};
    let all = {...tv, ...yt};
    let keys = Object.keys(all);
    let index = 0;

    function playStream(key) {
      index = keys.indexOf(key);
      if (tv[key]) player.src = tv[key];
      else player.src = "/stream/" + key;
    }

    function playRandom() {
      let r = keys[Math.floor(Math.random()*keys.length)];
      playStream(r);
    }

    document.addEventListener("keydown", e => {
      if (e.key === "0") playRandom();
      else if (e.key >= "1" && e.key <= "9") {
        let i = parseInt(e.key) - 1;
        if (i < keys.length) playStream(keys[i]);
      } else if (e.key === "4") {
        index = (index - 1 + keys.length) % keys.length;
        playStream(keys[index]);
      } else if (e.key === "6") {
        index = (index + 1) % keys.length;
        playStream(keys[index]);
      } else if (e.key === "5") {
        if (player.paused) player.play(); else player.pause();
      }
    });

    playRandom();
  </script>
</body>
</html>
    """, TV_STREAMS=TV_STREAMS, YT_STREAMS=YT_STREAMS)

@app.route("/stream/<channel>")
def stream_channel(channel):
    if channel not in YT_STREAMS:
        abort(404)
    url = YT_STREAMS[channel]
    ytdlp = subprocess.run(
        ["yt-dlp", "-g", "-f", "best[ext=mp4]", url],
        capture_output=True, text=True
    )
    direct_url = ytdlp.stdout.strip().split("\n")[-1]
    if not direct_url:
        abort(500)
    return Response(generate_stream(direct_url), mimetype="video/mp2t")

if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=8000)