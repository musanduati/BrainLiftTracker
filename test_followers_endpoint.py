#!/usr/bin/env python
"""Test script for the new followers-gained endpoint"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5555/api/v1"
API_KEY = "test_key_123"  # Replace with your actual API key

def test_followers_gained_endpoint():
    """Test the followers-gained endpoint with various parameters"""
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Test 1: Get followers gained in last 1 day
    print("\n=== Test 1: Followers gained in last 1 day ===")
    response = requests.get(
        f"{BASE_URL}/accounts/followers-gained",
        params={"time_period": "1d"},
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Status: SUCCESS")
        print(f"Time Period: {data.get('time_period')}")
        print(f"From: {data.get('from_date')}")
        print(f"To: {data.get('to_date')}")
        print(f"Summary:")
        print(f"  - Accounts with new followers: {data['summary']['accounts_with_new_followers']}")
        print(f"  - Total new followers: {data['summary']['total_new_followers']}")
        
        if data['accounts']:
            print(f"\nAccounts with new followers:")
            for account in data['accounts'][:3]:  # Show first 3 accounts
                print(f"  @{account['username']}: {account['new_follower_count']} new followers")
                for follower in account['new_followers'][:2]:  # Show first 2 followers
                    print(f"    - @{follower['username']} (joined: {follower['approved_at']})")
    else:
        print(f"Status: FAILED ({response.status_code})")
        print(f"Error: {response.text}")
    
    # Test 2: Get followers gained in last 7 days
    print("\n=== Test 2: Followers gained in last 7 days ===")
    response = requests.get(
        f"{BASE_URL}/accounts/followers-gained",
        params={"time_period": "7d"},
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Status: SUCCESS")
        print(f"Summary:")
        print(f"  - Accounts with new followers: {data['summary']['accounts_with_new_followers']}")
        print(f"  - Total new followers: {data['summary']['total_new_followers']}")
    else:
        print(f"Status: FAILED ({response.status_code})")
    
    # Test 3: Get followers gained in last 24 hours
    print("\n=== Test 3: Followers gained in last 24 hours ===")
    response = requests.get(
        f"{BASE_URL}/accounts/followers-gained",
        params={"time_period": "24h"},
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Status: SUCCESS")
        print(f"Summary:")
        print(f"  - Accounts with new followers: {data['summary']['accounts_with_new_followers']}")
        print(f"  - Total new followers: {data['summary']['total_new_followers']}")
    else:
        print(f"Status: FAILED ({response.status_code})")
    
    # Test 4: Invalid time period
    print("\n=== Test 4: Invalid time period (should fail) ===")
    response = requests.get(
        f"{BASE_URL}/accounts/followers-gained",
        params={"time_period": "invalid"},
        headers=headers
    )
    
    if response.status_code == 400:
        print(f"Status: CORRECTLY FAILED (400)")
        print(f"Error: {response.json().get('error')}")
    else:
        print(f"Status: UNEXPECTED ({response.status_code})")

if __name__ == "__main__":
    print("Testing Followers Gained Endpoint")
    print("==================================")
    test_followers_gained_endpoint()
    print("\n==================================")
    print("Tests completed!")