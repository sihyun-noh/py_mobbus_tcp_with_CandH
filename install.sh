#!/usr/bin/env bash
set -e

APP_DIR="/opt/fsm60-gateway"

sudo mkdir -p "$APP_DIR"
sudo cp -r . "$APP_DIR"
cd "$APP_DIR"

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -e .

if [ ! -f "$APP_DIR/config.json" ]; then
  sudo cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"
fi

echo "Installed to $APP_DIR"
echo "Edit config: sudo nano $APP_DIR/config.json"
echo "Run test: $APP_DIR/venv/bin/fsm60-gateway --config $APP_DIR/config.json"
