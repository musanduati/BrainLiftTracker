#!/bin/bash

# Cron script to refresh Twitter tokens hourly
# This script calls the batch refresh tokens endpoint

# Configuration
API_BASE_URL="http://localhost/api/v1"
API_KEY="6b6fea7c92a74e005a3c59a0834948c7cab4f50be333a68e852f09314120243d"
LOG_FILE="/home/ubuntu/twitter-manager/logs/token_refresh_cron.log"

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

log "Starting token refresh cron job"

# Make the API call
response=$(curl -s -w "\n%{http_code}" -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    "$API_BASE_URL/accounts/refresh-tokens")

# Extract HTTP status code (last line)
http_code=$(echo "$response" | tail -n1)

# Extract response body (all but last line)  
response_body=$(echo "$response" | head -n -1)

# Log the results
if [ "$http_code" = "200" ]; then
    log "SUCCESS: Token refresh completed. Response: $response_body"
else
    log "ERROR: Token refresh failed with HTTP $http_code. Response: $response_body"
fi

log "Token refresh cron job completed"