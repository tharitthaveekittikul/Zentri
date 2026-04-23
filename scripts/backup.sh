#!/bin/bash
set -e

DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="./backups"
BACKUP_FILE="$BACKUP_DIR/zentri-$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "Backing up Zentri data..."

# Dump PostgreSQL
docker compose exec -T postgres pg_dump -U postgres zentri > /tmp/zentri_db.sql
echo "Database dumped"

# Create archive with DB dump
tar -czf "$BACKUP_FILE" -C /tmp zentri_db.sql
rm /tmp/zentri_db.sql

echo "Backup saved to $BACKUP_FILE"
echo "Size: $(du -sh $BACKUP_FILE | cut -f1)"
