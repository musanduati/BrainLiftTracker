#!/usr/bin/env python3
"""
Token Health Monitor
Run this script periodically (e.g., every 30 minutes via cron) to:
1. Check token health for all accounts
2. Automatically refresh expiring tokens
3. Send alerts for accounts with issues

Example cron entry:
*/30 * * * * /usr/bin/python3 /path/to/monitor_tokens.py >> /var/log/token_monitor.log 2>&1
"""

import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:5555/api/v1')
API_KEY = os.getenv('API_KEY')

if not API_KEY:
    print("ERROR: API_KEY not found in environment")
    exit(1)

headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}

def check_token_health():
    """Check health status of all tokens"""
    try:
        response = requests.get(f'{API_BASE_URL}/accounts/token-health', headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error checking token health: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception checking token health: {e}")
        return None

def refresh_expiring_tokens():
    """Refresh all tokens that are expiring soon"""
    try:
        response = requests.post(f'{API_BASE_URL}/accounts/refresh-tokens', headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error refreshing tokens: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception refreshing tokens: {e}")
        return None

def send_alert(message, level='WARNING'):
    """Send alert (customize this based on your alerting system)"""
    # You can integrate with:
    # - Email (using smtplib)
    # - Slack webhook
    # - Discord webhook
    # - PagerDuty
    # - AWS SNS
    # - etc.
    
    # For now, just print with timestamp
    timestamp = datetime.utcnow().isoformat()
    print(f"[{timestamp}] {level}: {message}")
    
    # Example webhook implementation:
    # webhook_url = os.getenv('ALERT_WEBHOOK_URL')
    # if webhook_url:
    #     requests.post(webhook_url, json={'text': f"{level}: {message}"})

def main():
    print(f"\n{'='*60}")
    print(f"Token Health Monitor - {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")
    
    # Step 1: Check token health
    health_data = check_token_health()
    if not health_data:
        send_alert("Failed to check token health", "ERROR")
        return
    
    summary = health_data['summary']
    print(f"\nToken Health Summary:")
    print(f"  Total accounts: {summary['total_accounts']}")
    print(f"  Healthy: {summary['healthy']}")
    print(f"  Expiring soon: {summary['expiring_soon']}")
    print(f"  Expired: {summary['expired']}")
    print(f"  Refresh failures: {summary['refresh_failures']}")
    print(f"  No refresh token: {summary['no_refresh_token']}")
    
    # Step 2: Send alerts for critical issues
    if summary['expired'] > 0:
        expired_accounts = health_data['details']['expired']
        usernames = [acc['username'] for acc in expired_accounts]
        send_alert(f"{summary['expired']} accounts have expired tokens: {', '.join(usernames)}", "ERROR")
    
    if summary['refresh_failures'] > 0:
        failed_accounts = health_data['details']['refresh_failures']
        for acc in failed_accounts:
            send_alert(
                f"Account {acc['username']} has {acc['failure_count']} refresh failures", 
                "WARNING"
            )
    
    if summary['no_refresh_token'] > 0:
        no_refresh = health_data['details']['no_refresh_token']
        usernames = [acc['username'] for acc in no_refresh]
        send_alert(
            f"{summary['no_refresh_token']} accounts need re-authorization (no refresh token): {', '.join(usernames)}", 
            "WARNING"
        )
    
    # Step 3: Refresh expiring tokens
    if summary['expiring_soon'] > 0 or summary['expired'] > 0:
        print(f"\nRefreshing {summary['expiring_soon'] + summary['expired']} expiring/expired tokens...")
        refresh_result = refresh_expiring_tokens()
        
        if refresh_result:
            results = refresh_result['results']
            print(f"  Processed: {results['total']}")
            print(f"  Success: {results['success']}")
            print(f"  Failed: {results['failed']}")
            
            if results['failed'] > 0:
                failed_usernames = [
                    d['username'] for d in results['details'] 
                    if d['status'] == 'failed'
                ]
                send_alert(
                    f"Failed to refresh tokens for {results['failed']} accounts: {', '.join(failed_usernames)}", 
                    "ERROR"
                )
        else:
            send_alert("Failed to refresh expiring tokens", "ERROR")
    else:
        print("\nNo tokens need refreshing at this time.")
    
    print(f"\nMonitoring complete at {datetime.utcnow().isoformat()}")

if __name__ == "__main__":
    main()