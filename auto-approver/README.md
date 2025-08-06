# Twitter Follow Request Auto-Approver

Automated tool for managing Twitter/X follow requests using Selenium WebDriver with support for 2FA authentication codes and username filtering.

## Prerequisites

```bash
pip install -r requirements_selenium.txt
```

## Configuration

### Single Account (.env file)
```env
TWITTER_USERNAME=your_username
TWITTER_PASSWORD=your_password
TWITTER_EMAIL=your_email@example.com  # Optional
MAX_APPROVALS=50
DELAY_SECONDS=3

# Username Filtering (Optional)
# Only approve requests from these usernames (comma-separated)
# Leave empty to approve all requests
ALLOWED_USERNAMES=user1,user2,user3
```

### Multiple Accounts

**CSV format:**
```csv
username,password,email,max_approvals,delay_seconds
account1,password1,email1@example.com,50,3
account2,password2,email2@example.com,100,2
```

**JSON format:**
```json
{
  "accounts": [
    {
      "username": "account1",
      "password": "password1",
      "email": "email1@example.com",
      "max_approvals": 50,
      "delay_seconds": 3
    }
  ]
}
```

## Usage

### Single Account
```bash
python run_automation.py
```

### Multiple Accounts (Batch)
```bash
python batch_automation.py --accounts accounts.csv
python batch_automation.py --accounts accounts.json --headless
```

### BrainLift Accounts
```bash
python batch_automation.py --accounts brainlift_accounts.csv
```

## How It Works

1. **Automated Login**: Handles Twitter login with credentials
2. **2FA Support**: Interactive prompt for authentication codes when required
3. **Navigation**: Accesses follow requests via More → Follower requests
4. **Username Filtering**: Only approves requests from specified usernames (if configured)
5. **Auto-Approval**: Clicks Accept buttons for matching requests
6. **Progress Tracking**: Shows real-time approval and skip counts
7. **Batch Processing**: Handles multiple accounts sequentially

## Authentication Code Handling

When Twitter requires a 2FA authentication code:

1. **Automatic Detection**: The tool detects when Twitter asks for a verification code
2. **User Prompt**: Displays a clear message with 60-second countdown
3. **Code Entry**: Enter the code from SMS/email/authenticator app
4. **Skip Option**: Press ENTER without typing to skip the account
5. **Auto-Continue**: After 60 seconds, automatically proceeds to next account

### Example Prompt:
```
==================================================
🔐 AUTHENTICATION CODE REQUIRED
==================================================

Twitter is requesting an authentication code for account: @username
This code may have been sent to:
  - Your email address
  - Your phone via SMS
  - Your authenticator app

You have 60 seconds to enter the code.
Press ENTER without typing anything to skip this account.

Enter authentication code (or press ENTER to skip): _
```

## Error Handling

- Failed accounts don't stop the batch process
- Authentication code timeouts are handled gracefully
- Each error is logged and reported
- Browser properly closes even on failures
- Detailed JSON report generated after batch runs

### Batch Report Example:
```json
{
  "summary": {
    "total_accounts": 3,
    "successful_accounts": 2,
    "total_approvals": 75
  },
  "results": [
    {
      "username": "account1",
      "success": true,
      "approved_count": 45
    },
    {
      "username": "account2",
      "success": false,
      "error": "Authentication code required but not provided - account skipped",
      "auth_code_required": true
    }
  ]
}
```

## Username Filtering

The auto-approver now supports filtering follow requests by username. This allows you to:

- **Approve only specific users**: Set `ALLOWED_USERNAMES` to a comma-separated list
- **Approve all requests**: Leave `ALLOWED_USERNAMES` empty or unset
- **Case-insensitive matching**: Usernames are matched regardless of case

### Example Configuration
```env
# Only approve these specific users
ALLOWED_USERNAMES=jliemandt,OpsAIGuru,AiAutodidact,ZeroShotFlow,munawar2434,klair_three,klair_two
```

### Console Output with Filtering
```
==================================================
🐦 Twitter Auto-Approver Configuration
==================================================
Account: @your_account
Username Filter: Enabled
Allowed Usernames: jliemandt, OpsAIGuru, AiAutodidact, ZeroShotFlow, munawar2434, klair_three, klair_two
==================================================

Monitoring approval progress...
Filtering for usernames: jliemandt, OpsAIGuru, AiAutodidact, ZeroShotFlow, munawar2434, klair_three, klair_two
✅ Approved follow request from @jliemandt (#1)
⏭️ Skipped follow request from @randomuser (not in allowed list)
✅ Approved follow request from @OpsAIGuru (#2)
Progress: 2/50 approved, 1 skipped (not in allowed list)
```

## Files

- `twitter_selenium_automation.py` - Core automation logic with username filtering
- `twitter_auto_approver.js` - JavaScript module for browser-side approval
- `batch_automation.py` - Multi-account processor
- `run_automation.py` - Simple single-account runner
- `selenium_setup.py` - Browser driver configuration
- `requirements_selenium.txt` - Python dependencies

Use responsibly and in compliance with Twitter's Terms of Service.