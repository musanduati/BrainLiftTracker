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
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

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
        
    def setup_driver(self):
        """Set up the Selenium WebDriver with system ChromeDriver"""
        if self.browser_type == "chrome":
            from selenium.webdriver.chrome.service import Service
            
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
            
            # User agent to appear more like a real browser
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            if self.headless:
                options.add_argument('--headless')
            
            # Use system ChromeDriver (installed in container)
            try:
                print("Setting up ChromeDriver from system PATH...")
                service = Service('/usr/local/bin/chromedriver')
                self.driver = webdriver.Chrome(service=service, options=options)
                print("✅ ChromeDriver setup successful!")
            except Exception as e:
                print(f"❌ ChromeDriver setup failed: {e}")
                raise
            
        elif self.browser_type == "firefox":
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from webdriver_manager.firefox import GeckoDriverManager
            
            options = FirefoxOptions()
            
            if self.headless:
                options.add_argument('--headless')
            
            service = FirefoxService(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            
        else:
            raise ValueError(f"Unsupported browser type: {self.browser_type}")
        
        # Set up wait
        self.wait = WebDriverWait(self.driver, 20)
        
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def login_to_twitter(self):
        """Log into Twitter using credentials"""
        try:
            print("Navigating to Twitter login page...")
            self.driver.get("https://twitter.com/login")
            time.sleep(3)  # Allow page to load
            
            # Enter username
            print("Entering username...")
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
            )
            username_input.clear()
            username_input.send_keys(self.username)
            username_input.send_keys(Keys.RETURN)
            time.sleep(2)
            
            # Check if email verification is required
            try:
                email_input = self.driver.find_element(By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
                if email_input and self.email:
                    print("Email verification required, entering email...")
                    email_input.clear()
                    email_input.send_keys(self.email)
                    email_input.send_keys(Keys.RETURN)
                    time.sleep(2)
            except NoSuchElementException:
                pass  # Email verification not required
            
            # Enter password
            print("Entering password...")
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
            )
            password_input.clear()
            password_input.send_keys(self.password)
            password_input.send_keys(Keys.RETURN)
            
            # Wait for login to complete
            print("Waiting for login to complete...")
            time.sleep(5)
            
            # Check for authentication code request
            auth_code_required = self.handle_auth_code_if_needed()
            if auth_code_required == "skip":
                print("[WARNING] Authentication code required but not provided, skipping this account")
                self.auth_code_skipped = True
                return False
            
            # Verify login by checking for home timeline or profile elements
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
            )
            print("[OK] Successfully logged into Twitter!")
            return True
            
        except TimeoutException:
            print("[ERROR] Login timeout - check your credentials or Twitter's UI may have changed")
            return False
        except Exception as e:
            print(f"[ERROR] Login error: {str(e)}")
            return False
    
    def handle_auth_code_if_needed(self, timeout=60):
        """
        Handle authentication code if Twitter requests it
        
        Args:
            timeout (int): Maximum time to wait for user input in seconds
            
        Returns:
            str: "success" if code entered and accepted, "skip" if timeout, "none" if no code needed
        """
        try:
            # Check for authentication code input field
            # Twitter may use different selectors for the auth code input
            auth_code_selectors = [
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[name="text"]',
                'input[inputmode="numeric"]',
                'input[autocomplete="one-time-code"]',
                'input[type="text"][aria-label*="code"]',
                'input[type="text"][aria-label*="Code"]',
                'input[placeholder*="code"]',
                'input[placeholder*="Code"]'
            ]
            
            auth_code_input = None
            for selector in auth_code_selectors:
                try:
                    # Use a short timeout for each selector
                    auth_code_input = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # Verify it's actually visible and for auth code
                    if auth_code_input.is_displayed():
                        # Check surrounding text for auth code context
                        parent = auth_code_input.find_element(By.XPATH, './..')
                        page_text = parent.text.lower()
                        if any(keyword in page_text for keyword in ['code', 'verify', 'authentication', 'confirm']):
                            break
                    auth_code_input = None
                except:
                    continue
            
            if not auth_code_input:
                # No auth code required
                return "none"
            
            print("\n" + "="*50)
            print("🔐 AUTHENTICATION CODE REQUIRED")
            print("="*50)
            print(f"\nTwitter is requesting an authentication code for account: {self.username}")
            print("This code may have been sent to:")
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
                            EC.presence_of_element_located((By.CSS_SELECTOR, auth_code_input))
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
                    except:
                        # Auth code input disappeared, likely successful
                        print("[OK] Authentication code accepted!")
                        return "success"
                    
                    code_entered = True
                    break
                    
                except queue.Empty:
                    # No input yet, show countdown
                    remaining = int(timeout - (time.time() - start_time))
                    if remaining % 10 == 0 and remaining > 0:
                        print(f"⏱️  {remaining} seconds remaining...")
                except Exception as e:
                    print(f"Error handling auth code: {e}")
                    break
            
            if not code_entered:
                print("\n⏱️  Timeout reached, skipping this account...")
                return "skip"
            
            return "success"
            
        except Exception as e:
            print(f"Error checking for auth code: {e}")
            return "none"
    
    def navigate_to_follow_requests(self):
        """Navigate to the follow requests section"""
        try:
            # Method 1: Try direct navigation to follower_requests endpoint
            print("Navigating directly to follower requests page...")
            self.driver.get("https://twitter.com/follower_requests")
            time.sleep(3)
            
            # CRITICAL FIX: Always refresh to force modal content to load
            print("Forcing page refresh to load modal content...")
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
                print("[OK] Successfully navigated to follower requests page")
                return True
            
            # Method 2: Navigate via More menu
            print("Trying to access via More menu...")
            
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
                    print("[OK] Clicked More menu")
                    time.sleep(2)
                    break
                except NoSuchElementException:
                    continue
            
            if not more_clicked:
                print("[ERROR] Could not find More menu button")
                return False
            
            # Look for "Follower requests" in the More menu
            print("Looking for Follower requests option...")
            
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
                        print("[OK] Clicked Follower requests link")
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
                    print("[OK] Clicked Follower requests link")
                    time.sleep(3)
                    return True
                except NoSuchElementException:
                    continue
            
            print("[ERROR] Could not find Follower requests option in More menu")
            
            # Method 3: Try the old way via profile -> followers (fallback)
            print("\nTrying alternative method via profile...")
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
                        print("[OK] Found and clicked follow requests via profile")
                        time.sleep(3)
                        return True
            except Exception as e:
                print(f"Alternative method also failed: {str(e)}")
            
            return False
            
        except TimeoutException:
            print("[ERROR] Navigation timeout - the page may not have loaded properly")
            return False
        except Exception as e:
            print(f"[ERROR] Error navigating to follow requests: {str(e)}")
            return False
    
    def inject_auto_approver_script(self):
        """Inject and execute the auto-approver JavaScript"""
        try:
            # Wait a bit for the popup to fully load
            time.sleep(2)
            
            # Check if we're on the follower requests page
            current_url = self.driver.current_url
            if "follower_requests" not in current_url:
                print("[ERROR] Not on follower requests page")
                return False
            
            print("Checking for follow request popup...")
            
            # The follower requests are now in a modal/popup
            # Wait for the modal to be present
            try:
                # Look for the modal dialog
                modal = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                )
                print("[OK] Found follower requests modal")
            except TimeoutException:
                print("[WARNING] No modal found, will check after refresh...")
            
            # Enhanced loading strategy - refresh already done in navigate_to_follow_requests
            print("Checking for modal content...")
            
            # Step 1: Wait a moment for modal to appear after navigation
            time.sleep(3)
            
            # Step 2: Check if modal is present
            modal_present = False
            try:
                modal = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"]'))
                )
                modal_present = True
                print("[OK] Modal found")
                
                # Wait specifically for modal content to load
                print("Waiting for modal content to populate...")
                
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
                print("[WARNING] Modal not found, trying direct navigation...")
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
                    print("[OK] Modal appeared after navigation")
                except:
                    print("[ERROR] Still no modal, trying one more refresh...")
                    self.driver.refresh()
                    time.sleep(5)
            
            # Step 3: NOW inject the auto-approver script AFTER refresh
            print("Step 2: Injecting auto-approver script...")
            script_path = os.path.join(os.path.dirname(__file__), 'twitter_auto_approver.js')
            with open(script_path, 'r', encoding='utf-8') as f:
                auto_approver_script = f.read()
            
            self.driver.execute_script(auto_approver_script)
            print("[OK] Script injected")
            
            # Step 4: Wait and check for content with retries
            print("Step 3: Checking for modal content...")
            max_retries = 3
            retry_count = 0
            content_loaded = False
            
            while retry_count < max_retries and not content_loaded:
                if retry_count > 0:
                    print(f"Retry {retry_count}/{max_retries}: Attempting to load modal content...")
                
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
                print("Attempting to trigger content load...")
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
                print("Waiting for content to render...")
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
                        print(f"[WARNING] Modal appears empty, retrying... ({retry_count}/{max_retries})")
                        
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
                            print("Closed modal, reopening...")
                            time.sleep(2)
                            # Navigate to follower requests again
                            self.driver.get("https://twitter.com/follower_requests")
                            time.sleep(3)
                        else:
                            # Refresh the page
                            print("Refreshing page...")
                            self.driver.refresh()
                            time.sleep(5)
                            
                            # Check if modal reopened
                            try:
                                modal = self.wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                                )
                                print("[OK] Modal reopened after refresh")
                            except:
                                print("[ERROR] Modal did not reopen, navigating directly...")
                                self.driver.get("https://twitter.com/follower_requests")
                                time.sleep(3)
                else:
                    print("[OK] Modal content loaded successfully")
            
            if not content_loaded:
                print("[ERROR] Failed to load modal content after all retries")
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
                print("[WARNING] Modal appears empty, trying page refresh...")
                self.driver.refresh()
                time.sleep(5)
                
                # Check if modal reopened
                try:
                    modal = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                    )
                    print("[OK] Modal reopened after refresh")
                    time.sleep(3)
                except:
                    print("[ERROR] Modal did not reopen after refresh")
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
            
            print("[OK] Auto-approver script injected and started!")
            
            # Monitor the progress
            self.monitor_approval_progress()
            
        except Exception as e:
            print(f"[ERROR] Error injecting script: {str(e)}")
            return False
    
    def save_approved_followers_to_api(self, approved_followers):
        """Save approved followers to the API"""
        if not self.api_key:
            print("[WARNING] No API key configured, skipping follower save")
            return 0
        
        try:
            print(f"\n[SAVING] Saving {len(approved_followers)} approved followers to API...")
            
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
                print(f"[OK] Successfully saved followers to API")
                print(f"   - Account: {self.username}")
                print(f"   - Followers saved: {len(approved_followers)}")
                
                # Log individual followers
                for follower in approved_followers:
                    print(f"   - @{follower['username']} ({follower.get('name', 'N/A')})")
                
                return len(approved_followers)
            else:
                print(f"[ERROR] Failed to save followers: {response.status_code}")
                print(f"   Response: {response.text}")
                return 0
                
        except requests.exceptions.ConnectionError:
            print("[WARNING] Could not connect to API server (connection refused)")
            print("   Make sure the Flask API is running on localhost:5555")
            print(f"   Attempted URL: {api_url}")
            return 0
        except Exception as e:
            print(f"[ERROR] Error saving followers to API: {str(e)}")
            return 0
    
    def monitor_approval_progress(self):
        """Monitor the auto-approval progress"""
        try:
            print("Monitoring approval progress...")
            print(f"Filtering for usernames: {', '.join(self.allowed_usernames)}")
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
                        print(f"Progress: {current_count}/{max_approvals} approved, {skipped_count} skipped (not in allowed list)")
                        last_count = current_count
                        last_skipped = skipped_count
                    
                    # Check if completed
                    if not is_running:
                        print(f"[OK] Auto-approval completed! Total approved: {current_count}, skipped: {skipped_count}")
                        
                        # Save approved followers to API
                        approved_followers = status.get('approvedFollowers', [])
                        if approved_followers:
                            self.save_approved_followers_to_api(approved_followers)
                        
                        break
                    
                    # Check if stuck (no new approvals or skips)
                    if current_count == last_count and skipped_count == last_skipped:
                        no_change_counter += 1
                        if no_change_counter > 6:  # No change for 30 seconds
                            print("[WARNING] No progress detected, may have completed all available requests")
                            break
                    else:
                        no_change_counter = 0
                else:
                    print("[WARNING] Could not get approval status")
                    break
                    
        except Exception as e:
            print(f"Error monitoring progress: {str(e)}")
    
    def run_full_automation(self):
        """Run the complete automation workflow"""
        try:
            # Set up driver
            self.setup_driver()
            
            # Login to Twitter
            if not self.login_to_twitter():
                print("\n[ERROR] Failed to login to Twitter")
                print("Please check:")
                print("- Your username and password in .env file")
                print("- Your internet connection")
                print("- If Twitter requires additional verification")
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
            
            print("\n[OK] Automation completed!")
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Automation error: {str(e)}")
            return False
        finally:
            # Auto-close browser after a short delay
            if not self.headless:
                print("\nClosing browser in 3 seconds...")
                time.sleep(3)
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Browser closed.")


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