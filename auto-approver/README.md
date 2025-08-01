# Twitter Follow Request Auto-Approver

Automated tool for managing Twitter/X follow requests using Selenium WebDriver with support for 2FA authentication codes.

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
4. **Auto-Approval**: Clicks Accept buttons for each request
5. **Progress Tracking**: Shows real-time approval count
6. **Batch Processing**: Handles multiple accounts sequentially

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

## Files

- `twitter_selenium_automation.py` - Core automation logic
- `batch_automation.py` - Multi-account processor
- `run_automation.py` - Simple single-account runner
- `selenium_setup.py` - Browser driver configuration
- `requirements_selenium.txt` - Python dependencies

Use responsibly and in compliance with Twitter's Terms of Service.