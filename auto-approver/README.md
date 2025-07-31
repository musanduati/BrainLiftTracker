# Twitter Follow Request Auto-Approver

Automated tool for managing Twitter/X follow requests using Selenium WebDriver.

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
2. **Navigation**: Accesses follow requests via More → Follower requests
3. **Auto-Approval**: Clicks Accept buttons for each request
4. **Progress Tracking**: Shows real-time approval count
5. **Batch Processing**: Handles multiple accounts sequentially

## Error Handling

- Failed accounts don't stop the batch process
- Each error is logged and reported
- Browser properly closes even on failures
- Detailed JSON report generated after batch runs

## Files

- `twitter_selenium_automation.py` - Core automation logic
- `batch_automation.py` - Multi-account processor
- `run_automation.py` - Simple single-account runner
- `selenium_setup.py` - Browser driver configuration
- `requirements_selenium.txt` - Python dependencies

Use responsibly and in compliance with Twitter's Terms of Service.