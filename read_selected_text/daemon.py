#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from observation import ObservationRecorder


BACKEND = Path(__file__).with_name("backend.py")
state_lock = threading.Lock()
player = None
active_request_id = None


def stop(recorder=None):
    global player, active_request_id
    with state_lock:
        proc = player
        request_id = active_request_id
        player = None
        active_request_id = None
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        subprocess.run(
            ["systemctl", "--user", "restart", "read-selected-text-piper.service"],
            check=False,
        )
        if recorder:
            recorder.request_id = request_id or recorder.request_id
            recorder.offer("canceled", cancel_cause="shortcut_toggle")


def reap(proc):
    global player
    proc.wait()
    with state_lock:
        if player is proc:
            player = None


def start(text):
    global player, active_request_id
    request_id = str(uuid4())
    environment = os.environ.copy()
    environment["READ_SELECTED_TEXT_REQUEST_ID"] = request_id
    proc = subprocess.Popen(
        ["/usr/bin/python3", str(BACKEND)], stdin=subprocess.PIPE,
        text=True, start_new_session=True, env=environment,
    )
    proc.stdin.write(text)
    proc.stdin.close()
    with state_lock:
        player = proc
        active_request_id = request_id
    threading.Thread(target=reap, args=(proc,), daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._reply({"status": "ok"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/stop":
            recorder = ObservationRecorder.from_environment()
            stop(recorder=recorder)
            recorder.flush()
            result = {"status": "stopped"}
        elif self.path == "/toggle":
            text = request.get("text", "").strip()
            with state_lock:
                active = player is not None and player.poll() is None
            if active:
                recorder = ObservationRecorder.from_environment()
                stop(recorder=recorder)
                recorder.flush()
                result = {"status": "stopped"}
            elif text:
                start(text)
                result = {"status": "streaming"}
            else:
                result = {"status": "empty"}
        else:
            self.send_error(404)
            return
        self._reply(result)

    def _reply(self, result):
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18788), Handler).serve_forever()
