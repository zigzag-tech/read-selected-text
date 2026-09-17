#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/read-selected-text"
bin_dir="$HOME/.local/bin"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
voice_dir="$data_dir/voices"

mkdir -p "$data_dir" "$bin_dir" "$unit_dir" "$voice_dir"
python3 -m venv "$data_dir/venv"
"$data_dir/venv/bin/pip" install --upgrade pip
"$data_dir/venv/bin/pip" install 'piper-tts==1.8.0'
"$data_dir/venv/bin/python" -m piper.download_voices en_GB-cori-high --download-dir "$voice_dir"

ln -sfn "$repo_dir" "$data_dir/app"
ln -sfn "$repo_dir/read-selected-text" "$bin_dir/read-selected-text"
install -m 0644 "$repo_dir/systemd/read-selected-text.service" "$unit_dir/"
install -m 0644 "$repo_dir/systemd/read-selected-text-piper.service" "$unit_dir/"

systemctl --user daemon-reload
systemctl --user enable --now read-selected-text-piper.service read-selected-text.service

echo "Installed read-selected-text in $bin_dir"
echo 'Bind your desktop shortcut to: read-selected-text'
