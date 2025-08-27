#!/bin/bash

# Script to set up the token refresh cron job on Lightsail

echo "Setting up Twitter token refresh cron job..."

# Make the cron script executable
chmod +x /home/ubuntu/twitter-manager/scripts/refresh_tokens_cron.sh

# Create a temporary cron file
CRON_FILE=$(mktemp)

# Get existing cron jobs
crontab -l > "$CRON_FILE" 2>/dev/null || true

# Check if the cron job already exists
if grep -q "refresh_tokens_cron.sh" "$CRON_FILE"; then
    echo "Cron job already exists. Removing old one..."
    grep -v "refresh_tokens_cron.sh" "$CRON_FILE" > "${CRON_FILE}.tmp"
    mv "${CRON_FILE}.tmp" "$CRON_FILE"
fi

# Add the new cron job (runs every hour at minute 0)
echo "0 * * * * /home/ubuntu/twitter-manager/scripts/refresh_tokens_cron.sh >/dev/null 2>&1" >> "$CRON_FILE"

# Install the new cron file
crontab "$CRON_FILE"

# Clean up
rm "$CRON_FILE"

echo "✅ Cron job installed successfully!"
echo "The token refresh will run every hour at the top of the hour."
echo ""
echo "To check the cron job:"
echo "  crontab -l"
echo ""
echo "To view logs:"
echo "  tail -f /home/ubuntu/twitter-manager/logs/token_refresh_cron.log"
echo ""
echo "To test manually:"
echo "  /home/ubuntu/twitter-manager/scripts/refresh_tokens_cron.sh"