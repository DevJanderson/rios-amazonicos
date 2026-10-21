#!/usr/bin/env bash
# Install the project's systemd user units (collection timer + marimo server).
set -euo pipefail

ORIGEM="$(cd "$(dirname "$0")/systemd" && pwd)"
DESTINO="$HOME/.config/systemd/user"
mkdir -p "$DESTINO"
for unidade in "$ORIGEM"/*; do
  ln -sfn "$unidade" "$DESTINO/$(basename "$unidade")"
done
systemctl --user daemon-reload
systemctl --user enable --now rios-coleta.timer rios-marimo.service
systemctl --user list-timers rios-coleta.timer --no-pager
