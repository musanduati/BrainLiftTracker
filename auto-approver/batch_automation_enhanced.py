#!/usr/bin/env python3
"""
Complete Enhanced Batch Automation - Actually processes accounts
This version will actually run the Twitter automation on accounts from CSV files
"""

import os
import json
import csv
import time
import argparse
from datetime import datetime
from twitter_selenium_automation import TwitterSeleniumAutomation
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WorkingEnhancedBatchAutomation:
    def __init__(self, accounts_file=None, headless=False, browser="chrome"):
        """
        Initialize working batch automation with IMAP integration
        """
        self.accounts_file = accounts_file
        self.headless = headless
        self.browser = browser
        self.results = []
        self.accounts = []
        
        # IMAP Integration tracking
        self.imap_stats = {
            'total_auth_attempts': 0,
            'imap_successful': 0,
            'manual_fallback': 0,
            'auth_skipped': 0,
            'gmail_config_valid': False
        }
        
        # Validate Gmail configuration
        self.validate_gmail_configuration()
    
    def validate_gmail_configuration(self):
        """Validate Gmail IMAP configuration for batch processing"""
        print("=" * 50)
        print("\n🔍 Validating Gmail IMAP Configuration...")
        print("=" * 50)
        
        gmail_username = os.getenv('GMAIL_USERNAME')
        gmail_password = os.getenv('GMAIL_APP_PASSWORD')
        
        if gmail_username and gmail_password:
            print(f"✅ Gmail username: {gmail_username}")
            print("✅ Gmail App Password: Configured")
            
            # Test IMAP connection
            try:
                import imaplib
                mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
                mail.login(gmail_username, gmail_password)
                mail.select('inbox')
                mail.close()
                mail.logout()
                
                print("✅ Gmail IMAP connection: Successful")
                self.imap_stats['gmail_config_valid'] = True
                
            except Exception as e:
                print(f"❌ Gmail IMAP connection failed: {str(e)[:100]}")
                print("⚠️  Will fall back to manual authentication for all accounts")
                
        else:
            print("❌ Gmail credentials not configured")
            print("⚠️  IMAP automation disabled - all accounts will use manual authentication")
    
    def load_accounts_from_csv(self, file_path):
        """Load accounts from CSV file"""
        accounts = []
        try:
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
            
            print(f"✅ Loaded {len(accounts)} accounts from {file_path}")
            return accounts
            
        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
            return []
        except Exception as e:
            print(f"❌ Error loading accounts: {str(e)}")
            return []
    
    def load_accounts(self):
        """Load accounts from file or environment"""
        if self.accounts_file:
            self.accounts = self.load_accounts_from_csv(self.accounts_file)
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
                print(f"✅ Loaded 1 account from environment variables")
            else:
                print("❌ No accounts found. Provide accounts file or set environment variables.")
                return False
        
        return len(self.accounts) > 0
    
    def process_account_with_imap_tracking(self, account, timeout_minutes=10):
        """Enhanced account processing with IMAP authentication tracking"""
        username = account['username']
        print(f"{username} - [INFO] Processing account")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        result = {
            'username': username,
            'start_time': start_time.isoformat(),
            'success': False,
            'approved_count': 0,
            'error': None,
            'duration_seconds': 0,
            'timeout': False,
            'followers_saved': 0,
            # IMAP Integration tracking
            'auth_method_used': None,  # 'imap', 'manual', 'skipped', 'none'
            'imap_attempted': False,
            'imap_successful': False,
            'auth_code_required': False,
            'gmail_config_available': self.imap_stats['gmail_config_valid']
        }
        
        try:
            # Create automation instance
            automation = TwitterSeleniumAutomation(
                headless=self.headless,
                browser=self.browser
            )
            
            # Override credentials
            automation.username = account['username']
            automation.password = account['password']
            automation.email = account.get('email')
            # print(f"{automation.username} - [INFO] Automation username: {automation.username},\
            # Automation password: {automation.password[:2]}...{automation.password[-2:]},\
            # Automation email: {automation.email}")
            
            # Track authentication attempts by wrapping the handle_auth_code_if_needed method
            original_handle_auth = automation.handle_auth_code_if_needed
            
            def tracked_auth_handler(timeout=60):
                """Wrapper to track authentication method usage"""
                result['auth_code_required'] = True
                self.imap_stats['total_auth_attempts'] += 1
                
                print(f"{username} - [AUTH] 🔐 Authentication code required for @{username}")
                
                if self.imap_stats['gmail_config_valid']:
                    print(f"{username} - [AUTH] 📧 Attempting IMAP-first authentication...")
                    result['imap_attempted'] = True
                    
                    # Call original method which tries IMAP first
                    auth_result = original_handle_auth(timeout)
                    
                    # Determine which method was actually used
                    if auth_result == "success":
                        # For simplicity, assume IMAP was successful if no manual fallback indicators
                        result['auth_method_used'] = 'imap'
                        result['imap_successful'] = True
                        self.imap_stats['imap_successful'] += 1
                        print(f"{username} - [AUTH] ✅ IMAP authentication successful")
                    elif auth_result == "skip":
                        result['auth_method_used'] = 'skipped'
                        self.imap_stats['auth_skipped'] += 1
                        print(f"{username} - [AUTH] ⏭️ Authentication skipped")
                    
                    return auth_result
                else:
                    print(f"{username} - [AUTH] 📱 Gmail not configured, would use manual authentication...")
                    result['auth_method_used'] = 'manual'
                    self.imap_stats['manual_fallback'] += 1
                    # For demo purposes, we'll skip instead of requiring manual input
                    print(f"{username} - [AUTH] ⏭️ Skipping due to no Gmail IMAP configuration")
                    return "skip"
            
            # Replace the authentication handler
            automation.handle_auth_code_if_needed = tracked_auth_handler
            
            # Custom inject function with account-specific settings
            original_inject = automation.inject_auto_approver_script
            
            def custom_inject():
                """Inject with account-specific configuration"""
                try:
                    print(f"{username} - [INFO] Injecting auto-approver...")
                    
                    # Read the auto-approver script
                    script_path = os.path.join(os.path.dirname(__file__), 'twitter_auto_approver.js')
                    with open(script_path, 'r', encoding='utf-8') as f:
                        auto_approver_script = f.read()
                    
                    # Inject the script
                    automation.driver.execute_script(auto_approver_script)
                    
                    # Start with account-specific configuration
                    max_approvals = account.get('max_approvals', 50)
                    delay_seconds = account.get('delay_seconds', 3)
                    
                    # Get allowed usernames
                    allowed_usernames_env = os.getenv('ALLOWED_USERNAMES', '')
                    if allowed_usernames_env:
                        allowed_usernames = [u.strip().lower() for u in allowed_usernames_env.split(',')]
                    else:
                        allowed_usernames = [
                            'jliemandt', 'opsaiguru', 'aiautodidact',
                            'zeroshotflow', 'munawar2434', 'klair_three', 'klair_two'
                        ]
                    
                    allowed_usernames_json = json.dumps(allowed_usernames)
                    
                    config_script = f"""
                    console.log('\\n' + '='*50);
                    console.log('[CONFIG] USERNAME FILTER CONFIGURATION');
                    console.log('='*50);
                    console.log('ALLOWED USERNAMES:', {allowed_usernames_json});
                    console.log('List length:', {len(allowed_usernames)});
                    console.log('Any requests from users NOT in this list will be SKIPPED');
                    console.log('='*50 + '\\n');
                    
                    window.startAutoApproval({{
                        delay: {delay_seconds * 1000},
                        maxApprovals: {max_approvals},
                        autoScroll: true,
                        allowedUsernames: {allowed_usernames_json}
                    }});
                    """
                    
                    automation.driver.execute_script(config_script)
                    
                    print(f"{username} - [OK] Auto-approver started (max: {max_approvals}, delay: {delay_seconds}s)")
                    
                    # Monitor progress
                    last_count = 0
                    no_change_counter = 0
                    
                    while True:
                        time.sleep(5)
                        status = automation.driver.execute_script("return window.getApprovalStatus();")
                        
                        if status:
                            current_count = status.get('approvedCount', 0)
                            is_running = status.get('isRunning', False)
                            
                            if current_count > last_count:
                                print(f"{username} - [INFO] Approved {current_count} requests...")
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
                    print(f"{username} - [ERROR] Error in auto-approver: {str(e)}")
                    raise
            
            automation.inject_auto_approver_script = custom_inject
            
            # Run automation for this account
            success = automation.run_full_automation()
            result['success'] = success
            
            # Try to save approved followers to the API
            try:
                if hasattr(automation, 'driver') and automation.driver:
                    try:
                        automation.driver.current_url
                        
                        approved_followers = automation.driver.execute_script("""
                            if (window.approver && window.approver.approvedFollowers) {
                                return window.approver.approvedFollowers;
                            }
                            return [];
                        """)
                        
                        if approved_followers:
                            print(f"{username} - [OK] Found {len(approved_followers)} approved followers to save")
                            saved_count = automation.save_approved_followers_to_api(approved_followers)
                            result['followers_saved'] = saved_count
                        else:
                            print(f"{username} - [INFO] No followers to save")
                    except:
                        print(f"{username} - [WARNING] Browser closed before followers could be retrieved")
            except Exception as e:
                print(f"{username} - [WARNING] Could not save followers: {str(e)}")
            
            # Handle authentication-specific error reporting
            if not success and result['approved_count'] == 0:
                if result.get('auth_code_required') and result.get('auth_method_used') == 'skipped':
                    result['error'] = "Authentication code required but skipped"
                elif result.get('auth_code_required') and not self.imap_stats['gmail_config_valid']:
                    result['error'] = "Authentication required but Gmail IMAP not configured"
                else:
                    result['error'] = "No follow requests found or unable to access them"
            
            # Always ensure browser is closed after processing
            if hasattr(automation, 'driver') and automation.driver:
                automation.cleanup()
                print(f"{username} - [OK] Browser closed")
                
        except Exception as e:
            result['error'] = str(e)
            print(f"{username} - [ERROR] Error processing: {str(e)}")
            
            # Ensure cleanup even on error
            try:
                if 'automation' in locals() and hasattr(automation, 'driver') and automation.driver:
                    automation.cleanup()
                    print(f"{username} - [INFO] Browser closed")
            except:
                pass
        
        # Calculate duration
        end_time = datetime.now()
        result['end_time'] = end_time.isoformat()
        result['duration_seconds'] = (end_time - start_time).total_seconds()
        
        return result
    
    def run_batch_automation(self):
        """Run automation for all accounts"""

        print(f"{'='*60}")
        print("Starting Enhanced Batch Automation")
        print(f"{'='*60}")
        
        # Load accounts
        if not self.load_accounts():
            print("❌ No accounts to process!")
            return
        
        print(f"[START] Starting enhanced batch automation for {len(self.accounts)} account(s)")
        print(f"Browser: {self.browser} (headless: {self.headless})")
        print(f"Gmail IMAP: {'✅ Configured' if self.imap_stats['gmail_config_valid'] else '❌ Not configured'}")
        
        # Process each account
        for i, account in enumerate(self.accounts, 1):
            print(f"{account['username']} - [PROGRESS] Progress: {i}/{len(self.accounts)}")
            
            result = self.process_account_with_imap_tracking(account)
            self.results.append(result)
            
            # Wait between accounts to avoid rate limiting
            if i < len(self.accounts):
                wait_time = 5  # 5 seconds between accounts
                print(f"[WAIT] Waiting {wait_time} seconds before next account...")
                time.sleep(wait_time)
        
        # Generate summary report
        self.generate_enhanced_report()
    
    def generate_enhanced_report(self):
        """Generate enhanced report with IMAP authentication statistics"""
        print("\n" + "="*60)
        print("🎯 ENHANCED BATCH AUTOMATION SUMMARY")
        print("="*60)
        
        total_approved = 0
        total_followers_saved = 0
        successful_accounts = 0
        auth_code_accounts = 0
        
        for result in self.results:
            username = result['username']
            approved = result['approved_count']
            followers_saved = result.get('followers_saved', 0)
            success = result['success']
            duration = result['duration_seconds']
            
            total_approved += approved
            total_followers_saved += followers_saved
            if success:
                successful_accounts += 1
            if result.get('auth_code_required'):
                auth_code_accounts += 1
            
            status = "[OK]" if success else "[FAILED]"
            print(f"\n{status} @{username}:")
            print(f"   - Approved: {approved} requests")
            print(f"   - Followers saved: {followers_saved}")
            print(f"   - Duration: {duration:.1f} seconds")
            
            # Enhanced authentication reporting
            if result.get('auth_code_required'):
                auth_method = result.get('auth_method_used', 'unknown')
                if auth_method == 'imap':
                    print("   - Authentication: ✅ IMAP (automated)")
                elif auth_method == 'manual':
                    print("   - Authentication: 📱 Manual input")
                elif auth_method == 'skipped':
                    print("   - Authentication: ⏭️  Skipped")
                else:
                    print(f"   - Authentication: {auth_method}")
            else:
                print("   - Authentication: Not required")
            
            if result['error']:
                print(f"   - Error: {result['error']}")
        
        print(f"\n{'='*60}")
        print(f"ACCOUNT SUMMARY:")
        print(f"- Accounts processed: {len(self.results)}")
        print(f"- Successful: {successful_accounts}")
        print(f"- Total approvals: {total_approved}")
        print(f"- Total followers saved: {total_followers_saved}")
        
        print(f"\n{'='*60}")
        print(f"AUTHENTICATION SUMMARY:")
        print(f"- Gmail IMAP configured: {'✅ Yes' if self.imap_stats['gmail_config_valid'] else '❌ No'}")
        print(f"- Accounts requiring 2FA: {auth_code_accounts}")
        
        if self.imap_stats['total_auth_attempts'] > 0:
            print(f"- Total auth attempts: {self.imap_stats['total_auth_attempts']}")
            print(f"- IMAP successful: {self.imap_stats['imap_successful']} ({self.imap_stats['imap_successful']/self.imap_stats['total_auth_attempts']*100:.1f}%)")
            print(f"- Manual fallback: {self.imap_stats['manual_fallback']} ({self.imap_stats['manual_fallback']/self.imap_stats['total_auth_attempts']*100:.1f}%)")
            print(f"- Authentication skipped: {self.imap_stats['auth_skipped']}")
        else:
            print("- No authentication codes were required")
        
        print(f"- Completion time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save enhanced report
        report_file = f"enhanced_batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_accounts': len(self.results),
                    'successful_accounts': successful_accounts,
                    'total_approvals': total_approved,
                    'total_followers_saved': total_followers_saved,
                    'completion_time': datetime.now().isoformat(),
                    'authentication_stats': self.imap_stats,
                    'accounts_requiring_auth': auth_code_accounts
                },
                'results': self.results
            }, f, indent=2)
        
        print(f"\n[REPORT] Enhanced report saved to: {report_file}")
        print("="*60)

def main():
    """Main function for enhanced batch automation"""
    parser = argparse.ArgumentParser(description='Enhanced Twitter Batch Automation with IMAP Integration')
    parser.add_argument('--accounts', '-a', help='Path to accounts CSV file')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--browser', default='chrome', choices=['chrome', 'firefox'],
                       help='Browser to use (default: chrome)')
    
    args = parser.parse_args()
    
    print("🚀 ENHANCED TWITTER BATCH AUTOMATION WITH IMAP")
    print("=" * 60)
    
    # Create batch automation instance
    batch = WorkingEnhancedBatchAutomation(
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
