import subprocess
import time
from flask import Flask, Response

app = Flask(__name__)

# 📡 List of TV channels (URLs for TV streaming, but we'll stream only audio)
TV_CHANNELS = {
    "asianet_movies": "http://ktv.im:8080/44444/44444/81804",
    "surya_movies": "http://ktv.im:8080/44444/44444/81823",
    "surya_comedy": "http://ktv.im:8080/44444/44444/81825",
    "mazhavil_manorama": "http://ktv.im:8080/44444/44444/81837",
    "asianet_plus": "http://ktv.im:8080/44444/44444/81801",
    "media_one": "http://ktv.im:8080/44444/44444/81777",
    "kairali_we": "http://ktv.im:8080/44444/44444/81812",
}

# 🔄 Streaming function for audio (TV channels treated like radio)
def generate_stream(url):
    process = None
    while True:
        if process:
            process.kill()  # Stop old FFmpeg instance before restarting
        
        process = subprocess.Popen(
            [
                "ffmpeg", 
                "-reconnect", "1", 
                "-reconnect_streamed", "1", 
                "-reconnect_delay_max", "10", 
                "-max_delay", "1000",  # Limit max delay for smooth streaming
                "-i", url, 
                "-vn",  # Disable video (audio only)
                "-ac", "1",  # Mono audio (1 channel)
                "-b:a", "40k",  # Audio bitrate 40kbps
                "-f", "mp3",  # Output format for audio streaming
                "pipe:1"  # Output to stdout
            ],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            bufsize=16384
        )

        print(f"🎵 Streaming audio from: {url} (Mono, 40kbps)")

        try:
            # Stream the audio
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk
        except GeneratorExit:
            # Handle generator exit (when the client disconnects)
            process.kill()
            break
        except Exception as e:
            print(f"⚠️ Stream error: {e}")

        print("🔄 FFmpeg stopped, restarting stream...")
        time.sleep(5)  # Wait before restarting to prevent immediate restart

# 🌍 API to stream selected TV channel (audio only)
@app.route("/<channel_name>")
def stream(channel_name):
    url = TV_CHANNELS.get(channel_name)
    if not url:
        return "⚠️ Channel not found", 404
    
    return Response(generate_stream(url), mimetype="audio/mpeg")

# 🚀 Start Flask server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)