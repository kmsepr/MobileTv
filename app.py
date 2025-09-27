from flask import Flask, Response, render_template_string
import subprocess
import os

app = Flask(__name__)

# -----------------------
# Streams
# -----------------------
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
}

TV_STREAMS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
}

# -----------------------
# FFmpeg proxy (TV + YouTube)
# -----------------------
def proxy_stream(url):
    ffmpeg_cmd = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",
        "-i", url,
        "-c:v", "copy",
        "-c:a", "aac",
        "-movflags", "frag_keyframe+empty_moov",
        "-f", "mp4",
        "-"
    ]
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for chunk in iter(lambda: process.stdout.read(4096), b""):
            yield chunk
    except GeneratorExit:
        process.kill()
    except Exception:
        process.kill()

# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Live Streams</title>
      <style>
        body { font-family: sans-serif; padding: 10px; background: #fff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
        .card { padding: 20px; background: #f0f0f0; text-align: center; border-radius: 8px; }
        .card a { text-decoration: none; color: black; font-weight: bold; }
        .card:hover { background: #ddd; }
      </style>
    </head>
    <body>
      <h2>📺 Live Streams</h2>
      <div class="grid">
    """
    # YouTube
    for name in YOUTUBE_STREAMS:
        html += f"<div class='card'><a href='/yt/{name}'>{name.replace('_',' ').title()}</a></div>"
    # TV
    for name in TV_STREAMS:
        html += f"<div class='card'><a href='/tv/{name}'>{name.replace('_',' ').title()}</a></div>"
    html += "</div></body></html>"
    return render_template_string(html)

@app.route("/tv/<station>")
def tv(station):
    if station not in TV_STREAMS:
        return "Not found", 404
    return Response(proxy_stream(TV_STREAMS[station]), mimetype="video/mp4")

@app.route("/yt/<station>")
def yt(station):
    if station not in YOUTUBE_STREAMS:
        return "Not found", 404
    # convert YT live link → direct stream with yt-dlp
    cmd = ["yt-dlp", "-f", "best", "-g", YOUTUBE_STREAMS[station]]
    url = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    if not url:
        return "Stream unavailable", 503
    return Response(proxy_stream(url), mimetype="video/mp4")

# -----------------------
# Run Flask
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, threaded=True)