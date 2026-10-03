#!/usr/bin/env bash
set -euo pipefail

# Source .env from project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="spt_hrms_backup_${TIMESTAMP}.sql.gz"

echo "Creating PostgreSQL backup..."
docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-spt_user}" "${POSTGRES_DB:-spt_hrms}" | gzip > "$BACKUP_DIR/$FILENAME"

echo "✓ Backup saved: $BACKUP_DIR/$FILENAME"
echo "  Size: $(du -h "$BACKUP_DIR/$FILENAME" | cut -f1)"

# Keep only last 30 backups
ls -t "$BACKUP_DIR"/spt_hrms_backup_*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm
echo "✓ Old backups cleaned (keeping last 30)"
