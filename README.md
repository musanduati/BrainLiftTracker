# Twitter Manager API

A Flask-based RESTful API for managing multiple Twitter accounts and posting content via Twitter API v2. This application supports OAuth 2.0 authentication with PKCE, encrypted token storage, and real-time posting to Twitter/X.

> **Important**: Run the application using `python app.py` on port 5555.

## Features

- **Multi-Account Management**: Add and manage multiple Twitter accounts
- **OAuth 2.0 Authentication**: Secure Twitter authentication flow with PKCE
- **Real-Time Tweet Posting**: Post tweets directly to Twitter/X
- **Batch Operations**: Post all pending tweets at once
- **Twitter Lists**: Create and manage Twitter lists with multiple main accounts
- **List Membership**: Add/remove accounts to/from lists with bulk operations
- **Account Types**: Designate accounts as list owners or managed accounts
- **Encryption**: Secure storage of credentials using Fernet encryption
- **Token Management**: Support for refresh tokens and token updates
- **API Authentication**: Secure API access with API keys
- **Statistics**: Track tweet counts and posting status

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

#### Post All Pending Tweets
```http
POST /api/v1/tweets/post-pending
X-API-Key: your-api-key
```

Posts all tweets with "pending" status. Returns:
```json
{
    "total": 3,
    "posted": 2,
    "failed": 1,
    "details": [...]
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

# Post all pending tweets at once
curl -X POST http://localhost:5555/api/v1/tweets/post-pending \
  -H "X-API-Key: your-api-key"
```

### 3. Lists Management Example

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
| `/api/v1/tweets/post-pending` | POST | Yes | Post all pending tweets |
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