#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$SCRIPT_DIR}"
SERVICE_USER="${SERVICE_USER:-$(id -un)}"

cd "$APP_DIR"

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -e .

if [ ! -f "$APP_DIR/config.json" ]; then
  cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"
fi

sed \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  -e "s|__SERVICE_USER__|$SERVICE_USER|g" \
  "$APP_DIR/systemd/fsm60-gateway.service" > "$APP_DIR/fsm60-gateway.service"

echo "Installed to $APP_DIR"
echo "Edit config: nano $APP_DIR/config.json"
echo "Run test: $APP_DIR/venv/bin/fsm60-gateway --config $APP_DIR/config.json"
echo ""
echo "To register systemd service:"
echo "  sudo cp $APP_DIR/fsm60-gateway.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable fsm60-gateway"
echo "  sudo systemctl start fsm60-gateway"
