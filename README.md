# Read Selected Text

Select text in any Wayland application, press a shortcut, and hear it aloud.

Read Selected Text is a small Linux desktop utility with:

- system-wide primary-selection reading through `wl-paste`;
- press-again cancellation;
- a warm local [Piper](https://github.com/OHF-Voice/piper1-gpl) fallback;
- optional Harmony/PolyTTS Qwen streaming;
- chunked local synthesis so playback overlaps later generation;
- user-level systemd services.

## Install

Requirements: Python 3.11+, `curl`, `jq`, `wl-clipboard`, `pipewire`, and
`notify-send`.

```bash
./install.sh
```

The installer creates an isolated virtual environment, downloads Piper's
British English `en_GB-cori-high` voice, installs two user services, and places
`read-selected-text` in `~/.local/bin`.

For Hyprland, add:

```lua
o.bind("SUPER + R", "Read selected text", "read-selected-text")
```

## Optional Harmony/PolyTTS backend

Create `~/.config/read-selected-text/config.json`:

```json
{
  "voice_id": "YOUR_QWEN_VOICE_ID",
  "harmony_timeout_seconds": 6,
  "targets": [
    {
      "admit": "http://harmony-host:8799/admit",
      "health": "http://polytts-host:8100/health",
      "stream": "http://polytts-host:8100/tts/stream"
    }
  ]
}
```

No hosts, credentials, cloned voices, or model weights are included in this
repository. Configured Harmony targets are tried first within one shared,
bounded deadline. The warm local voice takes over if Harmony is unavailable,
not resident, or does not begin streaming in time.

## Optional metadata observations

For offline routing experiments, set `READ_SELECTED_TEXT_OBSERVATION_PATH` in
both user services to a writable JSONL path. Observation is disabled when the
variable is absent. Records contain bounded timing, attempt, backend, fallback,
outcome, and cancellation metadata only—never selected text, audio, endpoint
URLs, credentials, or voice content. The producer buffers in memory while audio
starts and writes only during cleanup; the file refuses new records at 1 MiB.

This recorder is evidence only. It cannot choose an engine, voice, route,
fallback, retry, or cancellation action.

## Test

```bash
python -m unittest discover -s tests -v
```

## License

MIT
