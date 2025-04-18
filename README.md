
*YouTube Live Audio Streamer*

A simple Flask-based server that streams live YouTube audio as MP3 using yt-dlp and ffmpeg. Ideal for creating low-bandwidth audio streams from educational, religious, or news live channels — great for low-end devices, legacy systems, or internet radios that support only direct MP3 HTTP streams.


---

Features

Streams live audio from YouTube Live channels

Auto-extracts audio URLs using yt-dlp

Converts audio to MP3 (mono, 40 kbps) using ffmpeg

Auto-refreshes links every 30 minutes

Lightweight and easily deployable on services like Koyeb, Railway, etc.

Optional support for cookies.txt to bypass age restrictions



---

Example Use

You can define channels like this in the Python code:

YOUTUBE_STREAMS = {
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
    "yaqeen_institute": "https://www.youtube.com/@yaqeeninstituteofficial/live",
    ...
}

Then access the stream via:

http://your-server/skicr_tv
http://your-server/yaqeen_institute

Each endpoint returns a live MP3 audio stream from the respective YouTube Live channel.


---

Setup Instructions

1. Install dependencies

pip install flask


2. Install yt-dlp and ffmpeg Make sure they are available in your $PATH.


3. (Optional) Add cookies.txt to bypass restricted content:

Place it at /mnt/data/cookies.txt or change the path in the script.



4. Run the app

python app.py




---

Deployment Tips

Works great on Koyeb, Railway, or similar platforms with persistent storage and basic Docker/Flask support.

Recommended to use a small mp3 bitrate (like 40 kbps mono) for smooth streaming on low-speed connections or older devices.



---

License

This project is licensed under the MIT License. Feel free to modify and redistribute.


