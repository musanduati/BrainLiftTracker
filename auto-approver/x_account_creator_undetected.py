#!/usr/bin/env python3
"""
X (Twitter) Account Creation Automation with Undetected ChromeDriver
This script uses undetected-chromedriver to bypass bot detection.
"""

import os
import sys
import csv
import time
import json
import random
import imaplib
import email
import re
from datetime import datetime
from pathlib import Path

# Fix Unicode output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class XAccountCreatorUndetected:
    def __init__(self, headless=False):
        """
        Initialize the X account creation automation with undetected-chromedriver
        
        Args:
            headless (bool): Run browser in headless mode
        """
        self.driver = None
        self.wait = None
        self.headless = headless
        
        # Email configuration for verification codes
        self.email_server = os.getenv('EMAIL_SERVER', 'imap.gmail.com')
        self.email_port = int(os.getenv('EMAIL_PORT', '993'))
        self.email_username = os.getenv('EMAIL_USERNAME')
        self.email_password = os.getenv('EMAIL_APP_PASSWORD')
        
        # Results tracking
        self.results = []
        
    def setup_driver(self):
        """Set up the Undetected ChromeDriver"""
        options = uc.ChromeOptions()
        
        # Add some options for stability
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,800')
        
        # Randomize window size slightly
        width = random.randint(1200, 1400)
        height = random.randint(700, 900)
        options.add_argument(f'--window-size={width},{height}')
        
        if self.headless:
            options.add_argument('--headless')
        
        # Create driver with undetected-chromedriver
        self.driver = uc.Chrome(options=options, version_main=None)
        
        # Set up wait
        self.wait = WebDriverWait(self.driver, 20)
        
        # Add some randomness to viewport
        self.driver.execute_script(f"window.moveTo({random.randint(0, 100)}, {random.randint(0, 100)})")
    
    def human_typing(self, element, text, speed_range=(0.05, 0.2)):
        """Type text with human-like speed and occasional pauses"""
        element.click()
        time.sleep(random.uniform(0.2, 0.5))
        
        for i, char in enumerate(text):
            element.send_keys(char)
            
            # Vary typing speed
            base_delay = random.uniform(*speed_range)
            
            # Sometimes pause longer (thinking)
            if random.random() < 0.1:
                time.sleep(base_delay * random.uniform(3, 6))
            # Sometimes type faster (familiar text)
            elif random.random() < 0.3:
                time.sleep(base_delay * 0.5)
            else:
                time.sleep(base_delay)
    
    def random_mouse_movement(self):
        """Perform random mouse movement to appear more human"""
        try:
            actions = ActionChains(self.driver)
            # Small random movement
            x_offset = random.randint(-50, 50)
            y_offset = random.randint(-50, 50)
            actions.move_by_offset(x_offset, y_offset).perform()
            time.sleep(random.uniform(0.1, 0.3))
            # Move back
            actions.move_by_offset(-x_offset, -y_offset).perform()
        except:
            pass
    
    def random_scroll(self):
        """Perform random scroll to appear more human"""
        try:
            scroll_amount = random.randint(100, 300)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
            time.sleep(random.uniform(0.5, 1))
            # Scroll back
            self.driver.execute_script(f"window.scrollBy(0, -{scroll_amount})")
        except:
            pass
    
    def load_accounts_from_csv(self, csv_file):
        """Load account data from CSV file"""
        accounts = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                account = {
                    'email': row['email'].strip(),
                    'username': row['username'].strip(),
                    'password': row['password'].strip(),
                    'display_name': row['display_name'].strip(),
                    'bio': row['bio'].strip(),
                    'birth_date': row['birth_date'].strip(),
                    'project': row['project'].strip()
                }
                accounts.append(account)
        return accounts
    
    def get_verification_code(self, target_email, wait_time=60):
        """Retrieve verification code from email"""
        try:
            mail = imaplib.IMAP4_SSL(self.email_server, self.email_port)
            mail.login(self.email_username, self.email_password)
            mail.select('inbox')
            
            start_time = time.time()
            verification_code = None
            
            while time.time() - start_time < wait_time:
                _, messages = mail.search(None, 'FROM "info@x.com"')
                email_ids = messages[0].split()
                
                for email_id in reversed(email_ids[-5:]):
                    _, msg = mail.fetch(email_id, '(RFC822)')
                    email_message = email.message_from_bytes(msg[0][1])
                    
                    to_email = email_message.get('To', '')
                    if target_email.lower() in to_email.lower():
                        subject = email_message.get('Subject', '')
                        
                        code_patterns = [
                            r'(\d{6}) is your X verification code',
                            r'Your X confirmation code is ([a-zA-Z0-9]{8})',
                        ]
                        
                        for pattern in code_patterns:
                            code_match = re.search(pattern, subject)
                            if code_match:
                                verification_code = code_match.group(1)
                                print(f"Found verification code: {verification_code}")
                                break
                        
                        if verification_code:
                            break
                
                if verification_code:
                    break
                    
                print(f"Waiting for verification email... ({int(time.time() - start_time)}s)")
                time.sleep(5)
            
            mail.logout()
            return verification_code
            
        except Exception as e:
            print(f"Error retrieving email: {str(e)}")
            return None
    
    def create_account(self, account_data):
        """Create a single X account"""
        result = {
            'email': account_data['email'],
            'username': account_data['username'],
            'display_name': account_data['display_name'],
            'start_time': datetime.now().isoformat(),
            'success': False,
            'error': None,
            'steps_completed': []
        }
        
        try:
            print(f"\n{'='*60}")
            print(f"Creating account: {account_data['display_name']} (@{account_data['username']})")
            print(f"Email: {account_data['email']}")
            print(f"{'='*60}")
            
            # Navigate to signup page
            print("Step 1: Navigating to X signup page...")
            self.driver.get("https://twitter.com/i/flow/signup")
            time.sleep(random.uniform(5, 8))
            
            # Random mouse movement
            self.random_mouse_movement()
            
            # Click "Create account" if present
            try:
                create_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Create account')]"))
                )
                time.sleep(random.uniform(2, 3))
                create_button.click()
                time.sleep(random.uniform(3, 5))
            except:
                print("Already on signup form")
            
            # Fill registration form
            print("Step 2: Filling registration form...")
            
            # Enter name
            name_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "name"))
            )
            time.sleep(random.uniform(1, 2))
            self.human_typing(name_input, account_data['display_name'])
            
            # Random scroll
            self.random_scroll()
            
            # Enter email
            try:
                email_input = self.driver.find_element(By.NAME, "email")
            except:
                # Click "Use email instead"
                use_email = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Use email instead')]")
                time.sleep(random.uniform(1, 2))
                use_email.click()
                time.sleep(random.uniform(2, 3))
                email_input = self.driver.find_element(By.NAME, "email")
            
            time.sleep(random.uniform(1, 2))
            self.human_typing(email_input, account_data['email'])
            
            # Set birth date
            birth_date = datetime.strptime(account_data['birth_date'], '%Y-%m-%d')
            
            # Month
            time.sleep(random.uniform(1, 2))
            month_dropdown = self.driver.find_element(By.ID, "SELECTOR_1")
            month_dropdown.click()
            time.sleep(random.uniform(0.5, 1))
            month_option = self.driver.find_element(By.XPATH, f"//option[@value='{birth_date.month}']")
            month_option.click()
            
            # Day
            time.sleep(random.uniform(0.5, 1))
            day_dropdown = self.driver.find_element(By.ID, "SELECTOR_2")
            day_dropdown.click()
            time.sleep(random.uniform(0.5, 1))
            day_option = self.driver.find_element(By.XPATH, f"//option[@value='{birth_date.day}']")
            day_option.click()
            
            # Year
            time.sleep(random.uniform(0.5, 1))
            year_dropdown = self.driver.find_element(By.ID, "SELECTOR_3")
            year_dropdown.click()
            time.sleep(random.uniform(0.5, 1))
            year_option = self.driver.find_element(By.XPATH, f"//option[@value='{birth_date.year}']")
            year_option.click()
            
            result['steps_completed'].append('filled_registration_form')
            
            # Click Next
            print("Step 3: Clicking Next...")
            time.sleep(random.uniform(2, 4))
            self.random_mouse_movement()
            
            next_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
            next_button.click()
            time.sleep(random.uniform(3, 5))
            
            # Check for error dialog
            try:
                ok_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'OK')]")
                if ok_button.is_displayed():
                    print("Found error dialog, clicking OK...")
                    time.sleep(random.uniform(1, 2))
                    ok_button.click()
                    time.sleep(random.uniform(2, 3))
            except:
                pass
            
            result['steps_completed'].append('submitted_registration')
            
            # Wait for verification code
            print("Step 4: Waiting for verification code...")
            time.sleep(random.uniform(10, 15))
            
            verification_code = self.get_verification_code(account_data['email'], wait_time=120)
            
            if verification_code:
                print(f"Step 5: Entering verification code...")
                time.sleep(random.uniform(5, 8))
                
                # Find and enter code
                code_input = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Verification code"]'))
                )
                
                self.human_typing(code_input, verification_code, speed_range=(0.1, 0.3))
                time.sleep(random.uniform(2, 3))
                
                # Submit
                try:
                    next_btn = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
                    next_btn.click()
                except:
                    code_input.send_keys(Keys.RETURN)
                
                time.sleep(random.uniform(3, 5))
                result['steps_completed'].append('email_verified')
            else:
                raise Exception("Failed to retrieve verification code")
            
            # Set password
            print("Step 6: Setting password...")
            time.sleep(random.uniform(2, 3))
            
            password_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            
            self.human_typing(password_input, account_data['password'])
            time.sleep(random.uniform(2, 3))
            
            # Click next
            try:
                next_btn = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
                next_btn.click()
            except:
                password_input.send_keys(Keys.RETURN)
            
            time.sleep(random.uniform(3, 5))
            result['steps_completed'].append('password_set')
            
            # Check current state
            print("Step 7: Checking account status...")
            current_url = self.driver.current_url
            print(f"Current URL: {current_url}")
            
            # Take screenshot
            self.driver.save_screenshot("final_state.png")
            
            # If we see sign-in page, account might be created
            if "sign_in" in current_url or "login" in current_url:
                print("Redirected to sign-in page - account may have been created")
                result['success'] = True
                result['steps_completed'].append('account_created')
            else:
                print("Unknown final state")
                result['error'] = "Could not verify account creation"
            
        except Exception as e:
            result['error'] = str(e)
            print(f"[ERROR] Failed: {str(e)}")
        
        result['end_time'] = datetime.now().isoformat()
        return result
    
    def create_multiple_accounts(self, csv_file, start_index=0, max_accounts=None):
        """Create multiple accounts from CSV file"""
        accounts = self.load_accounts_from_csv(csv_file)
        
        if start_index >= len(accounts):
            print("Start index exceeds number of accounts")
            return
        
        end_index = len(accounts)
        if max_accounts:
            end_index = min(start_index + max_accounts, len(accounts))
        
        print(f"\nStarting account creation...")
        print(f"Total accounts: {len(accounts)}")
        print(f"Processing: {start_index + 1} to {end_index}")
        
        # Setup driver
        self.setup_driver()
        
        try:
            for i in range(start_index, end_index):
                account = accounts[i]
                print(f"\n[Progress: {i - start_index + 1}/{end_index - start_index}]")
                
                result = self.create_account(account)
                self.results.append(result)
                
                # Longer wait between accounts
                if i < end_index - 1:
                    print("\nWaiting before next account...")
                    self.driver.quit()
                    
                    wait_time = random.randint(120, 180)  # 2-3 minutes
                    for j in range(wait_time, 0, -10):
                        print(f"Waiting {j} seconds...", end='\\r')
                        time.sleep(10)
                    
                    print("\nStarting next account...")
                    self.setup_driver()
                    
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except Exception as e:
            print(f"\nFatal error: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
            self.generate_report()
    
    def generate_report(self):
        """Generate report of results"""
        print("\n" + "="*60)
        print("ACCOUNT CREATION SUMMARY")
        print("="*60)
        
        successful = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - successful
        
        print(f"\nTotal: {len(self.results)}")
        print(f"Success: {successful}")
        print(f"Failed: {failed}")
        
        # Save report
        report_file = f"account_creation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_processed': len(self.results),
                    'successful': successful,
                    'failed': failed,
                    'completion_time': datetime.now().isoformat()
                },
                'results': self.results
            }, f, indent=2)
        
        print(f"\nReport saved to: {report_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='X Account Creation with Undetected ChromeDriver')
    parser.add_argument('--accounts', '-a', default='test_account.csv',
                       help='Path to CSV file with account data')
    parser.add_argument('--start', '-s', type=int, default=0,
                       help='Start index (0-based)')
    parser.add_argument('--max', '-m', type=int,
                       help='Maximum number of accounts to create')
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode')
    
    args = parser.parse_args()
    
    # Check environment variables
    required_vars = ['EMAIL_USERNAME', 'EMAIL_APP_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("[ERROR] Missing required environment variables:")
        print(f"   {', '.join(missing_vars)}")
        return
    
    # Create instance
    creator = XAccountCreatorUndetected(headless=args.headless)
    
    # Run
    creator.create_multiple_accounts(
        csv_file=args.accounts,
        start_index=args.start,
        max_accounts=args.max
    )

if __name__ == "__main__":
    main()