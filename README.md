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
repository. The warm local voice is currently the latency-first path; remote
targets are attempted only if it fails.

## Test

```bash
python -m unittest discover -s tests -v
```

## License

MIT
