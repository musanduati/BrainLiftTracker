#!/usr/bin/env python3
"""
Twitter Selenium Automation for Follow Request Management
This script automates the process of logging into Twitter and managing follow requests.
For educational and legitimate account management purposes only.
"""

import os
import time
import json
import requests
import imaplib
import email
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
from s3_session_manager import S3SessionManager
from human_behavior import HumanBehavior

# Load environment variables
load_dotenv()

class TwitterSeleniumAutomation:
    def __init__(self, headless=False, browser="chrome"):
        """
        Initialize the Twitter automation with Selenium
        
        Args:
            headless (bool): Run browser in headless mode
            browser (str): Browser type (chrome, firefox, edge)
        """
        self.browser_type = browser
        self.driver = None
        self.wait = None
        self.headless = headless
        self.auth_code_skipped = False  # Track if auth code was skipped
        
        # Configuration
        self.username = os.getenv('TWITTER_USERNAME')
        self.password = os.getenv('TWITTER_PASSWORD')
        self.email = os.getenv('TWITTER_EMAIL')  # Sometimes required for verification
        
        # API Configuration for saving followers
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:5555')
        self.api_key = os.getenv('API_KEY')
        
        # Gmail Configuration for automated 2FA code retrieval
        self.gmail_username = os.getenv('GMAIL_USERNAME')
        self.gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
        
        # Get allowed usernames from environment or use defaults
        # IMPORTANT: Normalize to lowercase for case-insensitive matching
        allowed_usernames_env = os.getenv('ALLOWED_USERNAMES', '')
        if allowed_usernames_env:
            self.allowed_usernames = [u.strip().lower() for u in allowed_usernames_env.split(',')]
        else:
            # Default allowed usernames (lowercase for matching)
            self.allowed_usernames = [
                'jliemandt', 'opsaiguru', 'aiautodidact',
                'zeroshotflow', 'munawar2434', 'klair_three', 'klair_two'
            ]
        
        # if not self.username or not self.password:
        #     raise ValueError("Twitter credentials not found in environment variables")
        
        # Session management
        self.session_manager = S3SessionManager()
        
        # Add to __init__ method:
        self.human = None  # Will be initialized after driver setup
        
    def setup_driver(self):
        """Set up the Selenium WebDriver with automatic driver management"""
        if self.browser_type == "chrome":
            # Use the existing selenium_setup functions which handle Mac ARM64 better
            from selenium_setup import get_chrome_driver
            try:
                print(f"{self.username} - [INFO] Setting up ChromeDriver using selenium_setup...")
                self.driver = get_chrome_driver(headless=self.headless)
                print(f"{self.username} - [OK] ChromeDriver setup successful!")
            except Exception as e:
                print(f"❌ ChromeDriver setup failed: {e}")
                raise
            
        elif self.browser_type == "firefox":
            from selenium_setup import get_firefox_driver
            try:
                print("Setting up Firefox using selenium_setup...")
                self.driver = get_firefox_driver(headless=self.headless)
                print("✅ Firefox setup successful!")
            except Exception as e:
                print(f"❌ Firefox setup failed: {e}")
                raise
                
        else:
            raise ValueError(f"Unsupported browser type: {self.browser_type}")
        
        # Set up wait
        self.wait = WebDriverWait(self.driver, 20)
        
        # Execute script to remove webdriver property (safe version)
        try:
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✅ Anti-detection script applied successfully")
        except Exception as e:
            print(f"⚠️ Anti-detection script failed (continuing without it): {str(e)[:100]}")
            # Modern Chrome versions prevent this - continue without anti-detection
        
        # Initialize human behavior after driver is ready
        self.human = HumanBehavior(self.driver)
        
        # Call this after driver setup
        self.verify_stealth_working()

    def verify_stealth_working(self, max_retries=3):
        """Verify stealth measures are working, retry if needed"""
        for attempt in range(max_retries):
            try:
                # Test webdriver detection
                webdriver_detected = self.driver.execute_script("return navigator.webdriver")
                
                if webdriver_detected is None:
                    print(f"✅ Stealth verification passed (attempt {attempt + 1})")
                    return True
                else:
                    print(f"⚠️ Stealth failed (attempt {attempt + 1}), retrying...")
                    # Re-apply stealth measures
                    self.driver.execute_script("""
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        delete navigator.__proto__.webdriver;
                    """)
                    time.sleep(1)
                    
            except Exception as e:
                print(f"⚠️ Stealth verification error (attempt {attempt + 1}): {e}")
                
        print("❌ Stealth verification failed after all retries")
        return False

    def login_to_twitter_with_human_behavior(self):
        """Enhanced login with human-like behavior"""
        print(f"\n🤖 Performing human-like login for @{self.username}")
        
        try:
            self.driver.get("https://x.com/i/flow/login")
            self.human.human_delay(2, 4)  # Page load time
            
            # Username field
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
            )
            
            # Human-like typing
            self.human.realistic_click_delay()
            self.human.human_type(username_input, self.username)
            self.human.human_delay(0.5, 1.0)
            
            # Next button
            next_button = self.driver.find_element(By.XPATH, "//span[text()='Next']/..")
            self.human.realistic_click_delay()
            next_button.click()
            self.human.human_delay(2, 3)
            
            # Password field
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
            )
            
            self.human.realistic_click_delay()
            self.human.human_type(password_input, self.password)
            self.human.human_delay(0.5, 1.0)
            
            # Login button
            login_button = self.driver.find_element(By.XPATH, "//span[text()='Log in']/..")
            self.human.realistic_click_delay()
            login_button.click()
            
            # Wait and check for success
            self.human.human_delay(3, 5)
            
            # Check if login was successful
            if self.driver.current_url.find('home') != -1 or self.driver.current_url.find('twitter.com') != -1:
                print(f"   ✅ Human-like login successful for @{self.username}")
                return True
            else:
                # Handle 2FA if needed
                return self.handle_auth_code_if_needed()
                
        except Exception as e:
            print(f"   ❌ Human-like login failed: {str(e)}")
            return False

    def login_to_twitter(self):
        """Log into Twitter using credentials"""
        try:
            print(f"{self.username} - [INFO] Navigating to Twitter login page...")
            self.driver.get("https://twitter.com/login")
            time.sleep(3)  # Allow page to load
            
            # Enter username
            print(f"{self.username} - [INFO] Entering username...")
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
            )
            username_input.clear()
            username_input.send_keys(self.username)
            username_input.send_keys(Keys.RETURN)
            time.sleep(2)
            
            # Check for unusual activity verification (phone/email request)
            unusual_activity_handled = self.handle_unusual_activity_if_needed()
            if not unusual_activity_handled:
                print(f"{self.username} - [ERROR] Unusual activity verification required but failed")
                return False
            
            # Enter password
            print(f"{self.username} - [INFO] Entering password...")
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
            )
            password_input.clear()
            password_input.send_keys(self.password)
            password_input.send_keys(Keys.RETURN)
            
            # Wait for initial login attempt to complete
            print(f"{self.username} - [INFO] Waiting for login to complete...")
            time.sleep(5)
            
            # Check if email verification is required 
            email_verification_handled = self.handle_email_verification_if_needed()
            if not email_verification_handled:
                print(f"{self.username} - [ERROR] Email verification required but failed")
                return False
            
            # Check for authentication code request (2FA)
            auth_code_required = self.handle_auth_code_if_needed()
            if auth_code_required == "skip":
                print(f"{self.username} - [WARNING] Authentication code required but not provided, skipping this account")
                # 🚨 ADD DEBUG CAPTURE HERE - 2FA FAILURE
                print(f"{self.username} - [DEBUG] Capturing page state for 2FA failure...")
                self.capture_page_debug_info("2fa_skip_failure")
                self.auth_code_skipped = True
                return False
            
            # Verify login by checking for home timeline or profile elements
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
            )
            print(f"{self.username} - [OK] Successfully logged into Twitter!")
            return True
            
        except TimeoutException:
            print(f"{self.username} - [ERROR] Login timeout - capturing page state for debugging...")
            self.capture_page_debug_info("login_timeout")
            return False
        except Exception as e:
            print(f"{self.username} - [ERROR] Login error: {str(e)}")
            self.capture_page_debug_info("login_error")
            return False

    def capture_page_debug_info(self, error_type):
        """Capture comprehensive page information for debugging"""
        import json
        from datetime import datetime
        import os
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_info = {
            "timestamp": timestamp,
            "error_type": error_type,
            "username": self.username,
            "url": None,
            "title": None,
            "page_source_length": 0,
            "visible_elements": [],
            "error_messages": [],
            "form_elements": [],
            "buttons": [],
            "input_fields": [],
            "page_structure": {},
            "network_status": {},
            "alerts_present": False,
            "screenshots": [],
            "s3_files": []  # Track S3 uploaded files
        }
        
        # Check if we're running in AWS (Fargate) environment
        s3_bucket = os.environ.get('S3_BUCKET_NAME')
        is_aws_env = s3_bucket is not None
        
        if is_aws_env:
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] AWS Environment detected - S3 bucket: {s3_bucket}")
            # Initialize S3 client
            try:
                import boto3
                s3_client = boto3.client('s3')
            except Exception as e:
                print(f"❌ Failed to initialize S3 client: {e}")
                s3_client = None
                is_aws_env = False
        
        try:
            # 1. BASIC PAGE INFO
            debug_info["url"] = self.driver.current_url
            debug_info["title"] = self.driver.title
            debug_info["page_source_length"] = len(self.driver.page_source)
            
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Current URL: {debug_info['url']}")
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Page Title: {debug_info['title']}")
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Page Source Length: {debug_info['page_source_length']} chars")
            
            # File paths (local first, then S3 if available)
            screenshot_path = f"debug_screenshot_{self.username}_{timestamp}.png"
            debug_json_path = f"debug_info_{self.username}_{timestamp}.json" 
            page_source_path = f"page_source_{self.username}_{timestamp}.html"
            
            # 🆕 IMPROVED S3 FOLDER STRUCTURE
            # Create username-based folder structure
            date_folder = datetime.now().strftime('%Y/%m/%d')
            username_clean = self.username.replace('@', '').replace('.', '_')  # Clean username for folder name
            s3_base_path = f"debug/{username_clean}/{date_folder}"
            
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] S3 folder structure: {s3_base_path}/")
            
            # 2. SCREENSHOT CAPTURE
            try:
                self.driver.save_screenshot(screenshot_path)
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Screenshot saved locally: {screenshot_path}")
                
                # Upload to S3 if available
                if is_aws_env and s3_client:
                    s3_key = f"{s3_base_path}/{screenshot_path}"
                    try:
                        with open(screenshot_path, 'rb') as f:
                            s3_client.put_object(
                                Bucket=s3_bucket,
                                Key=s3_key,
                                Body=f,
                                ContentType='image/png',
                                Metadata={
                                    'username': self.username,
                                    'error_type': error_type,
                                    'timestamp': timestamp,
                                    'file_type': 'screenshot'
                                }
                            )
                        s3_url = f"s3://{s3_bucket}/{s3_key}"
                        debug_info["s3_files"].append({
                            "type": "screenshot",
                            "s3_url": s3_url,
                            "s3_key": s3_key,
                            "local_path": screenshot_path
                        })
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Screenshot uploaded to S3: {s3_url}")
                    except Exception as e:
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to upload screenshot to S3: {e}")
                
                debug_info["screenshots"].append(screenshot_path)
            except Exception as e:
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to save screenshot: {e}")
            
            # 3. VISIBLE TEXT AND ELEMENTS
            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                visible_text = body.text[:500]  # First 500 chars
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Visible page text (first 500 chars): {repr(visible_text)}")
                debug_info["visible_text_preview"] = visible_text
            except:
                pass
            
            # 4. ERROR MESSAGES DETECTION
            error_selectors = [
                '[data-testid="error"]',
                '.error-message',
                '[role="alert"]',
                '.alert-danger',
                '.error',
                '[data-testid="loginErrorMessage"]',
                'span[data-testid="caption"]',  # Twitter error captions
                '[data-testid="helpText"]'
            ]
            
            for selector in error_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.text.strip():
                            debug_info["error_messages"].append({
                                "selector": selector,
                                "text": elem.text.strip(),
                                "location": elem.location
                            })
                            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Error message found: {elem.text.strip()}")
                except:
                    pass
            
            # 5. FORM ELEMENTS STATE
            try:
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                for inp in inputs:
                    if inp.is_displayed():
                        debug_info["input_fields"].append({
                            "type": inp.get_attribute("type"),
                            "name": inp.get_attribute("name"),
                            "placeholder": inp.get_attribute("placeholder"),
                            "value": inp.get_attribute("value")[:20] if inp.get_attribute("value") else "",
                            "autocomplete": inp.get_attribute("autocomplete"),
                            "location": inp.location,
                            "size": inp.size
                        })
            except:
                pass
            
            # 6. BUTTONS STATE
            try:
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if btn.is_displayed():
                        debug_info["buttons"].append({
                            "text": btn.text.strip(),
                            "type": btn.get_attribute("type"),
                            "disabled": btn.get_attribute("disabled"),
                            "location": btn.location,
                            "data_testid": btn.get_attribute("data-testid")
                        })
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Button found: '{btn.text.strip()}' (disabled: {btn.get_attribute('disabled')})")
            except:
                pass
            
            # 7. SPECIFIC TWITTER ELEMENTS
            twitter_elements = [
                '[data-testid="primaryColumn"]',  # What we're waiting for
                '[data-testid="loginButton"]',
                '[data-testid="ocfEnterTextTextInput"]',  # Auth code input
                '[data-testid="ocfSelectTextButton"]',    # SMS verification
                '[data-testid="challenge_response"]',     # Email verification
                '[data-testid="LoginForm"]',
                '[data-testid="sheetDialog"]',            # Modal dialogs
                '[role="main"]',
                '[data-testid="DenyAll"]',                # Cookie consent
                '[data-testid="confirmationSheetConfirm"]' # Confirmation buttons
            ]
            
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Twitter-specific elements check:")
            for selector in twitter_elements:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    found_count = len([e for e in elements if e.is_displayed()])
                    debug_info["visible_elements"].append({
                        "selector": selector,
                        "count": found_count,
                        "visible_count": found_count
                    })
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING]   {selector}: {found_count} found")
                    
                    # Get text content of visible elements
                    for elem in elements:
                        if elem.is_displayed() and elem.text.strip():
                            print(f"{self.username} - [ERROR_TROUBLESHOOTING]     Text: '{elem.text.strip()[:100]}'")
                except:
                    pass
            
            # 8. PAGE LOAD STATE
            try:
                ready_state = self.driver.execute_script("return document.readyState")
                debug_info["page_ready_state"] = ready_state
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Page ready state: {ready_state}")
            except:
                pass
            
            # 9. JAVASCRIPT ERRORS
            try:
                logs = self.driver.get_log('browser')
                js_errors = [log for log in logs if log['level'] == 'SEVERE']
                debug_info["javascript_errors"] = js_errors
                if js_errors:
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] JavaScript errors found: {len(js_errors)}")
                    for error in js_errors[:3]:  # Show first 3
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING]   {error['message'][:100]}...")
            except:
                pass
            
            # 10. NETWORK/LOADING STATE
            try:
                # Check if any network requests are pending
                pending_requests = self.driver.execute_script("""
                    return {
                        'performance_navigation_type': performance.navigation.type,
                        'document_ready_state': document.readyState,
                        'active_element': document.activeElement.tagName
                    }
                """)
                debug_info["network_status"] = pending_requests
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Network status: {pending_requests}")
            except:
                pass
            
            # 11. MODAL/POPUP DETECTION
            try:
                modals = self.driver.find_elements(By.CSS_SELECTOR, '[role="dialog"], .modal, [data-testid="sheetDialog"]')
                visible_modals = [m for m in modals if m.is_displayed()]
                if visible_modals:
                    debug_info["modals_present"] = len(visible_modals)
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] Modals/Popups found: {len(visible_modals)}")
                    for modal in visible_modals:
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING]   Modal text: '{modal.text.strip()[:100]}'")
            except:
                pass
            
            # 12. ALERTS
            try:
                alert = self.driver.switch_to.alert
                debug_info["alerts_present"] = True
                debug_info["alert_text"] = alert.text
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Alert present: {alert.text}")
            except:
                debug_info["alerts_present"] = False
            
            # 13. SAVE DEBUG INFO TO JSON FILE
            try:
                with open(debug_json_path, 'w') as f:
                    json.dump(debug_info, f, indent=2, default=str)
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] Debug info saved locally: {debug_json_path}")
                
                # Upload to S3 if available
                if is_aws_env and s3_client:
                    s3_key = f"{s3_base_path}/{debug_json_path}"
                    try:
                        s3_client.put_object(
                            Bucket=s3_bucket,
                            Key=s3_key,
                            Body=json.dumps(debug_info, indent=2, default=str),
                            ContentType='application/json',
                            Metadata={
                                'username': self.username,
                                'error_type': error_type,
                                'timestamp': timestamp,
                                'file_type': 'debug_json'
                            }
                        )
                        s3_url = f"s3://{s3_bucket}/{s3_key}"
                        debug_info["s3_files"].append({
                            "type": "debug_json",
                            "s3_url": s3_url,
                            "s3_key": s3_key,
                            "local_path": debug_json_path
                        })
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Debug JSON uploaded to S3: {s3_url}")
                    except Exception as e:
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to upload debug JSON to S3: {e}")
                        
            except Exception as e:
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to save debug info: {e}")
            
            # 14. SAVE PAGE SOURCE
            try:
                with open(page_source_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Page source saved locally: {page_source_path}")
                
                # Upload to S3 if available
                if is_aws_env and s3_client:
                    s3_key = f"{s3_base_path}/{page_source_path}"
                    try:
                        s3_client.put_object(
                            Bucket=s3_bucket,
                            Key=s3_key,
                            Body=self.driver.page_source,
                            ContentType='text/html',
                            Metadata={
                                'username': self.username,
                                'error_type': error_type,
                                'timestamp': timestamp,
                                'file_type': 'page_source'
                            }
                        )
                        s3_url = f"s3://{s3_bucket}/{s3_key}"
                        debug_info["s3_files"].append({
                            "type": "page_source", 
                            "s3_url": s3_url,
                            "s3_key": s3_key,
                            "local_path": page_source_path
                        })
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Page source uploaded to S3: {s3_url}")
                    except Exception as e:
                        print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to upload page source to S3: {e}")
                        
            except Exception as e:
                print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to save page source: {e}")
            
            # 15. CREATE INDEX FILE FOR EASY BROWSING
            if is_aws_env and s3_client and debug_info["s3_files"]:
                try:
                    index_content = self._create_debug_index_html(debug_info)
                    index_s3_key = f"{s3_base_path}/index.html"
                    
                    s3_client.put_object(
                        Bucket=s3_bucket,
                        Key=index_s3_key,
                        Body=index_content,
                        ContentType='text/html',
                        Metadata={
                            'username': self.username,
                            'error_type': error_type,
                            'timestamp': timestamp,
                            'file_type': 'debug_index'
                        }
                    )
                    
                    index_url = f"s3://{s3_bucket}/{index_s3_key}"
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] Debug index created: {index_url}")
                    
                    # Also create/update a master index for the username
                    master_index_key = f"debug/{username_clean}/index.html"
                    master_content = self._create_master_index_html(username_clean, s3_bucket, s3_client)
                    
                    s3_client.put_object(
                        Bucket=s3_bucket,
                        Key=master_index_key,
                        Body=master_content,
                        ContentType='text/html',
                        Metadata={
                            'username': self.username,
                            'file_type': 'master_index'
                        }
                    )
                    
                    master_url = f"s3://{s3_bucket}/{master_index_key}"
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] Master index updated: {master_url}")
                    
                except Exception as e:
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] Failed to create index files: {e}")
            
            # 16. CLEANUP LOCAL FILES IN AWS ENVIRONMENT
            if is_aws_env:
                try:
                    for file_path in [screenshot_path, debug_json_path, page_source_path]:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Cleaned up local file: {file_path}")
                except Exception as e:
                    print(f"{self.username} - [ERROR_TROUBLESHOOTING] Warning: Failed to cleanup local files: {e}")
                    
        except Exception as e:
            print(f"{self.username} - [ERROR_TROUBLESHOOTING] Error during debug info capture: {e}")
        
        return debug_info

    def _create_debug_index_html(self, debug_info):
        """Create an HTML index file for easy browsing of debug files"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Debug Session - {debug_info['username']} - {debug_info['timestamp']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .file-section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .error {{ color: red; font-weight: bold; }}
        .timestamp {{ color: #666; }}
        .url {{ word-break: break-all; }}
        pre {{ background: #f5f5f5; padding: 10px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Debug Session: {debug_info['username']}</h1>
        <p class="timestamp">Timestamp: {debug_info['timestamp']}</p>
        <p class="error">Error Type: {debug_info['error_type']}</p>
        <p class="url">URL: {debug_info.get('url', 'N/A')}</p>
        <p>Page Title: {debug_info.get('title', 'N/A')}</p>
    </div>
    
    <div class="file-section">
        <h2>📸 Screenshots</h2>
"""
        
        for file_info in debug_info.get('s3_files', []):
            if file_info['type'] == 'screenshot':
                html += f'<p><a href="{file_info["s3_url"]}">{file_info["local_path"]}</a></p>\n'
        
        html += """
    </div>
    
    <div class="file-section">
        <h2>📄 Page Source</h2>
"""
        
        for file_info in debug_info.get('s3_files', []):
            if file_info['type'] == 'page_source':
                html += f'<p><a href="{file_info["s3_url"]}">{file_info["local_path"]}</a></p>\n'
        
        html += """
    </div>
    
    <div class="file-section">
        <h2>💾 Debug JSON Data</h2>
"""
        
        for file_info in debug_info.get('s3_files', []):
            if file_info['type'] == 'debug_json':
                html += f'<p><a href="{file_info["s3_url"]}">{file_info["local_path"]}</a></p>\n'
        
        if debug_info.get('error_messages'):
            html += f"""
    </div>
    
    <div class="file-section">
        <h2>⚠️ Error Messages Found</h2>
        <pre>{json.dumps(debug_info['error_messages'], indent=2)}</pre>
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html

    def _create_master_index_html(self, username, bucket, s3_client):
        """Create a master index for all debug sessions for this username"""
        try:
            # List all debug sessions for this username
            prefix = f"debug/{username}/"
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/')
            
            sessions = []
            if 'CommonPrefixes' in response:
                for prefix_info in response['CommonPrefixes']:
                    date_path = prefix_info['Prefix'].replace(f"debug/{username}/", "").rstrip('/')
                    if '/' in date_path:  # YYYY/MM/DD format
                        sessions.append(date_path)
            
            sessions.sort(reverse=True)  # Most recent first
            
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Debug Sessions - {username}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .session {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 3px; }}
        .session:hover {{ background: #f9f9f9; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Debug Sessions: {username}</h1>
        <p>Total sessions: {len(sessions)}</p>
    </div>
    
    <h2>📁 Sessions by Date</h2>
"""
            
            for session in sessions:
                session_url = f"s3://{bucket}/debug/{username}/{session}/index.html"
                html += f'<div class="session"><a href="{session_url}">{session}</a></div>\n'
            
            html += """
</body>
</html>
"""
            return html
            
        except Exception as e:
            return f"<html><body><h1>Error creating master index: {e}</h1></body></html>"
    
    def handle_auth_code_if_needed(self, timeout=60):
        """
        Handle authentication code if Twitter requests it - with automated Gmail IMAP retrieval
        Enhanced to avoid conflicts with email verification screens
        
        Args:
            timeout (int): Maximum time to wait for email and code entry
            
        Returns:
            str: "success" if code entered and accepted, "skip" if failed, "none" if no code needed
        """
        try:
            print(f"{self.username} - [AUTH] Checking for 2FA code requirement...")
            
            # FIRST: Make sure we're NOT on email verification screen
            page_text = ""
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
            except:
                pass
                
            # Email verification screen indicators (should EXCLUDE 2FA detection)
            email_verification_indicators = [
                "Help us keep your account safe",
                "Verify your identity by entering the email address",
                "Enter the email address associated",
                "br**************************@t*********"  # Email hint pattern
            ]
            
            # Check if we're on email verification screen
            for indicator in email_verification_indicators:
                if indicator in page_text:
                    print(f"{self.username} - [AUTH] ✅ Email verification screen detected - skipping 2FA check")
                    return "none"  # Not a 2FA screen
            
            # 2FA-specific detection (prioritize specific selectors)
            auth_code_selectors = [
                # 2FA-specific selectors (prioritize these)
                'input[inputmode="numeric"]',
                'input[autocomplete="one-time-code"]', 
                'input[type="text"][aria-label*="verification code"]',
                'input[type="text"][aria-label*="confirmation code"]',
                'input[placeholder*="confirmation code"]',
                'input[placeholder*="verification code"]',
                'input[placeholder*="Enter code"]',
                # Generic selectors (only if no specific ones found)
                'input[name="text"]',
                'input[type="text"][aria-label*="code"]',
                'input[type="text"][aria-label*="Code"]',
                'input[placeholder*="code"]',
                'input[placeholder*="Code"]',
                # Last resort (but check context carefully)
                'input[data-testid="ocfEnterTextTextInput"]'
            ]
            
            # Look for 2FA-specific page indicators
            tfa_page_indicators = [
                "confirmation code",
                "verification code", 
                "enter the code",
                "we sent you a code",
                "check your email for a code",
                "enter your verification code",
                "we texted you a code"
            ]
            
            # Check if this looks like a 2FA screen
            is_tfa_screen = False
            page_text_lower = page_text.lower()
            
            for indicator in tfa_page_indicators:
                if indicator in page_text_lower:
                    print(f"{self.username} - [AUTH] Found 2FA indicator: '{indicator}'")
                    is_tfa_screen = True
                    break
            
            # Try to find auth code input field
            auth_code_input = None
            selector_used = None
            
            for selector in auth_code_selectors:
                try:
                    auth_code_input = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    if auth_code_input.is_displayed():
                        # Additional validation for generic selectors
                        if selector == 'input[data-testid="ocfEnterTextTextInput"]':
                            # Double-check this isn't email verification
                            if not is_tfa_screen:
                                print(f"{self.username} - [AUTH] Found input with generic selector but no 2FA indicators - skipping")
                                auth_code_input = None
                                continue
                        
                        selector_used = selector
                        print(f"{self.username} - [AUTH] Found 2FA input field with selector: {selector}")
                        break
                        
                except:
                    continue
            
            # If no input found or not a 2FA screen, return
            if not auth_code_input or not is_tfa_screen:
                print(f"{self.username} - [AUTH] ✅ No 2FA code required")
                return "none"
            
            print("\n" + "="*50)
            print(f"{self.username} - 🔐 2FA AUTHENTICATION CODE REQUIRED")
            print(f"{self.username} - Twitter is requesting verification code for")
            print(f"{self.username} - Attempting automated retrieval from Gmail via IMAP...")
            print("="*50)
            
            # Try IMAP retrieval first
            verification_code = self.get_verification_code_from_gmail_imap(max_wait_time=30)
            
            if verification_code:
                print(f"{self.username} - [INFO] ✅ Found verification code via IMAP: {verification_code}")
                
                # Enter the code
                print(f"{self.username} - [INFO] Entering verification code automatically...")
                auth_code_input.clear()
                auth_code_input.send_keys(verification_code)
                auth_code_input.send_keys(Keys.RETURN)
                
                # Wait for verification
                time.sleep(3)
                
                # Check if code was accepted
                try:
                    # If still on auth code page, check for errors
                    WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector_used))
                    )
                    
                    # Look for error messages
                    error_selectors = [
                        '[role="alert"]',
                        '.error-message', 
                        '[data-testid="toast"]',
                        'span[color="red"]'
                    ]
                    
                    error_found = False
                    for error_sel in error_selectors:
                        try:
                            error_elem = self.driver.find_element(By.CSS_SELECTOR, error_sel)
                            if error_elem.is_displayed():
                                print(f"{self.username} - [ERROR] IMAP code rejected: {error_elem.text}")
                                error_found = True
                                break
                        except:
                            continue
                    
                    if error_found:
                        print(f"{self.username} - [WARNING] IMAP code was rejected, falling back to manual input...")
                        # return self.handle_auth_code_manual_fallback(auth_code_input, timeout)
                        return "skip"
                    else:
                        print(f"{self.username} - [WARNING] Still on 2FA page after code entry - may have been rejected")
                        # 🚨 ADD DEBUG CAPTURE HERE - AUTOMATED CODE REJECTED
                        print(f"{self.username} - [DEBUG] Capturing page state for rejected 2FA code...")
                        self.capture_page_debug_info("2fa_code_rejected")
                        # return self.handle_auth_code_manual_fallback(auth_code_input, timeout)
                        return "skip"
                        
                except TimeoutException:
                    # Successfully moved past auth code page
                    print(f"{self.username} - [INFO] ✅ IMAP verification code accepted!")
                    return "success"
                
            else:
                print(f"{self.username} - [WARNING] No verification code found in Gmail, falling back to manual input...")
                # return self.handle_auth_code_manual_fallback(auth_code_input, timeout)
                return "skip"
                
        except Exception as e:
            print(f"{self.username} - [ERROR] Error in 2FA code handling: {str(e)}")
            # 🚨 ADD DEBUG CAPTURE HERE - EXCEPTION IN 2FA
            print(f"{self.username} - [DEBUG] Capturing page state for 2FA exception...")
            if hasattr(self, 'capture_page_debug_info'):
                self.capture_page_debug_info("2fa_exception")
            return "skip"

    def handle_email_verification_if_needed(self):
        """
        Handle email verification if Twitter requests it after password entry
        Enhanced to distinguish from 2FA screens
        
        Returns:
            bool: True if no email verification needed or successfully handled, False if failed
        """
        try:
            print(f"{self.username} - [AUTH] Checking for email verification requirement...")
            
            # Get page text for analysis
            page_text = ""
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
            except:
                pass
            
            # EXCLUDE 2FA/confirmation code screens first
            tfa_exclusion_indicators = [
                "Check your email",
                "confirmation code",
                "verification code", 
                "we've sent a confirmation code",
                "Enter the code",
                "code to br***",  # Masked email pattern
                "code to",
                "sent you a code"
            ]
            
            # If any 2FA indicators found, this is NOT email verification
            for indicator in tfa_exclusion_indicators:
                if indicator in page_text:
                    print(f"{self.username} - [AUTH] Found 2FA indicator '{indicator}' - this is NOT email verification")
                    return True  # Skip email verification, let 2FA handler deal with it
            
            # ONLY proceed if we have SPECIFIC email verification indicators
            email_verification_indicators = [
                "Help us keep your account safe",
                "Verify your identity by entering the email address",
                "Enter the email address associated with your account", 
                "What's your email address?",
                "Enter your email"
            ]
            
            # Check if we're ACTUALLY on email verification screen
            is_email_verification_screen = False
            
            for indicator in email_verification_indicators:
                if indicator in page_text:
                    print(f"{self.username} - [AUTH] Found email verification indicator: '{indicator}'")
                    is_email_verification_screen = True
                    break
            
            # Additional validation: look for email address input field characteristics
            if is_email_verification_screen:
                # Look for input fields that actually want email addresses
                email_input_selectors = [
                    'input[placeholder*="Email address" i]',
                    'input[aria-label*="Email address" i]', 
                    'input[name*="email" i]',
                    'input[type="email"]'
                ]
                
                email_input_element = None
                
                print(f"{self.username} - [AUTH] 📧 Email verification screen detected!")
                
                # Try to find the email input field
                for selector in email_input_selectors:
                    try:
                        email_input_element = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if email_input_element.is_displayed():
                            print(f"{self.username} - [AUTH] Found email input field with selector: {selector}")
                            break
                    except:
                        continue
                
                # If no specific email input found, try generic selector with additional validation
                if not email_input_element:
                    try:
                        generic_input = self.driver.find_element(By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
                        if generic_input.is_displayed():
                            # Check if the input actually expects an email (not a code)
                            placeholder = generic_input.get_attribute('placeholder') or ''
                            aria_label = generic_input.get_attribute('aria-label') or ''
                            
                            if 'email' in (placeholder + aria_label).lower():
                                email_input_element = generic_input
                                print(f"{self.username} - [AUTH] Found email input using generic selector with email validation")
                    except:
                        pass
                
                if email_input_element and self.email:
                    print(f"{self.username} - [AUTH] Entering email: {self.email}")
                    
                    # Clear and enter email
                    email_input_element.clear()
                    time.sleep(0.5)
                    email_input_element.send_keys(self.email)
                    time.sleep(1)
                    
                    # Submit using Enter key
                    email_input_element.send_keys(Keys.RETURN)
                    time.sleep(3)
                    
                    print(f"{self.username} - [AUTH] ✅ Email verification submitted successfully")
                    return True
                        
                elif not self.email:
                    print(f"{self.username} - [AUTH] ❌ Email verification required but no email configured in CSV")
                    return False
                else:
                    print(f"{self.username} - [AUTH] ❌ Could not find email input field")
                    return False
            
            else:
                # No email verification screen detected
                print(f"{self.username} - [AUTH] ✅ No email verification required")
                return True
                
        except Exception as e:
            print(f"{self.username} - [AUTH] ❌ Error handling email verification: {str(e)}")
            return False

    def handle_unusual_activity_if_needed(self):
        """
        Handle unusual activity verification if Twitter requests phone/email after username entry
        
        Returns:
            bool: True if no unusual activity screen or successfully handled, False if failed
        """
        try:
            print(f"{self.username} - [AUTH] Checking for unusual activity verification...")
            
            # Get page text for analysis
            page_text = ""
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
            except:
                pass
            
            # Look for unusual activity screen indicators
            unusual_activity_indicators = [
                "Enter your phone number or email address",
                "There was unusual login activity",
                "To help keep your account safe",
                "enter your phone number",
                "or email address to verify"
            ]
            
            # Check if we're on unusual activity screen
            is_unusual_activity_screen = False
            
            for indicator in unusual_activity_indicators:
                if indicator in page_text:
                    print(f"{self.username} - [AUTH] Found unusual activity indicator: '{indicator}'")
                    is_unusual_activity_screen = True
                    break
            
            if is_unusual_activity_screen:
                print(f"{self.username} - [AUTH] 📱 Unusual activity verification screen detected!")
                
                # Look for the phone/email input field
                input_selectors = [
                    'input[placeholder*="Phone or email" i]',
                    'input[aria-label*="Phone or email" i]',
                    'input[name*="challenge_response"]',
                    'input[data-testid="ocfEnterTextTextInput"]'  # Generic selector
                ]
                
                input_element = None
                
                # Try to find the input field
                for selector in input_selectors:
                    try:
                        input_element = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if input_element.is_displayed():
                            print(f"{self.username} - [AUTH] Found phone/email input field with selector: {selector}")
                            break
                    except:
                        continue
                
                if input_element and self.email:
                    print(f"{self.username} - [AUTH] Entering email for unusual activity verification: {self.email}")
                    
                    # Clear and enter email (prefer email over phone if we have it)
                    input_element.clear()
                    time.sleep(0.5)
                    input_element.send_keys(self.email)
                    time.sleep(1)
                    
                    # Submit using Enter key
                    try:
                        input_element.send_keys(Keys.RETURN)
                        print(f"{self.username} - [AUTH] Submitted using Enter key")
                    except:
                        # Fallback: try to find and click Next button
                        try:
                            next_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//div[@role='button'][contains(text(), 'Next')] | //button[contains(text(), 'Next')]"))
                            )
                            next_button.click()
                            print(f"{self.username} - [AUTH] Clicked Next button")
                        except:
                            print(f"{self.username} - [AUTH] Could not submit unusual activity verification")
                            return False
                    
                    time.sleep(3)
                    print(f"{self.username} - [AUTH] ✅ Unusual activity verification submitted successfully")
                    return True
                        
                elif not self.email:
                    print(f"{self.username} - [AUTH] ❌ Unusual activity verification required but no email configured in CSV")
                    print(f"{self.username} - [AUTH] Please add email for this account or configure phone number handling")
                    return False
                else:
                    print(f"{self.username} - [AUTH] ❌ Could not find phone/email input field")
                    return False
            
            else:
                # No unusual activity screen detected
                print(f"{self.username} - [AUTH] ✅ No unusual activity verification required")
                return True
                
        except Exception as e:
            print(f"{self.username} - [AUTH] ❌ Error handling unusual activity verification: {str(e)}")
            return False

    def handle_auth_code_manual_fallback(self, auth_code_input, timeout=60):
        # NOTE: This is a fallback method for when the automated code is rejected
        # However, we are not using it currently, since this is being run in the headless mode
        """
        Handle authentication code with manual user input (fallback method)
        
        Args:
            auth_code_input: The auth code input element found on the page
            timeout (int): Maximum time to wait for user input in seconds
            
        Returns:
            str: "success" if code entered and accepted, "skip" if timeout
        """
        try:
            print("\n" + "="*50)
            print("📱 MANUAL CODE INPUT REQUIRED")
            print("="*50)
            print(f"Account: {self.username}")
            print("\nThe verification code may have been sent to:")
            print("  - Your email address")
            print("  - Your phone via SMS")
            print("  - Your authenticator app")
            print(f"\nYou have {timeout} seconds to enter the code.")
            print("Press ENTER without typing anything to skip this account.\n")
            
            # Show a countdown and wait for user input
            import threading
            import queue
            
            input_queue = queue.Queue()
            
            def get_input():
                user_input = input("Enter authentication code (or press ENTER to skip): ").strip()
                input_queue.put(user_input)
            
            # Start input thread
            input_thread = threading.Thread(target=get_input)
            input_thread.daemon = True
            input_thread.start()
            
            # Wait for input with timeout
            start_time = time.time()
            code_entered = False
            
            while time.time() - start_time < timeout:
                try:
                    # Check if user provided input
                    user_code = input_queue.get(timeout=1)
                    
                    if not user_code:
                        print("No code entered, skipping this account...")
                        return "skip"
                    
                    # Enter the code
                    print(f"Entering authentication code: {user_code}")
                    auth_code_input.clear()
                    auth_code_input.send_keys(user_code)
                    auth_code_input.send_keys(Keys.RETURN)
                    
                    # Wait for code verification
                    time.sleep(3)
                    
                    # Check if we're still on the auth code page
                    try:
                        # If the auth code input is still there and visible, the code might be wrong
                        WebDriverWait(self.driver, 2).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]'))
                        )
                        # Check for error messages
                        error_selectors = [
                            '[role="alert"]',
                            '.error-message',
                            '[data-testid="toast"]',
                            'span[color="red"]'
                        ]
                        for error_sel in error_selectors:
                            try:
                                error_elem = self.driver.find_element(By.CSS_SELECTOR, error_sel)
                                if error_elem.is_displayed():
                                    print(f"[ERROR] Error: {error_elem.text}")
                                    print("The code may be incorrect. You can try again.")
                                    # Allow retry
                                    continue
                            except:
                                pass
                        
                        print("[WARNING] Code may be incorrect. You can try again.")
                        continue
                        
                    except:
                        # Auth code input disappeared, likely successful
                        print("[OK] ✅ Manual authentication code accepted!")
                        return "success"
                    
                    code_entered = True
                    break
                    
                except queue.Empty:
                    # No input yet, show countdown
                    remaining = int(timeout - (time.time() - start_time))
                    if remaining % 10 == 0 and remaining > 0:
                        print(f"⏱️  {remaining} seconds remaining...")
                except Exception as e:
                    print(f"Error handling manual auth code: {e}")
                    break
            
            if not code_entered:
                print("\n⏱️  Timeout reached, skipping this account...")
                # 🚨 ADD DEBUG CAPTURE HERE - MANUAL INPUT TIMEOUT
                print("[DEBUG] Capturing page state for manual input timeout...")
                if hasattr(self, 'capture_page_debug_info'):
                    self.capture_page_debug_info("2fa_manual_timeout")
                return "skip"
            
            return "success"
            
        except Exception as e:
            print(f"Error in manual auth code fallback: {e}")
            return "skip"
    
    def navigate_to_follow_requests(self):
        """Navigate to the follow requests section"""
        try:
            # Method 1: Try direct navigation to follower_requests endpoint
            print(f"{self.username} - [INFO] Navigating directly to follower requests page...")
            self.driver.get("https://twitter.com/follower_requests")
            time.sleep(3)
            
            # CRITICAL FIX: Always refresh to force modal content to load
            print(f"{self.username} - [INFO] Forcing page refresh to load modal content...")
            self.driver.refresh()
            time.sleep(4)
            
            # Additional trigger: Click somewhere on the page to activate it
            try:
                self.driver.execute_script("document.body.click();")
            except:
                pass
            
            # Try scrolling to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, 100);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # Check if we're on the follower requests page
            if "follower_requests" in self.driver.current_url:
                print(f"{self.username} - [OK] Successfully navigated to follower requests page")
                return True
            
            # Method 2: Navigate via More menu
            print(f"{self.username} - [INFO] Trying to access via More menu...")
            
            # Find and click More button
            more_button_selectors = [
                'a[href="/more"]',
                'a[data-testid="AppTabBar_More_Menu"]',
                'button[aria-label="More"]',
                'nav a[href="#"]',  # Sometimes More is just a # link
                '//span[text()="More"]/ancestor::a',  # XPath
                '//span[text()="More"]/ancestor::button'
            ]
            
            more_clicked = False
            for selector in more_button_selectors:
                try:
                    if selector.startswith('//'):
                        # XPath selector
                        more_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        more_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    more_button.click()
                    more_clicked = True
                    print(f"{self.username} - [OK] Clicked More menu")
                    time.sleep(2)
                    break
                except NoSuchElementException:
                    continue
            
            if not more_clicked:
                print(f"{self.username} - [ERROR] Could not find More menu button")
                return False
            
            # Look for "Follower requests" in the More menu
            print(f"{self.username} - [INFO] Looking for Follower requests option...")
            
            follower_requests_selectors = [
                'a[href="/follower_requests"]',
                'a[href="/i/follower_requests"]',
                '//span[text()="Follower requests"]/ancestor::a',
                '//span[contains(text(), "Follower request")]/ancestor::a',
                'a[role="link"][tabindex="0"]'  # Generic link in menu
            ]
            
            # Wait for menu to load
            time.sleep(1)
            
            # Try to find all links in the menu
            menu_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[role="link"]')
            for link in menu_links:
                try:
                    link_text = link.text.lower()
                    if 'follower' in link_text and 'request' in link_text:
                        link.click()
                        print(f"{self.username} - [OK] Clicked Follower requests link")
                        time.sleep(3)
                        return True
                except:
                    continue
            
            # Try specific selectors
            for selector in follower_requests_selectors:
                try:
                    if selector.startswith('//'):
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    element.click()
                    print(f"{self.username} - [OK] Clicked Follower requests link")
                    time.sleep(3)
                    return True
                except NoSuchElementException:
                    continue
            
            print(f"{self.username} - [ERROR] Could not find Follower requests option in More menu")
            
            # Method 3: Try the old way via profile -> followers (fallback)
            print(f"{self.username} - [INFO] Trying alternative method via profile...")
            try:
                # Navigate to profile
                self.driver.get(f"https://twitter.com/{self.username}")
                time.sleep(3)
                
                # Look for followers link
                followers_link = self.driver.find_element(By.CSS_SELECTOR, 'a[href$="/followers"]')
                followers_link.click()
                time.sleep(2)
                
                # Look for pending/requests tab
                elements = self.driver.find_elements(By.TAG_NAME, 'span')
                for element in elements:
                    if 'pending' in element.text.lower() or 'request' in element.text.lower():
                        element.click()
                        print(f"{self.username} - [OK] Found and clicked follow requests via profile")
                        time.sleep(3)
                        return True
            except Exception as e:
                print(f"Alternative method also failed: {str(e)}")
            
            return False
            
        except TimeoutException:
            print(f"{self.username} - [ERROR] Navigation timeout - the page may not have loaded properly")
            return False
        except Exception as e:
            print(f"{self.username} - [ERROR] Error navigating to follow requests: {str(e)}")
            return False
    
    def inject_auto_approver_script(self):
        """Inject and execute the auto-approver JavaScript"""
        try:
            # Wait a bit for the popup to fully load
            time.sleep(2)
            
            # Check if we're on the follower requests page
            current_url = self.driver.current_url
            if "follower_requests" not in current_url:
                print(f"{self.username} - [ERROR] Not on follower requests page")
                return False
            
            print(f"{self.username} - [INFO] Checking for follow request popup...")
            
            # The follower requests are now in a modal/popup
            # Wait for the modal to be present
            try:
                # Look for the modal dialog
                modal = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                )
                print(f"{self.username} - [OK] Found follower requests modal")
            except TimeoutException:
                print(f"{self.username} - [WARNING] No modal found, will check after refresh...")
            
            # Enhanced loading strategy - refresh already done in navigate_to_follow_requests
            print(f"{self.username} - [INFO] Checking for modal content...")
            
            # Step 1: Wait a moment for modal to appear after navigation
            time.sleep(3)
            
            # Step 2: Check if modal is present
            modal_present = False
            try:
                modal = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"]'))
                )
                modal_present = True
                print(f"{self.username} - [OK] Modal found")
                
                # Wait specifically for modal content to load
                print(f"{self.username} - [INFO] Waiting for modal content to populate...")
                
                # Try clicking inside the modal to activate it
                try:
                    self.driver.execute_script("""
                        const modal = document.querySelector('[role="dialog"], [aria-modal="true"]');
                        if (modal) {
                            modal.click();
                            // Also try clicking the modal body
                            const modalBody = modal.querySelector('div');
                            if (modalBody) modalBody.click();
                        }
                    """)
                except:
                    pass
                
                # Wait for actual content
                time.sleep(3)
                
            except:
                print(f"{self.username} - [WARNING] Modal not found, trying direct navigation...")
                self.driver.get("https://twitter.com/follower_requests")
                time.sleep(3)
                self.driver.refresh()
                time.sleep(4)
                
                # Check for modal again
                try:
                    modal = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"]'))
                    )
                    modal_present = True
                    print(f"{self.username} - [OK] Modal appeared after navigation")
                except:
                    print(f"{self.username} - [ERROR] Still no modal, trying one more refresh...")
                    self.driver.refresh()
                    time.sleep(5)
            
            # Step 3: NOW inject the auto-approver script AFTER refresh
            print(f"{self.username} - [INFO] Step 2: Injecting auto-approver script...")
            script_path = os.path.join(os.path.dirname(__file__), 'twitter_auto_approver.js')
            with open(script_path, 'r', encoding='utf-8') as f:
                auto_approver_script = f.read()
            
            self.driver.execute_script(auto_approver_script)
            print(f"{self.username} - [OK] Script injected")
            
            # Step 4: Wait and check for content with retries
            print(f"{self.username} - [INFO] Step 3: Checking for modal content...")
            max_retries = 3
            retry_count = 0
            content_loaded = False
            
            while retry_count < max_retries and not content_loaded:
                if retry_count > 0:
                    print(f"{self.username} - [INFO] Retry {retry_count}/{max_retries}: Attempting to load modal content...")
                
                # Simulate real user interaction with ActionChains
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                
                # Move mouse to center of screen and click
                try:
                    modal_element = self.driver.find_element(By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"]')
                    actions.move_to_element(modal_element).click().perform()
                    time.sleep(1)
                except:
                    pass
                
                # Wait for initial load
                time.sleep(2)
                
                # Check for loading indicators and wait for them to disappear
                wait_for_loading_script = """
                const waitForLoading = () => {
                    const loadingIndicators = document.querySelectorAll(
                        '[aria-label*="Loading"], [class*="loading"], [class*="spinner"], [data-testid="progressBar"]'
                    );
                    return loadingIndicators.length === 0;
                };
                return waitForLoading();
                """
                
                # Wait up to 10 seconds for loading to complete
                for _ in range(10):
                    loading_done = self.driver.execute_script(wait_for_loading_script)
                    if loading_done:
                        break
                    time.sleep(1)
                
                # Try to trigger content loading by various methods
                print(f"{self.username} - [INFO] Attempting to trigger content load...")
                trigger_script = """
                // Find the modal
                const modal = document.querySelector('[role="dialog"], [aria-modal="true"], .modal');
                if (modal) {
                    // Method 1: Focus and click the modal
                    modal.focus();
                    modal.click();
                    
                    // Method 2: Try to find and scroll any scrollable containers
                    const scrollContainers = modal.querySelectorAll(
                        '[data-testid*="scroll"], [class*="scroll"], div[style*="overflow"], [role="region"]'
                    );
                    console.log(`Found ${scrollContainers.length} potential scroll containers`);
                    
                    scrollContainers.forEach(container => {
                        // Trigger scroll events
                        container.scrollTop = 1;
                        container.dispatchEvent(new Event('scroll', {bubbles: true}));
                        container.scrollTop = 0;
                    });
                    
                    // Method 3: Scroll the modal itself
                    modal.scrollTop = 1;
                    modal.dispatchEvent(new Event('scroll', {bubbles: true}));
                    modal.scrollTop = 0;
                    
                    // Method 4: Click the modal header to ensure focus
                    const modalHeader = modal.querySelector('h2, h3, [role="heading"], [aria-label*="Follower"]');
                    if (modalHeader) {
                        modalHeader.click();
                        console.log('Clicked modal header');
                    }
                    
                    // Method 5: Simulate viewport intersection (triggers lazy loading)
                    const entries = modal.querySelectorAll('*');
                    entries.forEach(entry => {
                        if (typeof entry.scrollIntoView === 'function') {
                            entry.scrollIntoView({block: 'nearest'});
                        }
                    });
                }
                
                // Check current state
                console.log('Current URL:', window.location.href);
                const hasDialog = !!document.querySelector('[role="dialog"]');
                console.log('Dialog present:', hasDialog);
                
                return hasDialog;
                """
                self.driver.execute_script(trigger_script)
                
                # Wait for content to render
                print(f"{self.username} - [INFO] Waiting for content to render...")
                time.sleep(3)
                
                # Check if content has loaded - improved detection
                check_content_script = """
                const modal = document.querySelector('[role="dialog"], [aria-modal="true"], .modal');
                if (modal) {
                    // Method 1: Look for user cells with various selectors
                    const userCells = modal.querySelectorAll(
                        '[data-testid*="UserCell"], ' +
                        '[data-testid*="user-cell"], ' +
                        'div[role="button"][data-testid*="follow"], ' +
                        'div[data-testid*="cell"], ' +
                        'article[role="article"], ' +
                        'div[data-testid="cellInnerDiv"], ' +
                        'button[data-testid*="follow"], ' +
                        'a[href*="/"][role="link"][tabindex="0"]'
                    );
                    
                    // Method 2: Check for any buttons with "Approve" or "Deny" text
                    const buttons = Array.from(modal.querySelectorAll('button')).filter(btn => {
                        const text = btn.textContent.toLowerCase();
                        return text.includes('approve') || text.includes('deny') || text.includes('follow');
                    });
                    
                    // Method 3: Check for empty state messages
                    const textElements = Array.from(modal.querySelectorAll('span, div')).filter(el => {
                        const text = el.textContent.toLowerCase();
                        return text.includes('no pending') || 
                               text.includes("don't have") || 
                               text.includes('no follow') ||
                               text.includes('requests will appear');
                    });
                    
                    const hasContent = userCells.length > 0 || buttons.length > 0 || textElements.length > 0;
                    
                    console.log('Content check:');
                    console.log(`- User cells: ${userCells.length}`);
                    console.log(`- Action buttons: ${buttons.length}`);
                    console.log(`- Text indicators: ${textElements.length}`);
                    
                    if (userCells.length > 0) {
                        console.log('Sample cell text:', userCells[0].innerText.substring(0, 100));
                    }
                    
                    return hasContent;
                }
                return false;
                """
                content_loaded = self.driver.execute_script(check_content_script)
                
                if not content_loaded:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"{self.username} - [WARNING] Modal appears empty, retrying... ({retry_count}/{max_retries})")
                        
                        # Try closing and reopening the modal
                        close_modal_script = """
                        const closeButton = document.querySelector(
                            '[aria-label*="Close"], [data-testid*="close"], button[aria-label="Close"]'
                        );
                        if (closeButton) {
                            closeButton.click();
                            return true;
                        }
                        return false;
                        """
                        closed = self.driver.execute_script(close_modal_script)
                        
                        if closed:
                            print(f"{self.username} - [INFO] Closed modal, reopening...")
                            time.sleep(2)
                            # Navigate to follower requests again
                            self.driver.get("https://twitter.com/follower_requests")
                            time.sleep(3)
                        else:
                            # Refresh the page
                            print(f"{self.username} - [INFO] Refreshing page...")
                            self.driver.refresh()
                            time.sleep(5)
                            
                            # Check if modal reopened
                            try:
                                modal = self.wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                                )
                                print(f"{self.username} - [OK] Modal reopened after refresh")
                            except:
                                print(f"{self.username} - [ERROR] Modal did not reopen, navigating directly...")
                                self.driver.get("https://twitter.com/follower_requests")
                                time.sleep(3)
                else:
                    print(f"{self.username} - [OK] Modal content loaded successfully")
            
            if not content_loaded:
                print(f"{self.username} - [ERROR] Failed to load modal content after all retries")
                return False
            
            # Debug: Check what's in the modal
            debug_script = """
            console.log('Debugging follower requests modal...');
            const modal = document.querySelector('[role="dialog"], [aria-modal="true"], .modal');
            console.log('Modal found:', !!modal);
            if (modal) {
                console.log('Modal HTML:', modal.innerHTML.substring(0, 500));
            }
            const buttons = document.querySelectorAll('button');
            console.log('Total buttons found:', buttons.length);
            buttons.forEach((btn, i) => {
                if (i < 5) console.log(`Button ${i}:`, btn.textContent, btn.getAttribute('data-testid'));
            });
            """
            self.driver.execute_script(debug_script)
            
            # Get console logs
            time.sleep(1)
            
            # Check if we found any follow request entries
            check_content_script = """
            const modal = document.querySelector('[role="dialog"], [aria-modal="true"], .modal');
            if (modal) {
                // Look for user entries in the modal
                const userCells = modal.querySelectorAll('[data-testid*="UserCell"], [data-testid*="user-cell"], div[role="button"]');
                const hasContent = userCells.length > 0;
                console.log(`User cells found: ${userCells.length}`);
                return hasContent;
            }
            return false;
            """
            has_content = self.driver.execute_script(check_content_script)
            
            if not has_content:
                print(f"{self.username} - [WARNING] Modal appears empty, trying page refresh...")
                self.driver.refresh()
                time.sleep(5)
                
                # Check if modal reopened
                try:
                    modal = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                    )
                    print(f"{self.username} - [OK] Modal reopened after refresh")
                    time.sleep(3)
                except:
                    print(f"{self.username} - [ERROR] Modal did not reopen after refresh")
                    return False
            
            # Start the auto-approval with custom configuration
            # Make sure usernames are passed as an array
            allowed_usernames_json = json.dumps(self.allowed_usernames)
            
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
            
            // Double-check the list contains what we expect
            if (!allowedUsernames.includes('zeroshotflow')) {{
                console.error('ERROR: ZeroShotFlow not in list!');
            }}
            if (allowedUsernames.includes('lim_uncsrd')) {{
                console.error('ERROR: lim_uncsrd should NOT be in list!');
            }}
            
            const config = {{
                delay: 3000,
                maxApprovals: 50,
                autoScroll: true,
                allowedUsernames: allowedUsernames
            }};
            
            console.log('Starting with config:', config);
            window.startAutoApproval(config);
            """
            self.driver.execute_script(config_script)
            
            print(f"{self.username} - [OK] Auto-approver script injected and started!")
            
            # Monitor the progress
            self.monitor_approval_progress()
            
        except Exception as e:
            print(f"{self.username} - [ERROR] Error injecting script: {str(e)}")
            return False
    
    def save_approved_followers_to_api(self, approved_followers):
        """Save approved followers to the API"""
        if not self.api_key:
            print(f"{self.username} - [WARNING] No API key configured, skipping follower save")
            return 0
        
        try:
            print(f"\n{self.username} - [SAVING] Saving {len(approved_followers)} approved followers to API...")
            
            # Get the correct username from the database (case-sensitive)
            # First check what username is in the database
            api_url = self.api_base_url
            try:
                check_response = requests.get(
                    f"{api_url}/api/v1/accounts",
                    headers={"X-API-Key": self.api_key},
                    timeout=10
                )
                
                db_username = self.username  # Default to env username
                if check_response.status_code == 200:
                    accounts = check_response.json().get('accounts', [])
                    for account in accounts:
                        if account['username'].lower() == self.username.lower():
                            db_username = account['username']  # Use exact DB capitalization
                            break
            except:
                db_username = self.username
            
            # Prepare the batch update data
            batch_data = {
                "updates": [
                    {
                        "account_username": db_username,
                        "followers": approved_followers
                    }
                ]
            }
            
            # Send to API
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{api_url}/api/v1/accounts/batch-update-followers",
                json=batch_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"{self.username} - [OK] Successfully saved followers to API")
                print(f"   - Account: {self.username}")
                print(f"   - Followers saved: {len(approved_followers)}")
                
                # Log individual followers
                for follower in approved_followers:
                    print(f"   - @{follower['username']} ({follower.get('name', 'N/A')})")
                
                return len(approved_followers)
            else:
                print(f"{self.username} - [ERROR] Failed to save followers: {response.status_code}")
                print(f"   Response: {response.text}")
                return 0
                
        except requests.exceptions.ConnectionError:
            print(f"{self.username} - [WARNING] Could not connect to API server (connection refused)")
            print(f"   Make sure the Flask API is running on localhost:5555")
            print(f"   Attempted URL: {api_url}")
            return 0
        except Exception as e:
            print(f"{self.username} - [ERROR] Error saving followers to API: {str(e)}")
            return 0
    
    def monitor_approval_progress(self):
        """Monitor the auto-approval progress"""
        try:
            print(f"{self.username} - [INFO] Monitoring approval progress...")
            print(f"{self.username} - [INFO] Filtering for usernames: {', '.join(self.allowed_usernames)}")
            last_count = 0
            last_skipped = 0
            no_change_counter = 0
            
            while True:
                time.sleep(5)  # Check every 5 seconds
                
                # Get current status
                status = self.driver.execute_script("return window.getApprovalStatus();")
                
                if status:
                    current_count = status.get('approvedCount', 0)
                    skipped_count = status.get('skippedCount', 0)
                    is_running = status.get('isRunning', False)
                    max_approvals = status.get('maxApprovals', 0)
                    
                    # Only print if there's a change
                    if current_count != last_count or skipped_count != last_skipped:
                        print(f"{self.username} - [INFO] Progress: {current_count}/{max_approvals} approved, {skipped_count} skipped (not in allowed list)")
                        last_count = current_count
                        last_skipped = skipped_count
                    
                    # Check if completed
                    if not is_running:
                        print(f"{self.username} - [OK] Auto-approval completed! Total approved: {current_count}, skipped: {skipped_count}")
                        
                        # Save approved followers to API
                        approved_followers = status.get('approvedFollowers', [])
                        if approved_followers:
                            self.save_approved_followers_to_api(approved_followers)
                        
                        break
                    
                    # Check if stuck (no new approvals or skips)
                    if current_count == last_count and skipped_count == last_skipped:
                        no_change_counter += 1
                        if no_change_counter > 6:  # No change for 30 seconds
                            print(f"{self.username} - [WARNING] No progress detected, may have completed all available requests")
                            break
                    else:
                        no_change_counter = 0
                else:
                    print(f"{self.username} - [WARNING] Could not get approval status")
                    break
                    
        except Exception as e:
            print(f"{self.username} - [ERROR] Error monitoring progress: {str(e)}")
    
    def run_full_automation(self):
        """Run the complete automation workflow"""
        try:
            # Set up driver
            self.setup_driver()
            
            # Login to Twitter
            if not self.login_with_session_management():
                print(f"{self.username} - [ERROR] Failed to login to Twitter")
                print(f"{self.username} - Please check:")
                print(f"{self.username} - 1. Username and password in .env file")
                print(f"{self.username} - 2. If Twitter requires additional verification")
                return False
            
            # Navigate to follow requests
            if not self.navigate_to_follow_requests():
                print("\n[WARNING] Could not access follow requests")
                print("\nPossible reasons:")
                print("1. You don't have any pending follow requests")
                print("2. Your account is public (only private accounts have follow requests)")
                print("3. Twitter's UI may have changed")
                print("\nTo use this tool:")
                print("1. Make sure your account is set to private/protected")
                print("2. Wait for someone to request to follow you")
                print("3. Run this script again when you have pending requests")
                return False
            
            # Inject and run auto-approver
            self.inject_auto_approver_script()
            
            print(f"{self.username} - [OK] Automation completed!")
            return True
            
        except Exception as e:
            print(f"{self.username} - [ERROR] Automation error: {str(e)}")
            return False
        finally:
            # Auto-close browser after a short delay
            if not self.headless:
                print(f"{self.username} - [INFO] Closing browser in 3 seconds...")
                time.sleep(3)
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print(f"{self.username} - [INFO] Browser closed.")

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

    def get_verification_code_from_gmail_imap(self, max_wait_time=60):
        """
        Retrieve verification code from Gmail using IMAP (bypasses 2FA)
        Enhanced to filter by recipient and recent emails only
        
        Args:
            max_wait_time (int): Maximum time to wait for email
            
        Returns:
            str: Verification code if found, None if not found
        """
        if not self.gmail_username or not self.gmail_app_password:
            print(f"{self.username} - [ERROR] Gmail credentials not configured")
            return None
        
        if not self.email:
            print(f"{self.username} - [ERROR] Account email not configured - cannot filter by recipient")
            return None
        
        try:
            print(f"{self.username} - [INFO] Connecting to Gmail via IMAP to retrieve verification code...")
            print(f"{self.username} - [INFO] Filtering for emails TO: {self.email}")
            
            # Gmail IMAP settings
            email_server = 'imap.gmail.com'
            email_port = 993
            
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL(email_server, email_port)
            mail.login(self.gmail_username, self.gmail_app_password)
            mail.select('inbox')
            
            start_time = time.time()
            verification_code = None
            
            while time.time() - start_time < max_wait_time:
                try:
                    # Search for recent emails TO the specific account (past 2 minutes)
                    import datetime
                    
                    # Get timestamp for 2 minutes ago
                    two_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=2)
                    date_string = two_minutes_ago.strftime("%d-%b-%Y")
                    
                    print(f"{self.username} - [INFO] Searching for X verification emails since {date_string}...")
                    
                    # Build search query for recent emails TO the specific account
                    search_queries = [
                        f'(TO "{self.email}" FROM "info@x.com" SINCE "{date_string}")',
                        f'(TO "{self.email}" FROM "verify@twitter.com" SINCE "{date_string}")',
                        f'(TO "{self.email}" FROM "info@twitter.com" SINCE "{date_string}")',
                        f'(TO "{self.email}" SUBJECT "confirmation code" SINCE "{date_string}")',
                        f'(TO "{self.email}" SUBJECT "verification code" SINCE "{date_string}")'
                    ]
                    
                    email_ids = []
                    for query in search_queries:
                        try:
                            print(f"{self.username} - [DEBUG] Searching with: {query}")
                            _, messages = mail.search(None, query)
                            if messages[0]:
                                found_ids = messages[0].split()
                                email_ids.extend(found_ids)
                                print(f"{self.username} - [DEBUG] Found {len(found_ids)} emails with this query")
                        except Exception as e:
                            print(f"{self.username} - [DEBUG] Search query failed: {e}")
                            continue
                    
                    # Remove duplicates and get most recent emails
                    email_ids = list(set(email_ids))
                    
                    if email_ids:
                        print(f"{self.username} - [INFO] Found {len(email_ids)} potential verification emails for {self.email}")
                        
                        # Sort by email ID (newer emails have higher IDs) and check most recent first
                        email_ids.sort(key=int, reverse=True)
                        
                        # Check latest emails first (last 5 should be enough)
                        for email_id in email_ids[:5]:
                            try:
                                _, msg = mail.fetch(email_id, '(RFC822)')
                                email_message = email.message_from_bytes(msg[0][1])
                                
                                # Double-check the TO field
                                to_header = email_message.get('To', '')
                                if self.email.lower() not in to_header.lower():
                                    print(f"{self.username} - [DEBUG] Skipping email - TO field '{to_header}' doesn't match '{self.email}'")
                                    continue
                                
                                # Check email date to ensure it's actually recent
                                date_header = email_message.get('Date', '')
                                print(f"{self.username} - [DEBUG] Checking email TO: {to_header}, Date: {date_header}")
                                
                                # Get subject line - X puts the code in the subject!
                                subject = email_message.get('Subject', '')
                                print(f"{self.username} - [INFO] Checking email subject: {subject}")
                                
                                # Extract verification code from subject line
                                code_patterns = [
                                    r'(\d{6}) is your X verification code',  # 6 digits for new accounts
                                    r'Your X confirmation code is ([a-zA-Z0-9]{8})',  # 8 chars for existing
                                    r'Your X confirmation code is ([a-zA-Z0-9]{6,8})',  # Variable length
                                    r'(\d{6,8}) is your',  # Fallback for digits
                                    r'code is ([a-zA-Z0-9]{6,8})',  # Fallback
                                    r'confirmation code is ([a-zA-Z0-9]+)',  # Generic pattern
                                ]
                                
                                for pattern in code_patterns:
                                    code_match = re.search(pattern, subject, re.IGNORECASE)
                                    if code_match:
                                        verification_code = code_match.group(1)
                                        print(f"{self.username} - [OK] Found verification code in subject: {verification_code}")
                                        print(f"{self.username} - [OK] Email TO: {to_header}")
                                        break
                                
                                # If not found in subject, check body as fallback
                                if not verification_code:
                                    body = self.get_email_body(email_message)
                                    for pattern in code_patterns:
                                        code_match = re.search(pattern, body, re.IGNORECASE)
                                        if code_match:
                                            verification_code = code_match.group(1)
                                            print(f"{self.username} - [OK] Found verification code in body: {verification_code}")
                                            print(f"{self.username} - [OK] Email TO: {to_header}")
                                            break
                                
                                if verification_code:
                                    break
                                    
                            except Exception as e:
                                print(f"{self.username} - [WARNING] Error parsing email: {str(e)}")
                                continue
                    else:
                        print(f"{self.username} - [INFO] No recent verification emails found for {self.email}")
                
                    if verification_code:
                        break
                    
                    print(f"{self.username} - [INFO] No code found yet, waiting... ({int(time.time() - start_time)}s)")
                    time.sleep(5)
                
                except Exception as e:
                    print(f"{self.username} - [WARNING] Error during email search: {str(e)}")
                    time.sleep(5)
        
            # Close IMAP connection
            mail.close()
            mail.logout()
            
            if verification_code:
                print(f"{self.username} - [OK] Successfully retrieved verification code: {verification_code}")
            else:
                print(f"{self.username} - [ERROR] No verification code found for {self.email} within timeout period")
            
            return verification_code
            
        except Exception as e:
            print(f"{self.username} - [ERROR] Error retrieving verification code via IMAP: {str(e)}")
            return None

    def login_with_session_management(self):
        """Enhanced login that tries session restoration first"""
        print(f"\n🔐 Attempting login for @{self.username}")
        
        # Clean up expired sessions first
        if hasattr(self.session_manager, 'cleanup_expired_sessions'):
            self.session_manager.cleanup_expired_sessions()
        
        # Try to restore existing session
        if self.session_manager.load_session(self.username, self.driver):
            print(f"   ✅ Session restored successfully for @{self.username}")
            
            # Verify we can access follow requests (basic functionality test)
            try:
                self.driver.get("https://x.com/follower_requests")
                time.sleep(3)
                
                # Check if we're on the right page
                if "follow" in self.driver.current_url.lower() or "follower" in self.driver.current_url.lower():
                    print(f"   ✅ Session is fully functional for @{self.username}")
                    return True
                else:
                    print(f"   ⚠️ Session restored but cannot access follow requests")
            except Exception as e:
                print(f"   ⚠️ Session verification failed: {str(e)}")
        
        # Fall back to normal login
        print(f"   🔑 Performing fresh login for @{self.username}")
        login_success = self.login_to_twitter()
        
        # NEW: If standard login fails, try human behavior as last resort
        if not login_success:
            print(f"   🤖 Standard login failed, trying human-like login for @{self.username}")
            login_success = self.login_to_twitter_with_human_behavior()
            
            if login_success:
                print(f"   ✅ Human-like login succeeded where standard failed!")
            else:
                print(f"   ❌ Both login methods failed for @{self.username}")
        
        if login_success:
            # Save the new session
            print(f"   💾 Saving new session for @{self.username}")
            self.session_manager.save_session(self.username, self.driver)
        
        return login_success


def main():
    """Main function to run the automation"""
    # Check for required environment variables
    required_vars = ['TWITTER_USERNAME', 'TWITTER_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("[ERROR] Missing required environment variables:")
        print(f"   {', '.join(missing_vars)}")
        print("\nPlease create a .env file with:")
        print("TWITTER_USERNAME=your_username")
        print("TWITTER_PASSWORD=your_password")
        print("TWITTER_EMAIL=your_email (optional, for verification)")
        print("ALLOWED_USERNAMES=user1,user2,user3 (optional, for filtering)")
        return
    
    # Create automation instance
    automation = TwitterSeleniumAutomation(headless=False)
    
    # Display configuration
    print("\n" + "="*50)
    print("🐦 Twitter Auto-Approver Configuration")
    print("="*50)
    print(f"Account: @{automation.username}")
    print(f"Username Filter: {'Enabled' if automation.allowed_usernames else 'Disabled'}")
    if automation.allowed_usernames:
        print(f"Allowed Usernames (lowercase): {', '.join(automation.allowed_usernames)}")
        print("Note: All usernames are matched case-insensitively")
    print("="*50 + "\n")
    
    # Run the automation
    automation.run_full_automation()


if __name__ == "__main__":
    main()