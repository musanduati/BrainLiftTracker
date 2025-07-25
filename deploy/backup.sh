#!/bin/bash
# Twitter Manager Database Backup Script
# This script backs up the SQLite database with rotation

# Configuration
APP_DIR="/home/ubuntu/twitter-manager"
DB_PATH="$APP_DIR/instance/twitter_manager.db"
BACKUP_DIR="$APP_DIR/backups"
MAX_BACKUPS=7  # Keep 7 days of backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="twitter_manager_backup_$TIMESTAMP.db"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}Error: Database not found at $DB_PATH${NC}"
    exit 1
fi

# Create backup
echo "Creating backup: $BACKUP_NAME"
cp $DB_PATH "$BACKUP_DIR/$BACKUP_NAME"

# Compress the backup
gzip "$BACKUP_DIR/$BACKUP_NAME"
BACKUP_NAME="$BACKUP_NAME.gz"

# Verify backup was created
if [ -f "$BACKUP_DIR/$BACKUP_NAME" ]; then
    echo -e "${GREEN}Backup created successfully: $BACKUP_DIR/$BACKUP_NAME${NC}"
    
    # Get backup size
    BACKUP_SIZE=$(ls -lh "$BACKUP_DIR/$BACKUP_NAME" | awk '{print $5}')
    echo "Backup size: $BACKUP_SIZE"
else
    echo -e "${RED}Error: Backup creation failed${NC}"
    exit 1
fi

# Rotate old backups (keep only MAX_BACKUPS)
echo "Rotating old backups (keeping last $MAX_BACKUPS)..."
cd $BACKUP_DIR
ls -t twitter_manager_backup_*.db.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -v

# Optional: Copy to S3 (uncomment and configure if using S3)
# if command -v aws &> /dev/null; then
#     echo "Uploading to S3..."
#     aws s3 cp "$BACKUP_DIR/$BACKUP_NAME" s3://your-bucket-name/twitter-manager-backups/
# fi

# Log backup completion
echo "$(date): Backup completed - $BACKUP_NAME" >> "$APP_DIR/logs/backup.log"

# Display backup summary
echo ""
echo "Backup Summary:"
echo "---------------"
echo "Current backups in $BACKUP_DIR:"
ls -lht $BACKUP_DIR/*.gz | head -n $MAX_BACKUPS