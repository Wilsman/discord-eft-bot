#!/bin/bash
# Run on the server: pull the latest code, refresh deps and restart.
#   sudo /opt/nerdbot/app/deploy/update.sh [branch]
set -euo pipefail
BRANCH="${1:-main}"
APP=/opt/nerdbot/app

sudo -u nerdbot git -C "$APP" fetch --prune origin
sudo -u nerdbot git -C "$APP" checkout -B "$BRANCH" "origin/$BRANCH"
sudo -u nerdbot /opt/nerdbot/venv/bin/pip install -q --no-cache-dir -r "$APP/requirements.txt"
install -m 644 "$APP/deploy/nerdbot.service" /etc/systemd/system/nerdbot.service
systemctl daemon-reload
systemctl restart nerdbot
sleep 3
systemctl --no-pager --lines=15 status nerdbot
