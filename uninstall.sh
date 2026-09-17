#!/usr/bin/env bash
set -euo pipefail

data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/read-selected-text"
bin_dir="$HOME/.local/bin"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

systemctl --user disable --now read-selected-text.service read-selected-text-piper.service 2>/dev/null || true
rm -f "$unit_dir/read-selected-text.service" "$unit_dir/read-selected-text-piper.service"
rm -f "$bin_dir/read-selected-text"
systemctl --user daemon-reload

echo "Services and launcher removed. Voice data remains in $data_dir"
