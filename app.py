from flask import Flask, render_template_string, abort

app = Flask(__name__)

# ---------------- TV STREAM LINKS ----------------
STREAM_LINKS = {
    "safari_tv": "https://j78dp346yq5r-hls-live.5centscdn.com/safari/live.stream/chunks.m3u8",
    "victers_tv": "https://932y4x26ljv8-hls-live.5centscdn.com/victers/tv.stream/victers/tv1/chunks.m3u8",
    "kairali_we": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/wetv_nim_https/050522/wetv/playlist.m3u8",
    "mazhavil_manorama": "https://yuppmedtaorire.akamaized.net/v1/master/a0d007312bfd99c47f76b77ae26b1ccdaae76cb1/mazhavilmanorama_nim_https/050522/mazhavilmanorama/playlist.m3u8",
}

# ---------------- HOME (GRID OF CHANNELS) ----------------
@app.route("/")
def home():
    html = """
    <html>
    <head>
        <title>Live TV</title>
        <style>
            body { font-family: sans-serif; text-align:center; background:#111; color:#fff; }
            .grid { display:grid; grid-template-columns:repeat(2,1fr); gap:15px; margin:20px; }
            .card { background:#222; padding:20px; border-radius:10px; }
            a { color:#0f0; text-decoration:none; font-size:18px; }
            video { width:90%; max-width:600px; margin:20px auto; display:block; }
        </style>
    </head>
    <body>
        <h2>📺 Live TV Channels</h2>
        <div class="grid">
            {% for key in streams.keys() %}
                <div class="card">
                    <a href="/watch/{{ key }}">▶ {{ key.replace('_',' ').title() }}</a>
                </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, streams=STREAM_LINKS)

# ---------------- PLAYER ----------------
@app.route("/watch/<channel>")
def watch(channel):
    if channel not in STREAM_LINKS:
        abort(404)
    stream_url = STREAM_LINKS[channel]
    html = """
    <html>
    <head>
        <title>{{ channel }}</title>
        <style>
            body { font-family:sans-serif; text-align:center; background:#000; color:#fff; }
            video { width:95%; max-width:700px; margin:20px auto; display:block; }
            a { color:#0f0; text-decoration:none; }
        </style>
    </head>
    <body>
        <h2>{{ channel.replace('_',' ').title() }}</h2>
        <video controls autoplay>
            <source src="{{ url }}" type="application/x-mpegURL">
            Your browser does not support HLS.
        </video>
        <p><a href="/">⬅ Back to channels</a></p>
    </body>
    </html>
    """
    return render_template_string(html, channel=channel, url=stream_url)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)