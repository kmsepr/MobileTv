# -----------------------
# HOME PAGE (Auto Grid, big text, no thumbnails)
# -----------------------
@app.route("/")
def home():
    # only list live channels that are currently available
    live_youtube = [n for n, ok in LIVE_STATUS.items() if ok]
    files = sorted(os.listdir(CACHE_DIR), reverse=True)

    html = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Live + MP3</title>
  <style>
    :root{--bg:#0b0b0b;--card:#121212;--accent:#0ff;--muted:#9aa0a6}
    body{margin:0;font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial;color:#fff;background:var(--bg)}
    .tabs{display:flex;justify-content:center;gap:12px;padding:14px;background:#000}
    .tab{padding:12px 18px;border-radius:10px;background:#111;cursor:pointer;font-size:20px}
    .tab.active{background:var(--accent);color:#000;font-weight:700}
    .container{padding:16px;max-width:1100px;margin:0 auto}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:16px}
    .card{background:var(--card);padding:18px;border-radius:10px;text-align:center;font-size:20px}
    .bigbtn{display:inline-block;margin-top:10px;padding:10px 14px;border-radius:8px;background:transparent;border:1px solid var(--accent);color:var(--accent);text-decoration:none}
    form input{width:70%;padding:12px;font-size:18px;border-radius:8px;border:1px solid #333;background:#0b0b0b;color:#fff}
    form button{padding:12px 16px;font-size:18px;border-radius:8px;margin-left:8px;background:var(--accent);color:#000;border:none}
    h1{font-size:24px;margin:6px 0}
    small{color:var(--muted);display:block;margin-top:8px}
  </style>
  <script>
    function showTab(id){
      document.getElementById('live').style.display='none';
      document.getElementById('mp3').style.display='none';
      document.getElementById(id).style.display='block';
      document.getElementById('tab_live').classList.remove('active');
      document.getElementById('tab_mp3').classList.remove('active');
      document.getElementById('tab_'+id).classList.add('active');
    }
    window.onload=function(){ showTab('live'); }
  </script>
</head>
<body>
  <div class="tabs">
    <div id="tab_live" class="tab active" onclick="showTab('live')">▶ YouTube Live</div>
    <div id="tab_mp3" class="tab" onclick="showTab('mp3')">🎵 MP3 Converter</div>
  </div>

  <div class="container">
    <div id="live">
      <h1>Live Channels (only available ones)</h1>
      <div class="grid">
      {% if youtube_channels %}
        {% for ch in youtube_channels %}
          <div class="card">
            <div style="font-size:20px;font-weight:700">{{ ch.replace('_',' ').title() }}</div>
            <small>Live</small>
            <div style="margin-top:12px">
              <a class="bigbtn" href="/watch/{{ ch }}">▶ Watch</a>
              <a class="bigbtn" href="/audio/{{ ch }}">🎵 Audio</a>
            </div>
          </div>
        {% endfor %}
      {% else %}
        <div class="card">No live channels available right now.</div>
      {% endif %}
      </div>
    </div>

    <div id="mp3" style="display:none">
      <h1>MP3 Converter (40 kbps Mono)</h1>
      <form method="POST" action="/convert">
        <input name="url" placeholder="Paste YouTube link..." required />
        <button type="submit">Convert</button>
      </form>
      <small>Cached files are stored on the server.</small>

      <div class="grid" style="margin-top:18px">
        {% if files %}
          {% for f in files %}
            <div class="card">
              <div style="font-weight:700">{{ f }}</div>
              <div style="margin-top:12px">
                <a class="bigbtn" href="/mp3/{{ f }}">▶ Play</a>
                <a class="bigbtn" href="/download/{{ f }}">⬇ Download</a>
              </div>
            </div>
          {% endfor %}
        {% else %}
          <div class="card">No cached MP3 files yet.</div>
        {% endif %}
      </div>
    </div>
  </div>
</body>
</html>
"""
    available = [ch for ch in YOUTUBE_STREAMS.keys() if LIVE_STATUS.get(ch)]
    return render_template_string(html, youtube_channels=available, files=files)
