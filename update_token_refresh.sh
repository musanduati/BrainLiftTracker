#!/bin/bash
# Quick update script for token refresh feature
# For existing deployments

set -e

echo "Updating Twitter Manager with Token Refresh feature..."

# Backup database first
echo "Backing up database..."
cp instance/twitter_manager.db instance/twitter_manager.db.backup.$(date +%Y%m%d_%H%M%S)

# Pull latest or copy files
if [ -d .git ]; then
    echo "Pulling latest changes..."
    git pull
else
    echo "Please manually copy the updated files:"
    echo "  - app.py"
    echo "  - monitor_tokens.py"
    echo "  - CLAUDE.md"
fi

# Make monitor script executable
if [ -f monitor_tokens.py ]; then
    chmod +x monitor_tokens.py
    echo "Token monitor script made executable"
fi

# Add to crontab if not already present
if ! crontab -l 2>/dev/null | grep -q "monitor_tokens.py"; then
    echo "Adding token monitoring to crontab..."
    (crontab -l 2>/dev/null; echo "*/30 * * * * cd $(pwd) && /usr/bin/python3 monitor_tokens.py >> logs/token_monitor.log 2>&1") | crontab -
    echo "Token monitoring cron job added"
else
    echo "Token monitoring already in crontab"
fi

# Restart services
echo "Restarting services..."
sudo systemctl restart twitter-manager
sudo systemctl restart nginx

echo ""
echo "Update complete!"
echo ""
echo "New endpoints available:"
echo "  GET  /api/v1/accounts/token-health"
echo "  POST /api/v1/accounts/{id}/refresh-token"
echo "  POST /api/v1/accounts/refresh-tokens"
echo "  POST /api/v1/accounts/{id}/clear-failures"
echo ""
echo "Check token health with:"
echo "  curl -X GET http://localhost:5555/api/v1/accounts/token-health -H \"X-API-Key: your-api-key\""
echo ""
echo "Monitor logs at: logs/token_monitor.log"