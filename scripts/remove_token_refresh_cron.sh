#!/bin/bash

# Script to remove the token refresh cron job

echo "Removing Twitter token refresh cron job..."

# Create a temporary cron file
CRON_FILE=$(mktemp)

# Get existing cron jobs and remove the token refresh one
crontab -l 2>/dev/null | grep -v "refresh_tokens_cron.sh" > "$CRON_FILE"

# Install the updated cron file
crontab "$CRON_FILE"

# Clean up
rm "$CRON_FILE"

echo "✅ Token refresh cron job removed successfully!"
echo ""
echo "To verify:"
echo "  crontab -l"