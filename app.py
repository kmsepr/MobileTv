import subprocess
from flask import Flask, Response, render_template_string, request

app = Flask(__name__)

# ----------------------------
# HTML player (autoplay + repeat)
# ----------------------------
PLAYER_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radio Stream</title>
<style>
  body { background:#000; color:#0f0; font-family:monospace; text-align:center; padding:20px; }
  audio { width:90%; margin-top:20px; }
</style>
</head>
<body>
  <h2>🎧 Now Playing: {{ channel }}</h2>
  <audio id="player" controls autoplay loop>
    <source src="/stream/{{ channel }}?url={{ url }}" type="audio/mpeg">
  </audio>
  <p>Streaming live... (auto-restarts if stopped)</p>
  <script>
    // If autoplay fails (mobile), retry after a tap
    const p = document.getElementById("player");
    document.body.addEventListener("click", () => p.play());
  </script>
</body>
</html>
"""

# ----------------------------
# Player page route
# ----------------------------
@app.route("/")
def index():
    # Example usage: /?url=https://some-radio-url.mp3&channel=MalayalamFM
    url = request.args.get("url", "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one")
    channel = request.args.get("channel", "BBC Radio 1")
    return render_template_string(PLAYER_HTML, url=url, channel=channel)

# ----------------------------
# Streaming route (FFmpeg proxy)
# ----------------------------
@app.route("/stream/<channel>")
def stream_audio(channel):
    """
    Proxy radio/audio through FFmpeg so browsers can play MP3 reliably.
    Loops automatically if stream drops.
    """
    source_url = request.args.get("url")
    if not source_url:
        return "Missing 'url' parameter", 400

    def generate():
        while True:  # repeat if ffmpeg exits (auto reconnect)
            cmd = [
                "ffmpeg",
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-i", source_url,
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "64k",
                "-f", "mp3",
                "-"
            ]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                for chunk in iter(lambda: process.stdout.read(4096), b""):
                    yield chunk
            except GeneratorExit:
                process.kill()
                break
            finally:
                process.wait()
            # Restart after stream ends
            yield b""
    return Response(generate(), mimetype="audio/mpeg")

# ----------------------------
# Local run (for testing)
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)