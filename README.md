# Twitter Manager API

A Flask-based RESTful API for managing multiple Twitter accounts and posting content via Twitter API v2. This application supports OAuth 2.0 authentication with PKCE, encrypted token storage, and real-time posting to Twitter/X.

> **Important**: Run the application using `python app.py` on port 5555.

## Features

- **Multi-Account Management**: Add and manage multiple Twitter accounts
- **OAuth 2.0 Authentication**: Secure Twitter authentication flow with PKCE
- **Real-Time Tweet Posting**: Post tweets directly to Twitter/X
- **Twitter Threads**: Create and post multi-tweet threads with automatic reply chaining
- **Batch Operations**: Post all pending tweets at once
- **Twitter Lists**: Create and manage Twitter lists with multiple main accounts
- **List Membership**: Add/remove accounts to/from lists with bulk operations
- **Account Types**: Designate accounts as list owners or managed accounts
- **Encryption**: Secure storage of credentials using Fernet encryption
- **Automatic Token Refresh**: OAuth tokens refresh automatically when expired
- **Token Health Monitoring**: Track token expiry and health status across all accounts
- **API Authentication**: Secure API access with API keys
- **Statistics**: Track tweet counts and posting status
- **Rate Limiting Protection**: Automatic tracking and prevention of Twitter API 429 errors
- **Failed Tweet Recovery**: Retry or reset failed tweets without data loss

## Requirements

- Python 3.8+
- Twitter Developer Account with OAuth 2.0 app configured

## Installation

1. Clone the repository:
```bash
cd twitter-manager
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy environment template:
```bash
cp .env.example .env
```

5. Configure environment variables in `.env`:
```env
# Generate your own API key (e.g., using: python -c "import secrets; print(secrets.token_hex(32))")
API_KEY=your-api-key

# Generate encryption key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-encryption-key

# Twitter API credentials from Developer Portal
TWITTER_CLIENT_ID=your-twitter-client-id
TWITTER_CLIENT_SECRET=your-twitter-client-secret
TWITTER_CALLBACK_URL=http://localhost:5555/auth/callback
```

## Running the Application

### Development Server
```bash
python app.py
```
The API will be available at `http://localhost:5555/api/v1/`

The application will automatically create the SQLite database on first run.

## API Endpoints

### Health Check
```http
GET /api/v1/health
```

### Account Management

#### Add Account via OAuth 2.0

#### Start OAuth Flow
```http
GET /api/v1/auth/twitter
X-API-Key: your-api-key
```

Returns:
```json
{
    "auth_url": "https://twitter.com/i/oauth2/authorize?...",
    "state": "secure-random-state"
}
```

#### OAuth Callback (Automatic)
```
GET /auth/callback?code=XXX&state=XXX
```

This endpoint is called automatically by Twitter after authorization. It displays a success page with instructions.

#### List Accounts
```http
GET /api/v1/accounts
X-API-Key: your-api-key
```

#### Get Account Details
```http
GET /api/v1/accounts/{account_id}
X-API-Key: your-api-key
```


### Tweet Management

#### Create Tweet (Pending)
```http
POST /api/v1/tweet
X-API-Key: your-api-key
Content-Type: application/json

{
    "text": "Hello from Twitter Manager API!",
    "account_id": 1
}
```

Creates a tweet with "pending" status. Returns:
```json
{
    "message": "Tweet created successfully",
    "tweet_id": 5
}
```

#### Post Single Tweet to Twitter
```http
POST /api/v1/tweet/post/{tweet_id}
X-API-Key: your-api-key
```

Posts a specific pending tweet to Twitter. Returns:
```json
{
    "message": "Tweet posted successfully",
    "tweet_id": 5,
    "twitter_id": "1947673926596731295"
}
```

#### Post All Pending Tweets (Batch Mode)
```http
POST /api/v1/tweets/post-pending
X-API-Key: your-api-key
Content-Type: application/json

{
    "batch_size": 10,    // Optional: Number of tweets per batch (default: 10, max: 50)
    "offset": 0          // Optional: Starting position for pagination (default: 0)
}
```

Posts tweets with "pending" status in batches to prevent timeouts. Returns:
```json
{
    "total_pending": 25,
    "batch_size": 10,
    "offset": 0,
    "processed": 10,
    "posted": 8,
    "failed": 2,
    "has_more": true,    // Indicates if more tweets need processing
    "details": [...]
}
```

To process all tweets, continue calling with incremented offset until `has_more` is false.

#### Post All Pending Tweets (Async/Background)
```http
POST /api/v1/tweets/post-pending-async
X-API-Key: your-api-key
Content-Type: application/json

{
    "batch_size": 20    // Optional: Number of tweets per batch (default: 10, max: 50)
}
```

Starts a background job to post all pending tweets without timeout issues. Returns immediately:
```json
{
    "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "started",
    "total_pending": 150,
    "message": "Background job started. Use /api/v1/jobs/{job_id} to check status."
}
```

#### Check Background Job Status
```http
GET /api/v1/jobs/{job_id}
X-API-Key: your-api-key
```

Check the status of a background tweet posting job:
```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "running",    // Options: pending, running, completed, failed
    "total_pending": 150,
    "posted": 45,
    "failed": 5,
    "processed": 50,
    "batch_size": 20,
    "created_at": "2024-01-20T10:30:00Z",
    "started_at": "2024-01-20T10:30:01Z",
    "completed_at": null    // Set when job finishes
}
```

#### Check Twitter Account Status
```http
GET /api/v1/accounts/check-twitter-status
X-API-Key: your-api-key
```

Check if your Twitter accounts are active, suspended, locked, restricted, or have other issues. Problematic accounts are listed by username:
```json
{
    "summary": {
        "total": 5,
        "active": 2,
        "suspended": ["suspended_user"],
        "locked": ["locked_user"],
        "restricted": [],
        "protected": 1,
        "deactivated": [],
        "token_expired": ["expired_token_user", "another_expired"],
        "unauthorized": ["revoked_user"],
        "other_issues": ["error_user"]
    },
    "accounts": [
        {
            "id": 1,
            "username": "example_user",
            "twitter_status": "active",
            "error": null,
            "metrics": {
                "followers_count": 1234,
                "following_count": 567,
                "tweet_count": 890
            }
        },
        {
            "id": 2,
            "username": "suspended_user",
            "twitter_status": "suspended",
            "error": "User has been suspended: suspended_user"
        },
        {
            "id": 3,
            "username": "locked_user",
            "twitter_status": "locked",
            "error": "Account is locked"
        },
        {
            "id": 4,
            "username": "protected_user",
            "twitter_status": "protected",
            "error": null,
            "checked_at": "2024-01-20T10:30:03Z"
        }
    ]
}
```

#### Check Rate Limit Status
```http
GET /api/v1/rate-limits
X-API-Key: your-api-key
```

Monitor rate limit status for all accounts to avoid 429 errors:
```json
{
    "rate_limits": [
        {
            "account_id": 1,
            "username": "example_user",
            "tweets_posted": 45,
            "tweets_remaining": 135,
            "reset_in_seconds": 720,
            "reset_at": "2024-01-20T10:45:00",
            "current_delay": 1
        }
    ],
    "timestamp": "2024-01-20T10:30:00Z"
}
```

#### Retry Failed Tweets

##### Retry Single Failed Tweet
```http
POST /api/v1/tweet/retry/{tweet_id}
X-API-Key: your-api-key
```

Attempts to repost a specific failed tweet. Returns:
```json
{
    "message": "Tweet posted successfully on retry",
    "tweet_id": 123,
    "twitter_id": "1947673926596731295"
}
```

##### Retry Multiple Failed Tweets
```http
POST /api/v1/tweets/retry-failed
X-API-Key: your-api-key
Content-Type: application/json

{
    "batch_size": 10,       // Optional: default 10, max 50
    "offset": 0,            // Optional: for pagination
    "account_id": 5         // Optional: retry only for specific account
}
```

Retries failed tweets in batches. Returns:
```json
{
    "total_failed": 25,
    "batch_size": 10,
    "offset": 0,
    "processed": 10,
    "posted": 7,
    "still_failed": 3,
    "has_more": true,
    "details": [...]
}
```

##### Reset Failed Tweets to Pending
```http
POST /api/v1/tweets/reset-failed
X-API-Key: your-api-key
Content-Type: application/json

{
    "tweet_ids": [123, 456],    // Option 1: Specific tweet IDs
    "account_id": 5,            // Option 2: All failed for an account
    "days_old": 7               // Option 3: Failed tweets older than X days
}
```

Resets failed tweets back to pending status so they can be posted again:
```json
{
    "message": "Reset 15 failed tweets to pending status",
    "count": 15
}
```

#### Mock Mode Control
```http
GET /api/v1/mock-mode
X-API-Key: your-api-key
```

Check if mock mode is enabled (currently disabled by default).

```http
POST /api/v1/mock-mode
X-API-Key: your-api-key
Content-Type: application/json

{
    "enabled": true
}
```

Toggle mock mode for testing without real Twitter posts.

### Twitter Threads

#### Create a Thread
```http
POST /api/v1/thread
X-API-Key: your-api-key
Content-Type: application/json

{
    "account_id": 1,
    "tweets": [
        "🧵 1/3 Here's an important update about our product launch...",
        "2/3 We've been working hard on new features including...",
        "3/3 Sign up for early access at our website! Thanks for your support!"
    ]
}
```

Creates a thread of connected tweets. Returns:
```json
{
    "message": "Thread created with 3 tweets",
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "tweets": [
        {"id": 1, "position": 0, "content": "🧵 1/3 Here's an important update..."},
        {"id": 2, "position": 1, "content": "2/3 We've been working hard..."},
        {"id": 3, "position": 2, "content": "3/3 Sign up for early access..."}
    ]
}
```

#### Post a Thread to Twitter
```http
POST /api/v1/thread/post/{thread_id}
X-API-Key: your-api-key
```

Posts all pending tweets in a thread to Twitter, with each tweet replying to the previous one. Returns:
```json
{
    "message": "Thread posting completed",
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "posted": 3,
    "failed": 0,
    "tweets": [
        {
            "tweet_id": 1,
            "twitter_id": "1234567890123456789",
            "position": 0,
            "status": "posted"
        },
        {
            "tweet_id": 2,
            "twitter_id": "1234567890123456790",
            "position": 1,
            "status": "posted"
        },
        {
            "tweet_id": 3,
            "twitter_id": "1234567890123456791",
            "position": 2,
            "status": "posted"
        }
    ]
}
```

#### Get All Threads
```http
GET /api/v1/threads
X-API-Key: your-api-key
```

Returns a list of all threads with their status:
```json
{
    "threads": [
        {
            "thread_id": "550e8400-e29b-41d4-a716-446655440000",
            "account_id": 1,
            "account_username": "@myaccount",
            "tweet_count": 3,
            "posted_count": 3,
            "pending_count": 0,
            "failed_count": 0,
            "created_at": "2025-01-25T10:30:00"
        }
    ]
}
```

#### Get Thread Details
```http
GET /api/v1/thread/{thread_id}
X-API-Key: your-api-key
```

Returns detailed information about a specific thread:
```json
{
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "account_username": "@myaccount",
    "tweet_count": 3,
    "tweets": [
        {
            "id": 1,
            "content": "🧵 1/3 Here's an important update...",
            "status": "posted",
            "twitter_id": "1234567890123456789",
            "reply_to_tweet_id": null,
            "position": 0,
            "created_at": "2025-01-25T10:30:00",
            "posted_at": "2025-01-25T10:31:00"
        },
        {
            "id": 2,
            "content": "2/3 We've been working hard...",
            "status": "posted",
            "twitter_id": "1234567890123456790",
            "reply_to_tweet_id": "1234567890123456789",
            "position": 1,
            "created_at": "2025-01-25T10:30:00",
            "posted_at": "2025-01-25T10:31:05"
        }
    ]
}
```

### Account Type Management

#### Set Account Type
```http
POST /api/v1/accounts/{account_id}/set-type
X-API-Key: your-api-key
Content-Type: application/json

{
    "account_type": "list_owner"
}
```

Sets an account as either "managed" (default) or "list_owner". Only list_owner accounts can create and manage Twitter lists.

#### Get Accounts by Type
```http
GET /api/v1/accounts?type=list_owner
X-API-Key: your-api-key
```

Filter accounts by type. Useful for finding all accounts that can manage lists.

### Twitter Lists Management

Twitter Lists allow you to organize accounts into groups. This feature requires at least one account with type "list_owner".

#### Create List
```http
POST /api/v1/lists
X-API-Key: your-api-key
Content-Type: application/json

{
    "name": "Tech Influencers",
    "description": "Top technology voices",
    "mode": "public",
    "owner_account_id": 1
}
```

Creates a new Twitter list. The `owner_account_id` must be an account with type "list_owner".
- `mode` can be "private" (default) or "public"

#### Get All Lists
```http
GET /api/v1/lists
X-API-Key: your-api-key
```

Optional query parameter:
- `owner_account_id` - Filter lists by owner

#### Get List Details
```http
GET /api/v1/lists/{list_id}
X-API-Key: your-api-key
```

Returns list details including all members.

#### Update List
```http
PUT /api/v1/lists/{list_id}
X-API-Key: your-api-key
Content-Type: application/json

{
    "name": "Updated Name",
    "description": "Updated description"
}
```

Update list name and/or description.

#### Delete List
```http
DELETE /api/v1/lists/{list_id}
X-API-Key: your-api-key
```

Deletes a list from both Twitter and the local database.

### List Membership Management

#### Add Accounts to List
```http
POST /api/v1/lists/{list_id}/members
X-API-Key: your-api-key
Content-Type: application/json

{
    "account_ids": [2, 3, 4, 5]
}
```

Add multiple accounts to a list. Returns details of successful and failed additions.

#### Get List Members
```http
GET /api/v1/lists/{list_id}/members
X-API-Key: your-api-key
```

Get all members of a specific list.

#### Remove Account from List
```http
DELETE /api/v1/lists/{list_id}/members/{account_id}
X-API-Key: your-api-key
```

Remove a specific account from a list.

### Cleanup Operations

#### Delete Account
```http
DELETE /api/v1/accounts/{account_id}
X-API-Key: your-api-key
```

Deletes an account and all its associated tweets.

#### Cleanup Inactive Accounts
```http
POST /api/v1/accounts/cleanup
X-API-Key: your-api-key
Content-Type: application/json

{
    "statuses": ["failed", "suspended", "inactive"]
}
```

Deletes all accounts with specified statuses (default: failed, suspended, inactive).

#### Delete Tweet
```http
DELETE /api/v1/tweets/{tweet_id}
X-API-Key: your-api-key
```

#### Cleanup Tweets
```http
POST /api/v1/tweets/cleanup
X-API-Key: your-api-key
Content-Type: application/json

{
    "statuses": ["failed", "posted"],
    "days_old": 30,
    "account_id": 2
}
```

Delete tweets by:
- `statuses`: Tweet status (failed, posted, pending)
- `days_old`: Tweets older than X days
- `account_id`: Only tweets from specific account

All parameters are optional but at least one of `statuses` or `days_old` is required.

#### Delete Thread
```http
DELETE /api/v1/thread/{thread_id}
X-API-Key: your-api-key
```

Deletes a specific thread and all its tweets. Returns:
```json
{
    "message": "Thread deleted successfully",
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "deleted_tweets": 3,
    "posted_tweets_deleted": 3
}
```

#### Cleanup Threads
```http
POST /api/v1/threads/cleanup
X-API-Key: your-api-key
Content-Type: application/json

{
    "statuses": ["posted", "failed"],
    "days_old": 7,
    "account_id": 1
}
```

Delete threads by:
- `statuses`: Delete threads where ALL tweets have the specified status
- `days_old`: Threads older than X days
- `account_id`: Only threads from specific account

All parameters are optional but at least one of `statuses` or `days_old` is required.

Returns:
```json
{
    "message": "Successfully deleted 2 threads",
    "deleted_threads": 2,
    "deleted_tweets": 6,
    "criteria": {
        "statuses": ["posted"],
        "days_old": 7,
        "account_id": 1
    }
}
```

#### List Tweets
```http
GET /api/v1/tweets?status=posted&account_id=1&page=1
X-API-Key: your-api-key
```

### Statistics
```http
GET /api/v1/stats
X-API-Key: your-api-key
```

### Token Health Monitoring

#### Check Token Health
```http
GET /api/v1/accounts/token-health
X-API-Key: your-api-key
```

Returns health status of all account tokens:
```json
{
    "summary": {
        "total_accounts": 5,
        "healthy": 3,
        "expiring_soon": 1,
        "expired": 1,
        "refresh_failures": 0
    },
    "details": {
        "healthy": [...],
        "expiring_soon": [...],
        "expired": [...]
    }
}
```

#### Manually Refresh Token
```http
POST /api/v1/accounts/{account_id}/refresh-token
X-API-Key: your-api-key
```

#### Batch Refresh Expiring Tokens
```http
POST /api/v1/accounts/refresh-tokens
X-API-Key: your-api-key
```

Refreshes all tokens expiring within the next hour.

#### Clear Refresh Failures
```http
POST /api/v1/accounts/{account_id}/clear-failures
X-API-Key: your-api-key
```

Reset failure count after resolving token issues.

## Example Usage

### 1. Authorize a Twitter Account

Get the OAuth URL:
```bash
curl -X GET http://localhost:5555/api/v1/auth/twitter \
  -H "X-API-Key: your-api-key"
```

Open the returned `auth_url` in your browser, authorize the app, and you'll be redirected to a success page.

### 2. Multi-Account Posting Example

```bash
# Create tweets for different accounts
for id in 1 2 3; do
  curl -X POST http://localhost:5555/api/v1/tweet \
    -H "X-API-Key: your-api-key" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"Update from account $id\", \"account_id\": $id}"
done

# Post all pending tweets at once (for small batches)
curl -X POST http://localhost:5555/api/v1/tweets/post-pending \
  -H "X-API-Key: your-api-key"

# For large batches, use async mode to prevent timeouts
curl -X POST http://localhost:5555/api/v1/tweets/post-pending-async \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 20}'

# Check job status
curl -X GET http://localhost:5555/api/v1/jobs/{job_id} \
  -H "X-API-Key: your-api-key"
```

### 3. Handling Large Batches of Tweets

When posting many pending tweets, use the appropriate method based on volume:

**For small batches (< 50 tweets):**
```bash
# Use batch mode with pagination
curl -X POST http://localhost:5555/api/v1/tweets/post-pending \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 20, "offset": 0}'
```

**For large batches (50+ tweets) or to avoid timeouts:**
```bash
# Start async job
response=$(curl -X POST http://localhost:5555/api/v1/tweets/post-pending-async \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 30}')

job_id=$(echo $response | jq -r .job_id)

# Poll for status
while true; do
  status=$(curl -s http://localhost:5555/api/v1/jobs/$job_id \
    -H "X-API-Key: your-api-key" | jq -r .status)
  
  if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
    break
  fi
  
  echo "Job status: $status"
  sleep 5
done
```

### 4. Lists Management Example

```bash
# Set an account as list owner
curl -X POST http://localhost:5555/api/v1/accounts/1/set-type \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"account_type": "list_owner"}'

# Create a list
curl -X POST http://localhost:5555/api/v1/lists \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Favorite Accounts",
    "description": "Accounts I follow closely",
    "mode": "private",
    "owner_account_id": 1
  }'

# Add accounts to the list
curl -X POST http://localhost:5555/api/v1/lists/1/members \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"account_ids": [2, 3, 4]}'
```

## Twitter Developer Setup

1. Create a Twitter Developer Account at https://developer.twitter.com
2. Create a new App in the Developer Portal
3. Configure OAuth 2.0 settings:
   - Enable OAuth 2.0
   - Set callback URL: `http://localhost:5555/auth/callback`
   - Required scopes: `tweet.read`, `tweet.write`, `users.read`, `list.read`, `list.write`, `offline.access`
4. Copy Client ID and Client Secret to your `.env` file
5. Ensure the callback URL is set to: `http://localhost:5555/auth/callback`

## Security Considerations

- All credentials are encrypted before storage
- API authentication required for all endpoints
- Environment variables for sensitive configuration
- Input validation and sanitization
- Rate limiting protection
- Automatic token refresh prevents authentication failures
- Token health monitoring for proactive maintenance

## Token Monitoring

The application includes automatic token refresh to prevent authentication failures. Additionally, you can set up proactive monitoring:

### Automatic Monitoring Script

Run `monitor_tokens.py` periodically to:
- Check token health for all accounts
- Automatically refresh expiring tokens
- Generate alerts for accounts needing attention

Setup with cron:
```bash
# Run every 30 minutes
*/30 * * * * cd /path/to/twitter-manager && python3 monitor_tokens.py >> logs/token_monitor.log 2>&1
```

The monitor will:
- Refresh tokens expiring within 1 hour
- Alert on accounts with failed refreshes
- Track accounts needing re-authorization

## Tweet Status Lifecycle

- **pending**: Tweet created but not yet posted to Twitter
- **posted**: Successfully posted to Twitter (includes twitter_id)
- **failed**: Posting attempt failed

## Error Handling

The API returns standard HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized (invalid API key or expired Twitter token)
- `404` - Not Found
- `500` - Internal Server Error

Error responses include a JSON body:
```json
{
    "error": "Descriptive error message"
}
```

## Working Endpoints Summary

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/health` | GET | No | Health check |
| `/api/v1/accounts` | GET | Yes | List all accounts (with type filter) |
| `/api/v1/accounts/{id}` | GET | Yes | Get account details |
| `/api/v1/accounts/{id}/set-type` | POST | Yes | Set account type |
| `/api/v1/tweet` | POST | Yes | Create new tweet |
| `/api/v1/tweets` | GET | Yes | List all tweets |
| `/api/v1/tweet/post/{id}` | POST | Yes | Post tweet to Twitter |
| `/api/v1/tweets/post-pending` | POST | Yes | Post pending tweets (batch mode) |
| `/api/v1/tweets/post-pending-async` | POST | Yes | Post pending tweets (async/background) |
| `/api/v1/jobs/{id}` | GET | Yes | Check background job status |
| `/api/v1/tweet/retry/{id}` | POST | Yes | Retry specific failed tweet |
| `/api/v1/tweets/retry-failed` | POST | Yes | Retry failed tweets (batch mode) |
| `/api/v1/tweets/reset-failed` | POST | Yes | Reset failed tweets to pending |
| `/api/v1/rate-limits` | GET | Yes | Check rate limit status for all accounts |
| `/api/v1/accounts/check-twitter-status` | GET | Yes | Check if accounts are suspended/locked |
| `/api/v1/thread` | POST | Yes | Create new thread |
| `/api/v1/threads` | GET | Yes | List all threads |
| `/api/v1/thread/{id}` | GET | Yes | Get thread details |
| `/api/v1/thread/post/{id}` | POST | Yes | Post thread to Twitter |
| `/api/v1/thread/{id}` | DELETE | Yes | Delete specific thread |
| `/api/v1/threads/cleanup` | POST | Yes | Delete threads by criteria |
| `/api/v1/auth/twitter` | GET | Yes | Start OAuth flow |
| `/auth/callback` | GET | No | OAuth callback (automatic) |
| `/api/v1/lists` | POST | Yes | Create new list |
| `/api/v1/lists` | GET | Yes | Get all lists |
| `/api/v1/lists/{id}` | GET | Yes | Get list details |
| `/api/v1/lists/{id}` | PUT | Yes | Update list |
| `/api/v1/lists/{id}` | DELETE | Yes | Delete list |
| `/api/v1/lists/{id}/members` | POST | Yes | Add accounts to list |
| `/api/v1/lists/{id}/members` | GET | Yes | Get list members |
| `/api/v1/lists/{id}/members/{account_id}` | DELETE | Yes | Remove from list |
| `/api/v1/stats` | GET | Yes | Get statistics |
| `/api/v1/test` | GET | Yes | Test API key |
| `/api/v1/mock-mode` | GET/POST | Yes | Control mock mode |
| `/api/v1/accounts/{id}` | DELETE | Yes | Delete account and tweets |
| `/api/v1/accounts/cleanup` | POST | Yes | Delete inactive accounts |
| `/api/v1/tweets/{id}` | DELETE | Yes | Delete specific tweet |
| `/api/v1/tweets/cleanup` | POST | Yes | Delete tweets by criteria |

## Quick Start Example

1. **Start the API**:
   ```bash
   python app.py
   ```

2. **Add a Twitter account**:
   ```bash
   # Get OAuth URL
   curl -X GET http://localhost:5555/api/v1/auth/twitter \
     -H "X-API-Key: your-api-key"
   
   # Open the auth_url in browser and authorize
   ```

3. **Create and post a tweet**:
   ```bash
   # Create tweet
   curl -X POST http://localhost:5555/api/v1/tweet \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello Twitter!", "account_id": 1}'
   
   # Post it
   curl -X POST http://localhost:5555/api/v1/tweet/post/1 \
     -H "X-API-Key: your-api-key"
   ```

## Common Questions

**Q: Can I post to multiple accounts?**  
A: Yes! Add multiple accounts via OAuth, then use different account_ids when creating tweets.

**Q: What's the difference between creating and posting a tweet?**  
A: Creating makes it "pending", posting sends it to Twitter. This allows batch operations.

**Q: How do I post to all accounts at once?**  
A: Create pending tweets for each account, then use `/api/v1/tweets/post-pending`.

**Q: Is OAuth 1.0a supported?**  
A: No, only OAuth 2.0 with PKCE is supported for security.

## Troubleshooting

- **401 Unauthorized**: Check your API key or re-authorize the Twitter account
- **"Something went wrong" on Twitter**: Verify callback URL is exactly `http://localhost:5555/auth/callback`
- **Database not found**: The app creates it automatically on first run
- **"unable to open database file" error**: 
  - The app now automatically creates the `instance/` directory
  - If you still get this error, manually create it: `mkdir instance`
  - On Mac/Linux, ensure write permissions: `chmod 755 instance`
- **Port already in use**: Another process is using port 5555

## License

## Project Structure

```
twitter-manager/
├── app.py                    # Main application file
├── requirements.txt          # Python dependencies
├── .env                      # Your configuration (create from .env.example)
├── .env.example              # Configuration template
├── .gitignore                # Git ignore rules
├── instance/
│   └── twitter_manager.db    # SQLite database (auto-created)
├── README.md                 # This file
├── SECURITY.md               # Security guidelines
├── ADD_TWITTER_ACCOUNT.md    # Detailed OAuth guide
├── postman.md                # API testing guide
└── Twitter_Manager_API.postman_collection.json  # Postman collection
```

## Additional Resources

- **Postman Collection**: Import `Twitter_Manager_API.postman_collection.json` for easy API testing
- **Security Guide**: See `SECURITY.md` for best practices
- **OAuth Details**: See `ADD_TWITTER_ACCOUNT.md` for step-by-step account addition