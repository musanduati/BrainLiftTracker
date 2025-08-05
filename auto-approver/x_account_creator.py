#!/usr/bin/env python3
"""
X (Twitter) Account Creation Automation
This script automates the process of creating multiple X accounts from a CSV file.
Includes email verification, profile setup, and making accounts private.
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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class XAccountCreator:
    def __init__(self, headless=False, browser="chrome"):
        """
        Initialize the X account creation automation
        
        Args:
            headless (bool): Run browser in headless mode
            browser (str): Browser type (chrome, firefox, edge)
        """
        self.browser_type = browser
        self.driver = None
        self.wait = None
        self.headless = headless
        
        # Email configuration for verification codes
        self.email_server = os.getenv('EMAIL_SERVER', 'imap.gmail.com')
        self.email_port = int(os.getenv('EMAIL_PORT', '993'))
        self.email_username = os.getenv('EMAIL_USERNAME')  # brainlift.monitor@trilogy.com
        self.email_password = os.getenv('EMAIL_APP_PASSWORD')  # App-specific password
        
        # Results tracking
        self.results = []
        
    def setup_driver(self):
        """Set up the Selenium WebDriver with appropriate options"""
        if self.browser_type == "chrome":
            options = Options()
            
            # Add options to avoid detection
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # General options
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1280,800')
            
            # User agent to appear more like a real browser - randomize
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ]
            options.add_argument(f'user-agent={random.choice(user_agents)}')
            
            if self.headless:
                options.add_argument('--headless')
            
            self.driver = webdriver.Chrome(options=options)
            
        elif self.browser_type == "firefox":
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            options = FirefoxOptions()
            
            if self.headless:
                options.add_argument('--headless')
                
            self.driver = webdriver.Firefox(options=options)
            
        else:
            raise ValueError(f"Unsupported browser type: {self.browser_type}")
        
        # Set up wait
        self.wait = WebDriverWait(self.driver, 20)
        
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
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
        """
        Retrieve verification code from email
        
        Args:
            target_email: The email address that received the code
            wait_time: Maximum time to wait for the email
            
        Returns:
            Verification code or None if not found
        """
        try:
            # Connect to email server
            mail = imaplib.IMAP4_SSL(self.email_server, self.email_port)
            mail.login(self.email_username, self.email_password)
            mail.select('inbox')
            
            # Search for emails from X/Twitter
            start_time = time.time()
            verification_code = None
            
            while time.time() - start_time < wait_time:
                # Search for recent emails from X
                _, messages = mail.search(None, 'FROM "info@x.com"')
                email_ids = messages[0].split()
                
                # Check latest emails first
                for email_id in reversed(email_ids[-5:]):  # Check only last 5 emails
                    _, msg = mail.fetch(email_id, '(RFC822)')
                    
                    # Parse email
                    email_message = email.message_from_bytes(msg[0][1])
                    
                    # Check if email is for the target address
                    to_email = email_message.get('To', '')
                    if target_email.lower() in to_email.lower():
                        # Get subject line - X puts the code in the subject!
                        subject = email_message.get('Subject', '')
                        
                        # Extract verification code from subject line
                        # New accounts: "452176 is your X verification code"
                        # Existing accounts: "Your X confirmation code is igmvqgza"
                        code_patterns = [
                            r'(\d{6}) is your X verification code',  # 6 digits for new accounts
                            r'Your X confirmation code is ([a-zA-Z0-9]{8})',  # 8 chars for existing accounts
                            r'(\d{6,8}) is your',  # Fallback for digits
                            r'code is ([a-zA-Z0-9]{6,8})',  # Fallback
                        ]
                        
                        for pattern in code_patterns:
                            code_match = re.search(pattern, subject)
                            if code_match:
                                verification_code = code_match.group(1)
                                print(f"Found verification code in subject: {verification_code}")
                                break
                        
                        # If not found in subject, check body as fallback
                        if not verification_code:
                            body = self.get_email_body(email_message)
                            for pattern in code_patterns:
                                code_match = re.search(pattern, body)
                                if code_match:
                                    verification_code = code_match.group(1)
                                    print(f"Found verification code in body: {verification_code}")
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
    
    def get_email_body(self, email_message):
        """Extract email body from email message"""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif part.get_content_type() == "text/html":
                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            
        return body
    
    def handle_sign_in(self, account_data, result):
        """Handle sign-in after account creation
        Returns True if sign-in successful, False otherwise
        """
        print("Step 10: Attempting to sign in to verify account...")
        try:
            # Look for email/username input
            login_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            login_input.clear()
            # Use username instead of email for sign-in
            username = account_data['username'].replace('@', '')  # Remove @ if present
            login_input.send_keys(username)
            print(f"Entering username: {username}")
            
            # Click Next
            next_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
            next_button.click()
            time.sleep(2)
            
            # Check for error message (account doesn't exist)
            try:
                error_msg = self.driver.find_element(By.XPATH, "//*[contains(text(), 'find your account')]")
                if error_msg.is_displayed():
                    print("[ERROR] X says it cannot find the account")
                    return False
            except:
                pass
            
            # Enter password
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.clear()
            password_input.send_keys(account_data['password'])
            
            # Click Log in
            login_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Log in')]")
            login_button.click()
            time.sleep(5)
            
            # Check if we're logged in (look for home timeline)
            if "home" in self.driver.current_url:
                result['steps_completed'].append('signed_in')
                print("[OK] Successfully signed in - account exists!")
                return True
            else:
                print(f"[WARNING] Sign-in result unclear, current URL: {self.driver.current_url}")
                return False
            
        except Exception as e:
            print(f"Could not sign in: {str(e)}")
            return False
    
    def random_mouse_movement(self):
        """Perform random mouse movement to appear more human"""
        try:
            actions = ActionChains(self.driver)
            # Get window size
            window_size = self.driver.get_window_size()
            width = window_size['width']
            height = window_size['height']
            
            # Move to random position
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            
            # Move mouse smoothly
            actions.move_by_offset(x - width/2, y - height/2).perform()
            time.sleep(random.uniform(0.1, 0.3))
        except:
            pass  # Ignore errors in mouse movement
    
    def create_account(self, account_data):
        """
        Create a single X account
        
        Args:
            account_data: Dictionary with account information
            
        Returns:
            Result dictionary with success status and details
        """
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
            
            # Step 1: Navigate to signup page
            print("Step 1: Navigating to X signup page...")
            self.driver.get("https://twitter.com/i/flow/signup")
            time.sleep(random.uniform(5, 8))  # Human-like delay
            
            # Step 2: Click "Create account" if needed
            try:
                create_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Create account')]"))
                )
                # Random mouse movement before clicking
                self.random_mouse_movement()
                time.sleep(random.uniform(1, 2))  # Small delay before clicking
                create_button.click()
                time.sleep(random.uniform(3, 5))  # Delay after clicking
            except TimeoutException:
                print("No 'Create account' button found, assuming already on signup form")
                pass  # Already on signup form
            
            # Step 3: Fill in registration form
            print("Step 2: Filling registration form...")
            
            # Enter name
            try:
                name_input = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.NAME, "name"))
                )
                time.sleep(random.uniform(1, 2))
                name_input.click()
                name_input.clear()
                # Type name with human-like delays
                typing_speed = random.uniform(0.08, 0.12)  # Base typing speed
                for i, char in enumerate(account_data['display_name']):
                    name_input.send_keys(char)
                    # Vary typing speed - sometimes faster, sometimes slower
                    if i % 3 == 0:
                        time.sleep(typing_speed * random.uniform(0.5, 1.5))
                    else:
                        time.sleep(typing_speed)
                    # Occasionally pause as if thinking
                    if random.random() < 0.1:
                        time.sleep(random.uniform(0.3, 0.8))
            except TimeoutException:
                print("ERROR: Could not find name input field")
                self.driver.save_screenshot("signup_form_error.png")
                raise
            
            # Check if email input is available, if not click "Use email instead"
            try:
                email_input = self.driver.find_element(By.NAME, "email")
            except NoSuchElementException:
                # Click "Use email instead" if phone is default
                use_email_link = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Use email instead')]")
                time.sleep(random.uniform(1, 2))
                use_email_link.click()
                time.sleep(random.uniform(2, 3))
                email_input = self.wait.until(
                    EC.presence_of_element_located((By.NAME, "email"))
                )
            
            # Enter email
            time.sleep(random.uniform(1, 2))
            email_input.click()
            email_input.clear()
            # Type email with human-like delays
            for char in account_data['email']:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))  # Typing delay
            
            # Set birth date
            birth_date = datetime.strptime(account_data['birth_date'], '%Y-%m-%d')
            
            # Month dropdown
            time.sleep(random.uniform(1, 2))
            month_dropdown = self.driver.find_element(By.ID, "SELECTOR_1")
            month_dropdown.click()
            time.sleep(random.uniform(0.5, 1))
            month_option = self.driver.find_element(By.XPATH, f"//option[@value='{birth_date.month}']")
            month_option.click()
            
            # Day dropdown
            time.sleep(random.uniform(0.5, 1))
            day_dropdown = self.driver.find_element(By.ID, "SELECTOR_2")
            day_dropdown.click()
            time.sleep(random.uniform(0.5, 1))
            day_option = self.driver.find_element(By.XPATH, f"//option[@value='{birth_date.day}']")
            day_option.click()
            
            # Year dropdown
            time.sleep(random.uniform(0.5, 1))
            year_dropdown = self.driver.find_element(By.ID, "SELECTOR_3")
            year_dropdown.click()
            time.sleep(random.uniform(0.5, 1))
            year_option = self.driver.find_element(By.XPATH, f"//option[@value='{birth_date.year}']")
            year_option.click()
            
            result['steps_completed'].append('filled_registration_form')
            
            # Step 4: Click Next
            print("Clicking Next button...")
            time.sleep(random.uniform(2, 3))  # Pause before clicking Next
            next_button = None
            
            # Try multiple selectors for Next button
            next_selectors = [
                (By.XPATH, "//span[contains(text(), 'Next')]"),
                (By.XPATH, "//div[@role='button']//span[contains(text(), 'Next')]"),
                (By.CSS_SELECTOR, "[data-testid*='next']"),
                (By.XPATH, "//button[contains(., 'Next')]")
            ]
            
            for by, selector in next_selectors:
                try:
                    next_button = self.driver.find_element(by, selector)
                    if next_button.is_displayed() and next_button.is_enabled():
                        next_button.click()
                        print(f"Clicked Next button using selector: {selector}")
                        break
                except:
                    continue
                    
            if not next_button:
                raise Exception("Could not find Next button")
                
            time.sleep(random.uniform(3, 5))
            
            # Check for error dialog with OK button
            try:
                # Look for OK button in error dialog
                ok_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'OK')]")
                if ok_button.is_displayed():
                    print("Found error dialog, clicking OK to proceed...")
                    time.sleep(random.uniform(1, 2))
                    ok_button.click()
                    time.sleep(random.uniform(2, 3))
            except NoSuchElementException:
                pass  # No error dialog
            
            # Check for other error messages after clicking Next
            try:
                error_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Something in the')]")
                if error_element.is_displayed():
                    error_text = error_element.text
                    print(f"ERROR from X: {error_text}")
                    # Try to click OK if available
                    try:
                        ok_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'OK')]")
                        ok_btn.click()
                        time.sleep(random.uniform(2, 3))
                    except:
                        self.driver.save_screenshot("name_field_error.png")
                        raise Exception(f"X rejected the form: {error_text}")
            except NoSuchElementException:
                pass  # No error message, continue
            
            # Step 5: Handle customization options (if present)
            try:
                # Sometimes X asks about customization preferences
                skip_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Skip for now')]")
                skip_button.click()
                time.sleep(2)
            except:
                pass
            
            # Step 6: Check if we need to confirm signup or if we're already at verification
            print("Step 3: Checking current state...")
            
            # Check if we're already at the verification code screen
            at_verification = False
            try:
                # Look for "We sent you a code" text
                verification_text = self.driver.find_element(By.XPATH, "//div[contains(text(), 'We sent you a code')]")
                if verification_text.is_displayed():
                    print("Already at verification code screen")
                    at_verification = True
            except:
                pass
            
            if not at_verification:
                # Try to find and click signup button
                print("Looking for signup button...")
                try:
                    signup_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Sign up')]")),
                        timeout=5
                    )
                    signup_button.click()
                    print("Clicked Sign up button")
                    time.sleep(5)
                except:
                    print("No signup button found, may already be past this step")
            
            result['steps_completed'].append('submitted_registration')
            
            # Step 7: Handle verification code
            print("Step 4: Waiting for verification code modal...")
            time.sleep(5)  # Wait for modal to appear
            
            # Wait for the verification code modal to appear
            try:
                # Look for the text "We sent you a code"
                modal_text = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'We sent you a code')]"))
                )
                print("Verification code modal detected")
            except:
                print("Warning: Could not detect verification modal text")
            
            # Get verification code from email
            print("Waiting before checking email (human behavior)...")
            time.sleep(random.uniform(8, 15))  # Wait like a human checking email
            
            verification_code = self.get_verification_code(account_data['email'], wait_time=120)
            
            if verification_code:
                print(f"Step 5: Entering verification code: {verification_code}")
                # Add delay before entering code (like switching back from email)
                time.sleep(random.uniform(5, 10))
                
                # Find the verification code input field
                code_input = None
                
                # Try to find by placeholder text first
                try:
                    code_input = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Verification code"]'))
                    )
                    print("Found verification input by placeholder")
                except:
                    # Try alternative selectors
                    selectors = [
                        (By.XPATH, '//input[@placeholder="Verification code"]'),
                        (By.CSS_SELECTOR, 'input[aria-label*="Verification"]'),
                        (By.CSS_SELECTOR, 'input[type="text"]'),  # Last resort - any text input
                    ]
                    
                    for by, selector in selectors:
                        try:
                            inputs = self.driver.find_elements(by, selector)
                            for inp in inputs:
                                if inp.is_displayed():
                                    code_input = inp
                                    print(f"Found verification input using: {selector}")
                                    break
                            if code_input:
                                break
                        except:
                            continue
                
                if not code_input:
                    # Take screenshot for debugging
                    self.driver.save_screenshot("verification_input_not_found.png")
                    # Print page source to help debug
                    print("Current page title:", self.driver.title)
                    print("Current URL:", self.driver.current_url)
                    raise Exception("Could not find verification code input field")
                
                # Clear and enter the code
                code_input.click()  # Focus the input
                time.sleep(random.uniform(1, 2))
                code_input.clear()
                # Type verification code with human-like delays
                for char in verification_code:
                    code_input.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
                print(f"Entered verification code: {verification_code}")
                time.sleep(random.uniform(2, 3))
                
                # Submit code - try multiple methods
                print("Submitting verification code...")
                submitted = False
                
                # Method 1: Click Next button
                try:
                    next_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
                    next_button.click()
                    submitted = True
                except:
                    pass
                
                # Method 2: Press Enter on code input
                if not submitted:
                    try:
                        code_input.send_keys(Keys.RETURN)
                        submitted = True
                        print("Submitted code with Enter key")
                    except:
                        pass
                
                # Method 3: Find button by role
                if not submitted:
                    try:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, 'div[role="button"]')
                        for button in buttons:
                            if 'next' in button.text.lower():
                                button.click()
                                submitted = True
                                break
                    except:
                        pass
                time.sleep(3)
                
                result['steps_completed'].append('email_verified')
            else:
                raise Exception("Failed to retrieve verification code")
            
            # Step 8: Set password
            print("Step 6: Setting password...")
            time.sleep(random.uniform(2, 3))
            
            # Check for "Something went wrong" error before password
            try:
                error_text = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Something went wrong')]")
                if error_text.is_displayed():
                    print("[ERROR] X showing 'Something went wrong' error")
                    self.driver.save_screenshot("something_went_wrong_error.png")
                    
                    # Try to find and click Try again or OK button
                    try:
                        retry_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Try again')] | //button[contains(text(), 'OK')]")
                        retry_button.click()
                        time.sleep(random.uniform(2, 3))
                    except:
                        pass
                    
                    raise Exception("X blocked account creation - 'Something went wrong' error")
            except NoSuchElementException:
                pass
            
            password_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.click()
            time.sleep(random.uniform(0.5, 1))
            password_input.clear()
            # Type password with human-like delays
            for char in account_data['password']:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            time.sleep(random.uniform(1, 2))
            
            # Try multiple ways to find and click Next button
            print("Looking for Next button after password...")
            next_clicked = False
            
            # Method 1: Look for any button with "Next" text
            try:
                buttons = self.driver.find_elements(By.XPATH, "//div[@role='button']")
                for button in buttons:
                    if 'next' in button.text.lower():
                        button.click()
                        next_clicked = True
                        print("Clicked Next button (method 1)")
                        break
            except:
                pass
            
            # Method 2: Look for specific Next span
            if not next_clicked:
                try:
                    next_button = self.driver.find_element(By.XPATH, "//span[text()='Next']")
                    next_button.click()
                    next_clicked = True
                    print("Clicked Next button (method 2)")
                except:
                    pass
            
            # Method 3: Press Enter on password field
            if not next_clicked:
                try:
                    print("Pressing Enter on password field...")
                    password_input.send_keys(Keys.RETURN)
                    next_clicked = True
                except:
                    pass
            
            if not next_clicked:
                # Take screenshot for debugging
                self.driver.save_screenshot("password_next_button_not_found.png")
                raise Exception("Could not find Next button after password")
            
            time.sleep(3)
            
            result['steps_completed'].append('password_set')
            
            # Step 9: Handle profile picture popup
            print("Step 7: Checking for profile picture popup...")
            time.sleep(3)
            
            # Look for "Pick a profile picture" modal and skip it
            try:
                # Look for the skip button in profile picture modal
                skip_pic_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Skip for now')] | //span[contains(text(), 'Skip for now')]"))
                )
                print("Found profile picture modal, clicking 'Skip for now'...")
                skip_pic_button.click()
                time.sleep(3)
                result['steps_completed'].append('profile_pic_skipped')
            except:
                print("No profile picture modal found, continuing...")
            
            # Step 10: Handle username selection
            print("Step 8: Setting username...")
            username_set = False
            
            # Method 1: Check if there's a username input field on current page
            try:
                username_input = self.driver.find_element(By.NAME, "username")
                if username_input.is_displayed():
                    print("Found username input on current page")
                    # Clear the pre-filled username generated by X
                    username_input.click()
                    time.sleep(0.5)
                    # Select all and delete to clear pre-filled username
                    username_input.send_keys(Keys.CONTROL + "a")
                    username_input.send_keys(Keys.DELETE)
                    time.sleep(0.5)
                    # Now enter our custom username
                    username_input.send_keys(account_data['username'].replace('@', ''))  # Remove @ if present
                    
                    # Try to submit
                    try:
                        # Look for Next or Continue button
                        next_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Next')] | //span[contains(text(), 'Continue')]")
                        next_button.click()
                        username_set = True
                    except:
                        # Try pressing Enter
                        username_input.send_keys(Keys.RETURN)
                        username_set = True
                    
                    time.sleep(3)
            except:
                print("No username input on current page")
            
            # Method 2: Skip username for now if offered
            if not username_set:
                try:
                    skip_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Skip for now')] | //span[contains(text(), 'Skip')]")
                    skip_button.click()
                    print("Skipped username selection for now")
                    time.sleep(2)
                    username_set = True  # We'll set it later
                except:
                    pass
            
            # Method 3: If we're already logged in, we can set username later
            # For now, just continue
            if not username_set:
                print("Username will be set later in profile settings")
                time.sleep(2)
            
            result['steps_completed'].append('username_set')
            
            # Step 11: Dynamically detect where we are after account creation
            print("Step 9: Detecting current screen...")
            time.sleep(random.uniform(5, 7))  # Give more time for page to load
            
            current_url = self.driver.current_url
            page_title = self.driver.title
            print(f"Current URL: {current_url}")
            print(f"Page title: {page_title}")
            
            # Take screenshot for debugging
            self.driver.save_screenshot("after_username_screen.png")
            
            # Check for any error dialogs first
            try:
                ok_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'OK')]")
                if ok_button.is_displayed():
                    print("Found dialog, clicking OK...")
                    time.sleep(random.uniform(1, 2))
                    ok_button.click()
                    time.sleep(random.uniform(2, 3))
            except:
                pass
            
            # Try to detect what screen we're on by looking for specific elements
            screen_detected = False
            
            # Check 1: Sign-in page (might mean account created OR failed)
            if "sign_in" in current_url or "login" in current_url:
                print("[WARNING] Detected sign-in page - need to verify if account was created")
                # Don't assume success just because we're at sign-in
                # Try to sign in to verify
                screen_detected = True
                
                if self.handle_sign_in(account_data, result):
                    print("[OK] Successfully signed in - account was created")
                    result['success'] = True
                    result['steps_completed'].append('account_created')
                else:
                    print("[ERROR] Could not sign in - account may not have been created")
                    result['success'] = False
                    result['error'] = "At sign-in page but could not verify account creation"
            
            # Check 2: Look for "Sign in to X" text
            if not screen_detected:
                try:
                    sign_in_header = self.driver.find_element(By.XPATH, "//h1[contains(text(), 'Sign in to X')]")
                    if sign_in_header.is_displayed():
                        print("[WARNING] Found 'Sign in to X' header - need to verify account")
                        screen_detected = True
                        
                        if self.handle_sign_in(account_data, result):
                            print("[OK] Account verified through sign-in")
                            result['success'] = True
                            result['steps_completed'].append('account_created')
                        else:
                            print("[ERROR] Could not verify account exists")
                            result['success'] = False
                            result['error'] = "At sign-in page but account doesn't exist"
                except:
                    pass
            
            # Check 3: Home timeline (already logged in)
            if not screen_detected and ("home" in current_url or "twitter.com" in current_url):
                try:
                    # Look for tweet compose button
                    compose_button = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='SideNav_NewTweet_Button']")
                    if compose_button:
                        print("[OK] Already logged in to new account")
                        result['success'] = True
                        result['steps_completed'].append('account_created')
                        result['steps_completed'].append('signed_in')
                        screen_detected = True
                except:
                    pass
            
            # Check 4: Profile completion page
            if not screen_detected:
                try:
                    # Look for profile setup elements
                    if "i/flow/profile" in current_url:
                        print("[OK] On profile completion page")
                        result['success'] = True
                        result['steps_completed'].append('account_created')
                        screen_detected = True
                        # Skip profile completion for now
                        try:
                            skip_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Skip for now')]")
                            skip_button.click()
                            time.sleep(2)
                        except:
                            pass
                except:
                    pass
            
            # Check 5: Back at signup page (indicates failure)
            if not screen_detected and "i/flow/signup" in current_url:
                print("[ERROR] Back at signup page - account creation failed")
                result['success'] = False
                result['error'] = "Account creation failed - returned to signup page"
                screen_detected = True
            
            # Check 5: Any other screen - DO NOT assume success
            if not screen_detected:
                print(f"[WARNING] Unknown screen after account creation")
                print(f"URL: {current_url}")
                print("Account creation may have failed")
                # Don't mark as success unless we're sure
                result['success'] = False
                result['error'] = "Could not verify account creation - unknown final screen"
            
            if result['success']:
                print(f"[SUCCESS] Created account: @{account_data['username']}")
            else:
                print(f"[FAILED] Account creation could not be verified")
            
            # Step 12: Try to set bio (optional)
            print("Step 11: Attempting to set bio (optional)...")
            try:
                time.sleep(3)
                self.driver.get("https://twitter.com/home")
                time.sleep(3)
                
                # Navigate to profile settings
                self.driver.get("https://twitter.com/settings/profile")
                time.sleep(3)
                
                bio_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "description"))
                )
                bio_input.clear()
                bio_input.send_keys(account_data['bio'])
                
                save_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Save')]")
                save_button.click()
                time.sleep(2)
                
                result['steps_completed'].append('profile_updated')
                print("[OK] Profile bio updated")
            except Exception as e:
                print(f"Could not update bio (non-critical): {str(e)}")
            
            # Step 13: Try to make account private (optional)
            print("Step 12: Attempting to make account private (optional)...")
            try:
                self.make_account_private(account_data['password'])
                result['steps_completed'].append('account_made_private')
            except Exception as e:
                print(f"Could not make account private (non-critical): {str(e)}")
            
        except Exception as e:
            result['error'] = str(e)
            print(f"[ERROR] Failed to create account: {str(e)}")
        
        result['end_time'] = datetime.now().isoformat()
        return result
    
    def make_account_private(self, password):
        """
        Make the account private/protected
        Following the exact navigation path provided
        """
        try:
            print("Navigating to privacy settings...")
            
            # Click More
            more_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'More')]"))
            )
            more_button.click()
            time.sleep(1)
            
            # Click Settings and privacy
            settings_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Settings and privacy')]"))
            )
            settings_link.click()
            time.sleep(2)
            
            # Click Privacy and safety
            privacy_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Privacy and safety')]"))
            )
            privacy_link.click()
            time.sleep(2)
            
            # Click Account information
            account_info_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Account information')]"))
            )
            account_info_link.click()
            time.sleep(2)
            
            # Enter password when prompted
            try:
                password_input = self.wait.until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
                password_input.clear()
                password_input.send_keys(password)
                
                confirm_button = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Confirm')]")
                confirm_button.click()
                time.sleep(2)
            except:
                print("Password not required, continuing...")
            
            # Click Audience, media and tagging
            audience_link = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Audience, media and tagging')]"))
            )
            audience_link.click()
            time.sleep(2)
            
            # Check the "Protect your posts" checkbox
            protect_checkbox = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox' and @name='protected']"))
            )
            
            # Check if not already checked
            if not protect_checkbox.is_selected():
                protect_checkbox.click()
                print("[OK] Account set to private/protected")
            else:
                print("Account already private/protected")
                
            time.sleep(2)
            
        except Exception as e:
            print(f"Error making account private: {str(e)}")
            raise
    
    def create_multiple_accounts(self, csv_file, start_index=0, max_accounts=None):
        """
        Create multiple accounts from CSV file
        
        Args:
            csv_file: Path to CSV file with account data
            start_index: Index to start from (for resuming)
            max_accounts: Maximum number of accounts to create
        """
        # Load accounts
        accounts = self.load_accounts_from_csv(csv_file)
        
        if start_index >= len(accounts):
            print("Start index exceeds number of accounts")
            return
        
        # Determine how many accounts to process
        end_index = len(accounts)
        if max_accounts:
            end_index = min(start_index + max_accounts, len(accounts))
        
        print(f"\nStarting account creation...")
        print(f"Total accounts in file: {len(accounts)}")
        print(f"Processing accounts {start_index + 1} to {end_index}")
        
        # Setup driver
        self.setup_driver()
        
        try:
            # Process each account
            for i in range(start_index, end_index):
                account = accounts[i]
                print(f"\n[Progress: {i - start_index + 1}/{end_index - start_index}]")
                
                result = self.create_account(account)
                self.results.append(result)
                
                # Close browser and restart for next account
                if i < end_index - 1:
                    print("\nWaiting before next account...")
                    self.driver.quit()
                    
                    # Random wait between accounts (60-120 seconds)
                    wait_time = random.randint(60, 120)
                    for j in range(wait_time, 0, -10):
                        print(f"Waiting {j} seconds...", end='\r')
                        time.sleep(10)
                    
                    print("\nStarting next account...")
                    self.setup_driver()
                    
        except KeyboardInterrupt:
            print("\nAccount creation interrupted by user")
        except Exception as e:
            print(f"\nFatal error: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
            self.generate_report()
    
    def generate_report(self):
        """Generate and save report of account creation results"""
        print("\n" + "="*60)
        print("ACCOUNT CREATION SUMMARY")
        print("="*60)
        
        successful = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - successful
        
        print(f"\nTotal processed: {len(self.results)}")
        print(f"[Success]: {successful}")
        print(f"[Failed]: {failed}")
        
        # Detailed results
        print("\nDetailed Results:")
        for result in self.results:
            status = "[OK]" if result['success'] else "[FAIL]"
            print(f"\n{status} {result['display_name']} (@{result['username']})")
            print(f"   Email: {result['email']}")
            print(f"   Steps completed: {', '.join(result['steps_completed'])}")
            if result['error']:
                print(f"   Error: {result['error']}")
        
        # Save to JSON file
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
        
        print(f"\nDetailed report saved to: {report_file}")
        
        # Save successful accounts to separate file
        if successful > 0:
            success_file = f"successful_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(success_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['username', 'password', 'email', 'display_name'])
                for result in self.results:
                    if result['success']:
                        # Find original account data
                        writer.writerow([
                            result['username'],
                            'Kl41rM0n1t0r!',  # Password from our data
                            result['email'],
                            result['display_name']
                        ])
            print(f"Successful accounts saved to: {success_file}")


def main():
    """Main function for account creation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='X (Twitter) Account Creation Automation')
    parser.add_argument('--accounts', '-a', default='new_accounts_to_create.csv',
                       help='Path to CSV file with account data')
    parser.add_argument('--start', '-s', type=int, default=0,
                       help='Start index (0-based) for resuming')
    parser.add_argument('--max', '-m', type=int,
                       help='Maximum number of accounts to create')
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode')
    parser.add_argument('--browser', default='chrome',
                       choices=['chrome', 'firefox', 'edge'],
                       help='Browser to use (default: chrome)')
    
    args = parser.parse_args()
    
    # Check for required environment variables
    required_vars = ['EMAIL_USERNAME', 'EMAIL_APP_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("[ERROR] Missing required environment variables:")
        print(f"   {', '.join(missing_vars)}")
        print("\nPlease create a .env file with:")
        print("EMAIL_USERNAME=brainlift.monitor@trilogy.com")
        print("EMAIL_APP_PASSWORD=your_app_specific_password")
        print("\nFor Gmail, generate an app password at:")
        print("https://myaccount.google.com/apppasswords")
        return
    
    # Create account creator instance
    creator = XAccountCreator(headless=args.headless, browser=args.browser)
    
    # Run account creation
    creator.create_multiple_accounts(
        csv_file=args.accounts,
        start_index=args.start,
        max_accounts=args.max
    )


if __name__ == "__main__":
    main()