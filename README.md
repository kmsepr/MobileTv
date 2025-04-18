
# YouTube Live Audio Streamer

A simple Flask-based server that streams live YouTube audio as MP3 using `yt-dlp` and `ffmpeg`. Perfect for low-bandwidth audio streaming from educational, religious, or news channels — ideal for low-end devices, legacy systems, or internet radios that support only direct MP3 HTTP streams.

---

### Features

- Streams live audio from YouTube Live channels
- Auto-extracts audio URLs using `yt-dlp`
- Converts audio to MP3 (mono, 40 kbps) using `ffmpeg`
- Auto-refreshes links every 30 minutes
- Lightweight and easily deployable (Koyeb, Railway, etc.)
- Optional support for `cookies.txt` to bypass age restrictions

---

### Example Use

You can define channels like this in your Python code:

```python
YOUTUBE_STREAMS = {
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
    "yaqeen_institute": "https://www.youtube.com/@yaqeeninstituteofficial/live",
    ...
}

Then access the stream by visiting:

http://your-server/skicr_tv
http://your-server/yaqeen_institute

Each endpoint delivers a live MP3 audio stream from the corresponding YouTube Live channel.


---

Setup Instructions

1. Install dependencies

pip install flask

2. Install yt-dlp and ffmpeg

Make sure both yt-dlp and ffmpeg are installed and available in your $PATH.

3. (Optional) Add cookies.txt to bypass restricted content

Place the file at:

/mnt/data/cookies.txt

Or update the path inside the script to match your setup.

4. Run the app

python app.py

The app runs by default at:

http://localhost:8000


---

Deployment Tips

Runs well on Koyeb, Railway, and other platforms with Flask or Docker support

Keep bitrate low (like 40 kbps mono) for stable streaming on older devices or slower connections

Set up a cron or built-in timer to refresh streams every 30 minutes



---

License

This project is licensed under the MIT License. Feel free to modify and reuse as needed.


