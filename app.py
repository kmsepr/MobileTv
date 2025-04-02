from flask import Flask, Response
import subprocess

app = Flask(__name__)

def generate_stream():
    yt_cmd = ["/usr/local/bin/yt-dlp", "-f", "best", "-o", "-", "https://www.youtube.com/watch?v=your_video_id"]
    
    process = subprocess.Popen(yt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    def stream():
        while True:
            chunk = process.stdout.read(1024)
            if not chunk:
                break
            yield chunk
    
    return Response(stream(), content_type='video/mp4')

@app.route('/radio')
def radio():
    return generate_stream()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
