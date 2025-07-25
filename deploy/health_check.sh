#!/bin/bash
# Twitter Manager Health Check Script
# This script monitors the application and sends alerts if issues are detected

# Configuration
API_URL="http://localhost/api/v1/health"
API_KEY=${API_KEY:-"your-api-key"}  # Set this in environment or update here
LOG_FILE="/home/ubuntu/twitter-manager/logs/health_check.log"
SLACK_WEBHOOK=""  # Optional: Add Slack webhook for alerts

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> $LOG_FILE
    echo -e "$1"
}

# Function to send alert (customize as needed)
send_alert() {
    local message=$1
    
    # Log to file
    log "ALERT: $message"
    
    # Send to Slack if webhook is configured
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Twitter Manager Alert: $message\"}" \
            $SLACK_WEBHOOK 2>/dev/null
    fi
    
    # Send email (if mail is configured)
    # echo "$message" | mail -s "Twitter Manager Alert" admin@example.com
}

echo -e "${YELLOW}Twitter Manager Health Check${NC}"
echo "================================"

# 1. Check if services are running
echo -n "Checking Gunicorn service... "
if systemctl is-active --quiet twitter-manager; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    send_alert "Gunicorn service is not running!"
    sudo systemctl start twitter-manager
fi

echo -n "Checking Nginx service... "
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    send_alert "Nginx service is not running!"
    sudo systemctl start nginx
fi

# 2. Check API health endpoint
echo -n "Checking API health endpoint... "
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)
if [ "$HTTP_STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ Healthy (HTTP $HTTP_STATUS)${NC}"
else
    echo -e "${RED}✗ Unhealthy (HTTP $HTTP_STATUS)${NC}"
    send_alert "API health check failed with HTTP status $HTTP_STATUS"
fi

# 3. Check API with authentication
echo -n "Checking authenticated API endpoint... "
AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" http://localhost/api/v1/test)
if [ "$AUTH_STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ Authentication working${NC}"
else
    echo -e "${RED}✗ Authentication failed (HTTP $AUTH_STATUS)${NC}"
    log "Warning: API authentication check failed"
fi

# 4. Check disk space
echo -n "Checking disk space... "
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✓ ${DISK_USAGE}% used${NC}"
else
    echo -e "${RED}✗ ${DISK_USAGE}% used (Low space!)${NC}"
    send_alert "Disk usage is at ${DISK_USAGE}%"
fi

# 5. Check memory usage
echo -n "Checking memory usage... "
MEMORY_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
if [ "$MEMORY_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✓ ${MEMORY_USAGE}% used${NC}"
else
    echo -e "${YELLOW}⚠ ${MEMORY_USAGE}% used${NC}"
    if [ "$MEMORY_USAGE" -gt 90 ]; then
        send_alert "Memory usage is at ${MEMORY_USAGE}%"
    fi
fi

# 6. Check database file
echo -n "Checking database file... "
DB_PATH="/home/ubuntu/twitter-manager/instance/twitter_manager.db"
if [ -f "$DB_PATH" ]; then
    DB_SIZE=$(ls -lh $DB_PATH | awk '{print $5}')
    echo -e "${GREEN}✓ Exists (Size: $DB_SIZE)${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    send_alert "Database file not found!"
fi

# 7. Check recent errors in logs
echo -n "Checking for recent errors... "
ERROR_COUNT=$(tail -n 100 /home/ubuntu/twitter-manager/logs/twitter_manager.log 2>/dev/null | grep -i error | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ No recent errors${NC}"
else
    echo -e "${YELLOW}⚠ Found $ERROR_COUNT errors in last 100 log lines${NC}"
    if [ "$ERROR_COUNT" -gt 10 ]; then
        send_alert "Found $ERROR_COUNT errors in application logs"
    fi
fi

# 8. Check SSL certificate expiry (if HTTPS is configured)
if [ -f "/etc/letsencrypt/live/*/cert.pem" ]; then
    echo -n "Checking SSL certificate... "
    CERT_FILE=$(ls /etc/letsencrypt/live/*/cert.pem | head -n1)
    EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$CERT_FILE" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
    CURRENT_EPOCH=$(date +%s)
    DAYS_LEFT=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))
    
    if [ "$DAYS_LEFT" -gt 14 ]; then
        echo -e "${GREEN}✓ Valid for $DAYS_LEFT more days${NC}"
    else
        echo -e "${RED}✗ Expires in $DAYS_LEFT days!${NC}"
        send_alert "SSL certificate expires in $DAYS_LEFT days"
    fi
fi

# 9. Summary
echo ""
echo "Health Check Summary:"
echo "--------------------"
log "Health check completed - All systems checked"

# Exit with appropriate code
if [ "$HTTP_STATUS" -eq 200 ] && [ "$DISK_USAGE" -lt 90 ]; then
    exit 0
else
    exit 1
fi