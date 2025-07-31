#!/usr/bin/env python3
"""
Batch Twitter Automation - Process multiple accounts sequentially
"""

import os
import json
import csv
import time
from datetime import datetime
from pathlib import Path
from twitter_selenium_automation import TwitterSeleniumAutomation
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BatchTwitterAutomation:
    def __init__(self, accounts_file=None, headless=False, browser="chrome"):
        """
        Initialize batch automation
        
        Args:
            accounts_file: Path to JSON or CSV file with account credentials
            headless: Run browser in headless mode
            browser: Browser type (chrome, firefox, edge)
        """
        self.accounts_file = accounts_file
        self.headless = headless
        self.browser = browser
        self.results = []
        self.accounts = []
        
    def load_accounts_from_json(self, file_path):
        """Load accounts from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get('accounts', [])
    
    def load_accounts_from_csv(self, file_path):
        """Load accounts from CSV file"""
        accounts = []
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                account = {
                    'username': row.get('username', '').strip(),
                    'password': row.get('password', '').strip(),
                    'email': row.get('email', '').strip() if row.get('email') else None,
                    'max_approvals': int(row.get('max_approvals', 50)),
                    'delay_seconds': int(row.get('delay_seconds', 3))
                }
                if account['username'] and account['password']:
                    accounts.append(account)
        return accounts
    
    def load_accounts(self):
        """Load accounts from file or environment"""
        if self.accounts_file:
            file_path = Path(self.accounts_file)
            if not file_path.exists():
                raise FileNotFoundError(f"Accounts file not found: {self.accounts_file}")
            
            if file_path.suffix.lower() == '.json':
                self.accounts = self.load_accounts_from_json(file_path)
            elif file_path.suffix.lower() == '.csv':
                self.accounts = self.load_accounts_from_csv(file_path)
            else:
                raise ValueError("Accounts file must be JSON or CSV format")
        else:
            # Load single account from environment variables
            username = os.getenv('TWITTER_USERNAME')
            password = os.getenv('TWITTER_PASSWORD')
            email = os.getenv('TWITTER_EMAIL')
            
            if username and password:
                self.accounts = [{
                    'username': username,
                    'password': password,
                    'email': email,
                    'max_approvals': int(os.getenv('MAX_APPROVALS', 50)),
                    'delay_seconds': int(os.getenv('DELAY_SECONDS', 3))
                }]
            else:
                raise ValueError("No accounts found. Provide accounts file or set environment variables.")
        
        print(f"Loaded {len(self.accounts)} account(s) for processing")
        return self.accounts
    
    def process_account(self, account, timeout_minutes=10):
        """Process a single account with timeout protection"""
        username = account['username']
        print(f"\n{'='*60}")
        print(f"Processing account: @{username}")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        result = {
            'username': username,
            'start_time': start_time.isoformat(),
            'success': False,
            'approved_count': 0,
            'error': None,
            'duration_seconds': 0,
            'timeout': False
        }
        
        try:
            # Create automation instance for this account
            automation = TwitterSeleniumAutomation(
                headless=self.headless,
                browser=self.browser
            )
            
            # Override credentials
            automation.username = account['username']
            automation.password = account['password']
            automation.email = account.get('email')
            
            # Custom inject function with account-specific settings
            original_inject = automation.inject_auto_approver_script
            
            def custom_inject():
                """Inject with account-specific configuration"""
                try:
                    print(f"Injecting auto-approver for @{username}...")
                    
                    # Read the auto-approver script with UTF-8 encoding
                    script_path = os.path.join(os.path.dirname(__file__), 'twitter_auto_approver.js')
                    with open(script_path, 'r', encoding='utf-8') as f:
                        auto_approver_script = f.read()
                    
                    # Inject the script
                    automation.driver.execute_script(auto_approver_script)
                    
                    # Start with account-specific configuration
                    max_approvals = account.get('max_approvals', 50)
                    delay_seconds = account.get('delay_seconds', 3)
                    
                    config_script = f"""
                    window.startAutoApproval({{
                        delay: {delay_seconds * 1000},
                        maxApprovals: {max_approvals},
                        autoScroll: true
                    }});
                    """
                    automation.driver.execute_script(config_script)
                    
                    print(f"✅ Auto-approver started for @{username} (max: {max_approvals}, delay: {delay_seconds}s)")
                    
                    # Monitor progress and capture results
                    last_count = 0
                    no_change_counter = 0
                    
                    while True:
                        time.sleep(5)
                        status = automation.driver.execute_script("return window.getApprovalStatus();")
                        
                        if status:
                            current_count = status.get('approvedCount', 0)
                            is_running = status.get('isRunning', False)
                            
                            if current_count > last_count:
                                print(f"@{username}: Approved {current_count} requests...")
                                last_count = current_count
                                no_change_counter = 0
                            else:
                                no_change_counter += 1
                            
                            if not is_running or no_change_counter > 6:
                                result['approved_count'] = current_count
                                break
                        else:
                            break
                    
                except Exception as e:
                    print(f"❌ Error in auto-approver for @{username}: {str(e)}")
                    raise
            
            automation.inject_auto_approver_script = custom_inject
            
            # Run automation for this account
            success = automation.run_full_automation()
            result['success'] = success
            
            if not success and result['approved_count'] == 0:
                result['error'] = "No follow requests found or unable to access them"
            
        except Exception as e:
            result['error'] = str(e)
            print(f"❌ Error processing @{username}: {str(e)}")
            
            # Ensure cleanup even on error
            try:
                if 'automation' in locals() and hasattr(automation, 'driver') and automation.driver:
                    automation.driver.quit()
                    print(f"   Browser closed for @{username}")
            except:
                pass
        
        # Calculate duration
        end_time = datetime.now()
        result['end_time'] = end_time.isoformat()
        result['duration_seconds'] = (end_time - start_time).total_seconds()
        
        return result
    
    def run_batch_automation(self):
        """Run automation for all accounts"""
        # Load accounts
        self.load_accounts()
        
        if not self.accounts:
            print("No accounts to process!")
            return
        
        print(f"\n🚀 Starting batch automation for {len(self.accounts)} account(s)")
        print(f"Browser: {self.browser} (headless: {self.headless})")
        
        # Process each account
        for i, account in enumerate(self.accounts, 1):
            print(f"\n📊 Progress: {i}/{len(self.accounts)}")
            
            result = self.process_account(account)
            self.results.append(result)
            
            # Wait between accounts to avoid rate limiting
            if i < len(self.accounts):
                wait_time = 30  # 30 seconds between accounts
                print(f"\n⏳ Waiting {wait_time} seconds before next account...")
                time.sleep(wait_time)
        
        # Generate summary report
        self.generate_report()
    
    def generate_report(self):
        """Generate summary report of all processed accounts"""
        print("\n" + "="*60)
        print("BATCH AUTOMATION SUMMARY")
        print("="*60)
        
        total_approved = 0
        successful_accounts = 0
        
        for result in self.results:
            username = result['username']
            approved = result['approved_count']
            success = result['success']
            duration = result['duration_seconds']
            
            total_approved += approved
            if success:
                successful_accounts += 1
            
            status = "✅" if success else "❌"
            print(f"\n{status} @{username}:")
            print(f"   - Approved: {approved} requests")
            print(f"   - Duration: {duration:.1f} seconds")
            if result['error']:
                print(f"   - Error: {result['error']}")
        
        print(f"\n{'='*60}")
        print(f"TOTAL RESULTS:")
        print(f"- Accounts processed: {len(self.results)}")
        print(f"- Successful: {successful_accounts}")
        print(f"- Total approvals: {total_approved}")
        print(f"- Completion time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save report to file
        report_file = f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_accounts': len(self.results),
                    'successful_accounts': successful_accounts,
                    'total_approvals': total_approved,
                    'completion_time': datetime.now().isoformat()
                },
                'results': self.results
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")


def main():
    """Main function for batch automation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch Twitter Follow Request Automation')
    parser.add_argument('--accounts', '-a', help='Path to accounts file (JSON or CSV)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--browser', default='chrome', choices=['chrome', 'firefox', 'edge'],
                       help='Browser to use (default: chrome)')
    
    args = parser.parse_args()
    
    # Create batch automation instance
    batch = BatchTwitterAutomation(
        accounts_file=args.accounts,
        headless=args.headless,
        browser=args.browser
    )
    
    try:
        # Run batch automation
        batch.run_batch_automation()
    except KeyboardInterrupt:
        print("\n⚠️ Batch automation interrupted by user")
    except Exception as e:
        print(f"\n❌ Batch automation error: {str(e)}")


if __name__ == "__main__":
    main()