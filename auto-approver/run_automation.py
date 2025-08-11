#!/usr/bin/env python3
"""
Simplified runner script for Twitter follow request automation
"""

import os
import sys
import json
import time
from datetime import datetime
from selenium_setup import get_chrome_driver, get_firefox_driver, get_edge_driver
from twitter_selenium_automation import TwitterSeleniumAutomation
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main function with enhanced options"""
    print("=== Twitter Follow Request Automation ===")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 40)
    
    # Check for credentials
    if not os.getenv('TWITTER_USERNAME') or not os.getenv('TWITTER_PASSWORD'):
        print("[ERROR] Missing Twitter credentials!")
        print("\nPlease create a .env file with:")
        print("  TWITTER_USERNAME=your_username")
        print("  TWITTER_PASSWORD=your_password")
        print("  TWITTER_EMAIL=your_email (optional)")
        return
    
    # Get browser preference
    browser_type = os.getenv('BROWSER_TYPE', 'chrome').lower()
    headless = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'
    
    # Get auto-approver settings
    max_approvals = int(os.getenv('MAX_APPROVALS', '50'))
    delay_seconds = int(os.getenv('DELAY_SECONDS', '3'))
    auto_scroll = os.getenv('AUTO_SCROLL', 'true').lower() == 'true'
    
    print(f"Browser: {browser_type} (headless: {headless})")
    print(f"Max approvals: {max_approvals}")
    print(f"Delay between actions: {delay_seconds} seconds")
    print(f"Auto-scroll: {auto_scroll}")
    print("-" * 40)
    
    try:
        # Create and run automation
        automation = TwitterSeleniumAutomation(
            headless=headless,
            browser=browser_type
        )
        
        # Override the inject script method to use custom settings
        original_inject = automation.inject_auto_approver_script
        
        def custom_inject():
            """Inject with custom configuration"""
            try:
                print("Injecting auto-approver script with custom settings...")
                
                # Read the auto-approver script with UTF-8 encoding
                script_path = os.path.join(os.path.dirname(__file__), 'twitter_auto_approver.js')
                with open(script_path, 'r', encoding='utf-8') as f:
                    auto_approver_script = f.read()
                
                # Inject the script
                automation.driver.execute_script(auto_approver_script)
                
                # Get allowed usernames from environment or use defaults
                allowed_usernames_env = os.getenv('ALLOWED_USERNAMES', '')
                if allowed_usernames_env:
                    allowed_usernames = [u.strip().lower() for u in allowed_usernames_env.split(',')]
                else:
                    # Default allowed usernames (lowercase for matching)
                    allowed_usernames = [
                        'jliemandt', 'opsaiguru', 'aiautodidact',
                        'zeroshotflow', 'munawar2434', 'klair_three', 'klair_two'
                    ]
                
                allowed_usernames_json = json.dumps(allowed_usernames)
                
                # Start with custom configuration
                config_script = f"""
                // CRITICAL: Verify configuration before starting
                const allowedUsernames = {allowed_usernames_json};
                
                console.log('\\n' + '='*50);
                console.log('🔒 USERNAME FILTER CONFIGURATION');
                console.log('='*50);
                console.log('ALLOWED USERNAMES:', allowedUsernames);
                console.log('List length:', allowedUsernames.length);
                console.log('Any requests from users NOT in this list will be SKIPPED');
                console.log('='*50 + '\\n');
                
                window.startAutoApproval({{
                    delay: {delay_seconds * 1000},
                    maxApprovals: {max_approvals},
                    autoScroll: {str(auto_scroll).lower()},
                    allowedUsernames: allowedUsernames
                }});
                """
                automation.driver.execute_script(config_script)
                
                print("[OK] Auto-approver started with custom settings!")
                
                # Monitor and save followers
                try:
                    automation.monitor_approval_progress()
                except Exception as e:
                    print(f"[WARNING] Monitoring error (this is OK): {str(e)[:100]}")
                    
                # Wait for approvals to complete
                print("[INFO] Waiting for approvals to complete...")
                time.sleep(10)  # Give it time to finish
                
                # Try to get the final status and save followers
                print("[INFO] Attempting to retrieve approved followers...")
                try:
                    # Try different methods to get the status
                    status = automation.driver.execute_script("""
                        if (window.getApprovalStatus) {
                            return window.getApprovalStatus();
                        } else if (window.twitterAutoApprover) {
                            return window.twitterAutoApprover.getStatus();
                        } else {
                            return null;
                        }
                    """)
                    
                    if status:
                        print(f"[INFO] Status retrieved: {status.get('approvedCount', 0)} approved, {status.get('skippedCount', 0)} skipped")
                        
                        approved_followers = status.get('approvedFollowers', [])
                        if approved_followers:
                            print(f"[INFO] Found {len(approved_followers)} approved followers to save:")
                            for f in approved_followers:
                                print(f"       - @{f.get('username', 'unknown')}")
                            automation.save_approved_followers_to_api(approved_followers)
                        else:
                            print("[INFO] No approved followers found in status")
                    else:
                        print("[INFO] Could not retrieve status from JavaScript")
                except Exception as e:
                    print(f"[ERROR] Failed to retrieve/save followers: {str(e)[:200]}")
                
            except Exception as e:
                print(f"[ERROR] Error injecting script: {str(e)}")
                return False
        
        automation.inject_auto_approver_script = custom_inject
        
        # Run the automation
        success = automation.run_full_automation()
        
        if success:
            print("\n[OK] Automation completed successfully!")
        else:
            print("\n[ERROR] Automation encountered errors.")
        
    except KeyboardInterrupt:
        print("\n[WARNING] Automation interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {str(e)}")
    
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()