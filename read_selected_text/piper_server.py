#!/usr/bin/env python3
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from piper.voice import PiperVoice

from common import MODEL


MAX_CHARS = 20
voice = PiperVoice.load(MODEL, config_path=f"{MODEL}.json")
synthesis_lock = threading.Lock()


def segments(text):
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > MAX_CHARS:
            yield current
            current = word
        else:
            current = candidate
        while len(current) > MAX_CHARS:
            yield current[:MAX_CHARS]
            current = current[MAX_CHARS:]
    if current:
        yield current


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok","voice":"en_GB-cori-high"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/synthesize":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        text = json.loads(self.rfile.read(length) or b"{}").get("text", "").strip()
        if not text:
            self.send_error(400, "text is required")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("X-Sample-Rate", "22050")
        self.end_headers()
        try:
            with synthesis_lock:
                for segment in segments(text):
                    for chunk in voice.synthesize(segment):
                        self.wfile.write(chunk.audio_int16_bytes)
                        self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18789), Handler).serve_forever()
