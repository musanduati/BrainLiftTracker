# Twitter Manager API - Postman Documentation

This guide provides detailed instructions for testing the Twitter Manager API endpoints using Postman.

## Prerequisites

1. **Flask Server Running**: Ensure the Flask application is running on `http://localhost:5555`
2. **API Key**: `2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb`
3. **Database**: SQLite database with Twitter accounts

## Environment Setup in Postman

### 1. Create Environment Variables

Create a new environment in Postman with the following variables:

```
base_url: http://localhost:5555/api/v1
api_key: 2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb
```

### 2. Collection Setup

Create a new collection called "Twitter Manager API" and add the following headers to the collection:

```
X-API-Key: {{api_key}}
Content-Type: application/json
```

## Working API Endpoints

### 1. Health Check

**Endpoint**: `GET {{base_url}}/health`

**Description**: Check if the API is running

**Headers**: None required (public endpoint)

**Example Response**:
```json
{
    "status": "healthy",
    "timestamp": "2025-07-22T10:00:00.000000",
    "version": "2.0.0-simple"
}
```

---

### 2. Test API Key

**Endpoint**: `GET {{base_url}}/test`

**Description**: Test if your API key is valid

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "status": "success",
    "message": "API key validated!"
}
```

---

### 3. OAuth Authentication

#### Start OAuth Flow

**Endpoint**: `GET {{base_url}}/auth/twitter`

**Description**: Generate Twitter OAuth 2.0 authorization URL with PKCE

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "auth_url": "https://twitter.com/i/oauth2/authorize?response_type=code&client_id=...",
    "state": "secure_random_state_value"
}
```

**Next Steps**:
1. Open the `auth_url` in your browser
2. Log in with Twitter account
3. Authorize the application
4. You'll be redirected to `http://localhost:5555/auth/callback` with a success page

---

### 4. Account Management

#### List All Accounts

**Endpoint**: `GET {{base_url}}/accounts`

**Description**: Get all Twitter accounts

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "accounts": [
        {
            "id": 1,
            "username": "demo_user",
            "status": "active",
            "created_at": "2025-07-22T10:00:00"
        },
        {
            "id": 2,
            "username": "ZeroShotFlow",
            "status": "active",
            "created_at": "2025-07-22T12:31:51.819225"
        }
    ],
    "total": 2
}
```

#### Get Specific Account

**Endpoint**: `GET {{base_url}}/accounts/{account_id}`

**Description**: Get details of a specific account

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example**: `GET {{base_url}}/accounts/2`

**Example Response**:
```json
{
    "id": 2,
    "username": "ZeroShotFlow",
    "status": "active",
    "created_at": "2025-07-22T12:31:51.819225"
}
```

---

### 5. Tweet Management

#### Create Tweet (Pending Status)

**Endpoint**: `POST {{base_url}}/tweet`

**Description**: Create a new tweet with "pending" status

**Headers**:
```
X-API-Key: {{api_key}}
Content-Type: application/json
```

**Body** (raw JSON):
```json
{
    "text": "Hello from Twitter Manager API!",
    "account_id": 2
}
```

**Example Response**:
```json
{
    "message": "Tweet created successfully",
    "tweet_id": 6
}
```

#### Post Tweet to Twitter

**Endpoint**: `POST {{base_url}}/tweet/post/{tweet_id}`

**Description**: Post a pending tweet to Twitter

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example**: `POST {{base_url}}/tweet/post/6`

**Example Response**:
```json
{
    "message": "Tweet posted successfully",
    "tweet_id": 6,
    "twitter_id": "1947673926596731295"
}
```

#### Post All Pending Tweets

**Endpoint**: `POST {{base_url}}/tweets/post-pending`

**Description**: Post all tweets with "pending" status

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "total": 3,
    "posted": 2,
    "failed": 1,
    "details": [
        {
            "tweet_id": 7,
            "status": "posted",
            "twitter_id": "1947673926596731296"
        },
        {
            "tweet_id": 8,
            "status": "posted",
            "twitter_id": "1947673926596731297"
        },
        {
            "tweet_id": 9,
            "status": "failed",
            "error": "Twitter API error (status 401): Unauthorized"
        }
    ]
}
```

#### List All Tweets

**Endpoint**: `GET {{base_url}}/tweets`

**Description**: Get all tweets (max 50)

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "tweets": [
        {
            "id": 5,
            "text": "Hello from Twitter Manager API and Postman!",
            "status": "posted",
            "created_at": "2025-07-22T15:01:57.848184",
            "username": "ZeroShotFlow"
        },
        {
            "id": 4,
            "text": "Hello from Twitter Manager API! Testing real posting functionality.",
            "status": "failed",
            "created_at": "2025-07-22T14:46:00.111614",
            "username": "ZeroShotFlow"
        }
    ],
    "total": 5
}
```

---

### 6. Statistics

**Endpoint**: `GET {{base_url}}/stats`

**Description**: Get overall statistics

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "accounts": {
        "total": 2,
        "active": 2
    },
    "tweets": {
        "total": 5,
        "pending": 0,
        "posted": 3,
        "failed": 2
    }
}
```

---

### 7. Mock Mode Control

#### Check Mock Mode Status

**Endpoint**: `GET {{base_url}}/mock-mode`

**Description**: Check if mock mode is enabled

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "mock_mode": false
}
```

#### Toggle Mock Mode

**Endpoint**: `POST {{base_url}}/mock-mode`

**Description**: Enable or disable mock mode

**Headers**:
```
X-API-Key: {{api_key}}
Content-Type: application/json
```

**Body** (raw JSON):
```json
{
    "enabled": true
}
```

**Example Response**:
```json
{
    "message": "Mock mode enabled",
    "mock_mode": true
}
```

---

### 8. Cleanup Operations

#### Delete Account

**Endpoint**: `DELETE {{base_url}}/accounts/{account_id}`

**Description**: Delete a specific account and all its associated tweets

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "message": "Account @ZeroShotFlow deleted successfully",
    "deleted_tweets": 5
}
```

#### Cleanup Inactive Accounts

**Endpoint**: `POST {{base_url}}/accounts/cleanup`

**Description**: Delete all accounts with specified statuses

**Headers**:
```
X-API-Key: {{api_key}}
Content-Type: application/json
```

**Body** (raw JSON):
```json
{
    "statuses": ["failed", "suspended", "inactive"]
}
```

**Example Response**:
```json
{
    "message": "Cleaned up 2 inactive accounts",
    "results": {
        "deleted_accounts": [
            {
                "id": 3,
                "username": "failed_account",
                "status": "failed",
                "deleted_tweets": 10
            }
        ],
        "deleted_tweets_total": 10
    }
}
```

#### Delete Tweet

**Endpoint**: `DELETE {{base_url}}/tweets/{tweet_id}`

**Description**: Delete a specific tweet

**Headers**:
```
X-API-Key: {{api_key}}
```

**Example Response**:
```json
{
    "message": "Tweet deleted successfully",
    "tweet": {
        "id": 5,
        "content": "Hello from Twitter Manager API and Postman!",
        "status": "posted"
    }
}
```

#### Cleanup Tweets

**Endpoint**: `POST {{base_url}}/tweets/cleanup`

**Description**: Delete tweets by various criteria

**Headers**:
```
X-API-Key: {{api_key}}
Content-Type: application/json
```

**Examples**:

1. **Delete by Status**:
```json
{
    "statuses": ["failed"]
}
```

2. **Delete by Age**:
```json
{
    "days_old": 30
}
```

3. **Combined Criteria**:
```json
{
    "statuses": ["posted"],
    "days_old": 7,
    "account_id": 2
}
```

**Example Response**:
```json
{
    "message": "Deleted 15 tweets",
    "criteria": {
        "statuses": ["posted"],
        "days_old": 7,
        "account_id": 2
    }
}
```

---

## Tweet Status Lifecycle

1. **pending** - Tweet created but not posted to Twitter
2. **posted** - Successfully posted to Twitter (includes twitter_id)
3. **failed** - Posting attempt failed

## Testing Workflow

### 1. Complete OAuth Flow
1. GET `/auth/twitter` - Get OAuth URL
2. Open URL in browser and authorize
3. Check `/accounts` to see the new account

### 2. Post a Tweet
1. POST `/tweet` - Create a pending tweet
2. POST `/tweet/post/{id}` - Post it to Twitter
3. GET `/tweets` - Verify status changed to "posted"

### 3. Batch Posting
1. Create multiple pending tweets
2. POST `/tweets/post-pending` - Post all at once
3. Check results in the response

## Error Responses

### 401 Unauthorized
```json
{
    "error": "Invalid API key"
}
```

### 400 Bad Request
```json
{
    "error": "Missing text or account_id"
}
```

### 404 Not Found
```json
{
    "error": "Tweet not found or already posted"
}
```

### 500 Internal Server Error
```json
{
    "error": "Database error message"
}
```

## Important Notes

1. **Mock Mode**: By default, mock mode is DISABLED. Tweets will be posted to real Twitter accounts.
2. **OAuth 2.0 Only**: The app only supports OAuth 2.0. OAuth 1.0a accounts need to re-authorize.
3. **Rate Limits**: Be aware of Twitter's rate limits when testing.
4. **Token Expiry**: If you get 401 errors when posting, re-authorize the account.

## Quick Test Commands

Using curl instead of Postman:

```bash
# Health check
curl http://localhost:5555/api/v1/health

# List accounts
curl -H "X-API-Key: 2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb" \
  http://localhost:5555/api/v1/accounts

# Create tweet
curl -X POST http://localhost:5555/api/v1/tweet \
  -H "X-API-Key: 2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test tweet", "account_id": 2}'

# Post tweet
curl -X POST http://localhost:5555/api/v1/tweet/post/6 \
  -H "X-API-Key: 2043adb52a7468621a9245c94d702e4bed5866b0ec52772f203286f823a50bbb"
```