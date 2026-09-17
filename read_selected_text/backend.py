#!/usr/bin/env python3
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

from common import PIPER_URL, config


def notify(message):
    subprocess.run(["notify-send", "Read selected text", message], check=False)


def play(response, sample_rate, message):
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
        while chunk := response.read1(16384):
            player.stdin.write(chunk)
        player.stdin.close()
        return player.wait() == 0
    finally:
        if player.poll() is None:
            player.terminate()


def local_speech(text):
    request = urllib.request.Request(
        f"{PIPER_URL}/synthesize",
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return play(response, 22050, "Speaking locally — press the shortcut to stop")


def remote_speech(target, voice_id, text, deadline):
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
        return play(response, rate, "Speaking through PolyTTS — press the shortcut to stop")


def main():
    text = sys.stdin.read().strip()
    if not text:
        return 2
    errors = []
    settings = config()
    deadline = time.monotonic() + float(settings.get("harmony_timeout_seconds", 6))
    for target in settings.get("targets", []):
        try:
            if remote_speech(target, settings.get("voice_id", ""), text, deadline):
                print("backend=harmony-qwen", file=sys.stderr, flush=True)
                return 0
        except (OSError, RuntimeError, KeyError, TimeoutError, urllib.error.URLError) as error:
            errors.append(f"PolyTTS: {error}")
        if time.monotonic() >= deadline:
            break
    try:
        if local_speech(text):
            print("backend=piper-cori", file=sys.stderr, flush=True)
            return 0
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        errors.append(f"local Piper: {error}")
    notify("Every speech backend failed")
    print("\n".join(errors), file=sys.stderr)
    return 1


raise SystemExit(main())
