#!/usr/bin/env python3
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

from common import PIPER_URL, config
from observation import ObservationRecorder


def notify(message):
    subprocess.run(["notify-send", "Read selected text", message], check=False)


def play(response, sample_rate, message, recorder=None, attempt_id=None,
         backend_name=None):
    first = response.read1(16384)
    if not first:
        raise RuntimeError("speech backend returned no audio")
    player = subprocess.Popen(
        ["pw-play", "--raw", "--format", "s16", "--rate", str(sample_rate),
         "--channels", "1", "-"],
        stdin=subprocess.PIPE,
    )
    notify(message)
    try:
        player.stdin.write(first)
        player.stdin.flush()
        if recorder:
            recorder.offer("first_audible", attempt_id=attempt_id,
                           backend=backend_name, sample_rate=sample_rate)
        while chunk := response.read1(16384):
            player.stdin.write(chunk)
        player.stdin.close()
        return player.wait() == 0
    finally:
        if player.poll() is None:
            player.terminate()


def local_speech(text, recorder=None, attempt_id=None):
    request = urllib.request.Request(
        f"{PIPER_URL}/synthesize",
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return play(response, 22050, "Speaking locally — press the shortcut to stop",
                    recorder, attempt_id, "piper")


def remote_speech(target, voice_id, text, deadline, recorder=None,
                  attempt_id=None):
    def remaining():
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("Harmony attempt deadline expired")
        return max(0.2, left)

    admission = urllib.request.Request(
        target["admit"],
        data=json.dumps({"kind": "qwen", "owner": "read-selected-text"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(admission, timeout=remaining()) as response:
        if not json.load(response).get("granted"):
            return False
    with urllib.request.urlopen(target["health"], timeout=remaining()) as response:
        health = json.load(response)
    resident = health.get("manager", {}).get("resident", health.get("model", []))
    if "qwen" not in resident:
        return False
    request = urllib.request.Request(
        target["stream"],
        data=json.dumps({"text": text, "voice_id": voice_id,
                         "language": "en", "engine": "qwen"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=remaining()) as response:
        rate = int(response.headers.get("X-Sample-Rate", "24000"))
        return play(response, rate, "Speaking through PolyTTS — press the shortcut to stop",
                    recorder, attempt_id, "harmony")


def speak(text, settings, recorder):
    recorder.offer("requested", input_bytes=len(text.encode()))
    errors = []
    remote_failed = False
    deadline = time.monotonic() + float(settings.get("harmony_timeout_seconds", 6))
    for index, target in enumerate(settings.get("targets", [])):
        attempt_id = f"harmony-{index + 1}"
        try:
            if remote_speech(target, settings.get("voice_id", ""), text,
                             deadline, recorder, attempt_id):
                recorder.offer("served", attempt_id=attempt_id,
                               backend="harmony", outcome="completed")
                print("backend=harmony-qwen", file=sys.stderr, flush=True)
                return 0
            remote_failed = True
        except (OSError, RuntimeError, KeyError, TimeoutError,
                urllib.error.URLError) as error:
            remote_failed = True
            errors.append(f"PolyTTS: {error}")
            recorder.offer("attempt_failed", attempt_id=attempt_id,
                           backend="harmony", failure_class="unavailable")
        if time.monotonic() >= deadline:
            break
    try:
        if local_speech(text, recorder, "piper-1"):
            recorder.offer("served", attempt_id="piper-1", backend="piper",
                           outcome="completed",
                           fallback_kind=("harmony_failed" if remote_failed
                                          else "no_harmony_target"))
            print("backend=piper-cori", file=sys.stderr, flush=True)
            return 0
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        errors.append(f"local Piper: {error}")
        recorder.offer("attempt_failed", attempt_id="piper-1", backend="piper",
                       failure_class="unavailable")
    notify("Every speech backend failed")
    print("\n".join(errors), file=sys.stderr)
    recorder.offer("finished", outcome="failed", failure_class="all_backends")
    return 1


def main():
    text = sys.stdin.read().strip()
    if not text:
        return 2
    settings = config()
    recorder = ObservationRecorder.from_environment()
    try:
        return speak(text, settings, recorder)
    finally:
        recorder.flush()


if __name__ == "__main__":
    raise SystemExit(main())
