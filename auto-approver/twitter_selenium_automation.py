#!/usr/bin/env python3
"""
Twitter Selenium Automation for Follow Request Management
This script automates the process of logging into Twitter and managing follow requests.
For educational and legitimate account management purposes only.
"""

import os
import time
import json
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
        
        if not self.username or not self.password:
            raise ValueError("Twitter credentials not found in environment variables")
        
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
            
            # User agent to appear more like a real browser
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
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
                print("⚠️ Authentication code required but not provided, skipping this account")
                self.auth_code_skipped = True
                return False
            
            # Verify login by checking for home timeline or profile elements
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
            )
            print("✅ Successfully logged into Twitter!")
            return True
            
        except TimeoutException:
            print("❌ Login timeout - check your credentials or Twitter's UI may have changed")
            return False
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
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
                                    print(f"❌ Error: {error_elem.text}")
                                    print("The code may be incorrect. You can try again.")
                                    # Allow retry
                                    continue
                            except:
                                pass
                    except:
                        # Auth code input disappeared, likely successful
                        print("✅ Authentication code accepted!")
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
            
            # Check if we're on the follower requests page
            if "follower_requests" in self.driver.current_url:
                print("✅ Successfully navigated to follower requests page")
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
                    print("✅ Clicked More menu")
                    time.sleep(2)
                    break
                except NoSuchElementException:
                    continue
            
            if not more_clicked:
                print("❌ Could not find More menu button")
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
                        print("✅ Clicked Follower requests link")
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
                    print("✅ Clicked Follower requests link")
                    time.sleep(3)
                    return True
                except NoSuchElementException:
                    continue
            
            print("❌ Could not find Follower requests option in More menu")
            
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
                        print("✅ Found and clicked follow requests via profile")
                        time.sleep(3)
                        return True
            except Exception as e:
                print(f"Alternative method also failed: {str(e)}")
            
            return False
            
        except TimeoutException:
            print("❌ Navigation timeout - the page may not have loaded properly")
            return False
        except Exception as e:
            print(f"❌ Error navigating to follow requests: {str(e)}")
            return False
    
    def inject_auto_approver_script(self):
        """Inject and execute the auto-approver JavaScript"""
        try:
            # Wait a bit for the popup to fully load
            time.sleep(2)
            
            # Check if we're on the follower requests page
            current_url = self.driver.current_url
            if "follower_requests" not in current_url:
                print("❌ Not on follower requests page")
                return False
            
            print("Checking for follow request popup...")
            
            # The follower requests are now in a modal/popup
            # Wait for the modal to be present
            try:
                # Look for the modal dialog
                modal = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                )
                print("✅ Found follower requests modal")
            except TimeoutException:
                print("⚠️ No modal found, checking if requests are on the page directly...")
            
            print("Injecting auto-approver script...")
            
            # Read the auto-approver script with UTF-8 encoding
            script_path = os.path.join(os.path.dirname(__file__), 'twitter_auto_approver.js')
            with open(script_path, 'r', encoding='utf-8') as f:
                auto_approver_script = f.read()
            
            # Inject the script
            self.driver.execute_script(auto_approver_script)
            
            # Wait for modal content to load
            print("Waiting for modal content to load...")
            time.sleep(5)
            
            # Try to trigger content loading by scrolling
            print("Attempting to trigger content load...")
            trigger_script = """
            // Find the modal
            const modal = document.querySelector('[role="dialog"], [aria-modal="true"], .modal');
            if (modal) {
                // Try to find scrollable container within modal
                const scrollContainers = modal.querySelectorAll('[data-testid*="scroll"], [class*="scroll"], div[style*="overflow"]');
                console.log(`Found ${scrollContainers.length} potential scroll containers`);
                
                // Scroll each container
                scrollContainers.forEach(container => {
                    container.scrollTop = 100;
                    container.scrollTop = 0;
                });
                
                // Also try scrolling the modal itself
                modal.scrollTop = 100;
                modal.scrollTop = 0;
                
                // Dispatch scroll events
                modal.dispatchEvent(new Event('scroll'));
                
                // Click somewhere in the modal to ensure it's focused
                const modalHeader = modal.querySelector('h2, h3, [role="heading"]');
                if (modalHeader) {
                    modalHeader.click();
                }
            }
            
            // Check if we're truly on the follower_requests page
            console.log('Current URL:', window.location.href);
            
            // Look for any loading indicators
            const loadingIndicators = document.querySelectorAll('[aria-label*="Loading"], [class*="loading"], [class*="spinner"]');
            console.log(`Loading indicators found: ${loadingIndicators.length}`);
            """
            self.driver.execute_script(trigger_script)
            
            # Wait more for content to load after triggering
            print("Waiting for content after trigger...")
            time.sleep(5)
            
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
                print("⚠️ Modal appears empty, trying page refresh...")
                self.driver.refresh()
                time.sleep(5)
                
                # Check if modal reopened
                try:
                    modal = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"], [aria-modal="true"], .modal'))
                    )
                    print("✅ Modal reopened after refresh")
                    time.sleep(3)
                except:
                    print("❌ Modal did not reopen after refresh")
                    return False
            
            # Start the auto-approval with custom configuration
            config_script = """
            // Start auto-approval with configuration
            window.startAutoApproval({
                delay: 3000,        // 3 seconds between actions
                maxApprovals: 50,   // Maximum 50 approvals
                autoScroll: true    // Auto-scroll enabled
            });
            """
            self.driver.execute_script(config_script)
            
            print("✅ Auto-approver script injected and started!")
            
            # Monitor the progress
            self.monitor_approval_progress()
            
        except Exception as e:
            print(f"❌ Error injecting script: {str(e)}")
            return False
    
    def monitor_approval_progress(self):
        """Monitor the auto-approval progress"""
        try:
            print("Monitoring approval progress...")
            last_count = 0
            no_change_counter = 0
            
            while True:
                time.sleep(5)  # Check every 5 seconds
                
                # Get current status
                status = self.driver.execute_script("return window.getApprovalStatus();")
                
                if status:
                    current_count = status.get('approvedCount', 0)
                    is_running = status.get('isRunning', False)
                    max_approvals = status.get('maxApprovals', 0)
                    
                    print(f"Progress: {current_count}/{max_approvals} approved")
                    
                    # Check if completed
                    if not is_running:
                        print(f"✅ Auto-approval completed! Total approved: {current_count}")
                        break
                    
                    # Check if stuck
                    if current_count == last_count:
                        no_change_counter += 1
                        if no_change_counter > 6:  # No change for 30 seconds
                            print("⚠️ No progress detected, may have completed all available requests")
                            break
                    else:
                        no_change_counter = 0
                    
                    last_count = current_count
                else:
                    print("⚠️ Could not get approval status")
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
                print("\n❌ Failed to login to Twitter")
                print("Please check:")
                print("- Your username and password in .env file")
                print("- Your internet connection")
                print("- If Twitter requires additional verification")
                return False
            
            # Navigate to follow requests
            if not self.navigate_to_follow_requests():
                print("\n⚠️ Could not access follow requests")
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
            
            print("\n✅ Automation completed!")
            return True
            
        except Exception as e:
            print(f"\n❌ Automation error: {str(e)}")
            return False
        finally:
            # Keep browser open for a bit to see results
            if not self.headless:
                input("\nPress Enter to close the browser...")
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
        print("❌ Missing required environment variables:")
        print(f"   {', '.join(missing_vars)}")
        print("\nPlease create a .env file with:")
        print("TWITTER_USERNAME=your_username")
        print("TWITTER_PASSWORD=your_password")
        print("TWITTER_EMAIL=your_email (optional, for verification)")
        return
    
    # Create automation instance
    automation = TwitterSeleniumAutomation(headless=False)
    
    # Run the automation
    automation.run_full_automation()


if __name__ == "__main__":
    main()