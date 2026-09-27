#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DIARY_DATA_DIR:-/var/lib/diary-server}"
BACKUP_DIR="${DIARY_BACKUP_DIR:-${DATA_DIR}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${BACKUP_DIR}"
tar -czf "${BACKUP_DIR}/diary-${STAMP}.tar.gz" -C "${DATA_DIR}" diary_server.db audio
find "${BACKUP_DIR}" -type f -name 'diary-*.tar.gz' -mtime +30 -delete
