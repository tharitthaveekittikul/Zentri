#!/bin/bash
set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./scripts/restore.sh ./backups/zentri-YYYY-MM-DD_HH-MM-SS.tar.gz"
    exit 1
fi

echo "This will overwrite your current Zentri data. Continue? (y/N)"
read -r confirm
if [ "$confirm" != "y" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Extracting backup..."
tar -xzf "$BACKUP_FILE" -C /tmp

echo "Restoring database..."
docker compose exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS zentri;"
docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE zentri;"
docker compose exec -T postgres psql -U postgres zentri < /tmp/zentri_db.sql
rm /tmp/zentri_db.sql

echo "Restore complete. Restart services: docker compose restart backend worker"
