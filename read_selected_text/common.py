import json
import os
from pathlib import Path


APP = "read-selected-text"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / APP
CONFIG_FILE = CONFIG_DIR / "config.json"
MODEL = DATA_DIR / "voices/en_GB-cori-high.onnx"
DAEMON_URL = "http://127.0.0.1:18788"
PIPER_URL = "http://127.0.0.1:18789"


def config():
    if not CONFIG_FILE.exists():
        return {"voice_id": "", "targets": []}
    return json.loads(CONFIG_FILE.read_text())
