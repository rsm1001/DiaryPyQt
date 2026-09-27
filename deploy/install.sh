#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${DIARY_APP_DIR:-/opt/diary-server/app}"
VENV_DIR="${DIARY_VENV_DIR:-/opt/diary-server/venv}"
DATA_DIR="${DIARY_DATA_DIR:-/var/lib/diary-server}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

install -d -o diary -g diary "${APP_DIR}" "${DATA_DIR}/audio" "${DATA_DIR}/backups" "${DATA_DIR}/logs"
python3 -m venv "${VENV_DIR}"
cp -a "${REPO_DIR}/server" "${APP_DIR}/"
cp -a "${REPO_DIR}/shared" "${APP_DIR}/"
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/server/requirements.txt"
install -m 0644 "${REPO_DIR}/deploy/backend.env.example" /etc/diary-server/backend.env.example
install -m 0644 "${REPO_DIR}/deploy/diary-server.service" /etc/systemd/system/diary-server.service
systemctl daemon-reload
systemctl enable diary-server.service
printf '?? backend.env.example ? backend.env????????????\n'
