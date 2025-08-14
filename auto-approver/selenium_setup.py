#!/usr/bin/env python3
"""
Enhanced Selenium setup with automatic driver management
"""

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

def is_containerized_environment():
    """Detect if we're running in a containerized environment like AWS Fargate"""
    # Check for manually installed ChromeDriver (installed by Dockerfile)
    if os.path.exists('/usr/local/bin/chromedriver'):
        return True
    
    # Check for container environment variables
    container_indicators = [
        'AWS_EXECUTION_ENV',  # AWS Lambda/Fargate
        'ECS_CONTAINER_METADATA_URI',  # ECS
        'KUBERNETES_SERVICE_HOST',  # Kubernetes
        'DOCKER_CONTAINER'  # Generic Docker flag
    ]
    
    for indicator in container_indicators:
        if os.environ.get(indicator):
            return True
    
    # Check if we're in a Docker container by looking for .dockerenv
    if os.path.exists('/.dockerenv'):
        return True
        
    return False

def get_chrome_driver(headless=False):
    """Get Chrome driver with auto-downloaded driver"""
    options = ChromeOptions()
    
    # Anti-detection options
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # General options
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,800')
    options.add_argument('--start-maximized')
    
    # User agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    if headless:
        options.add_argument('--headless=new')  # New headless mode
    
    # Choose ChromeDriver approach based on environment
    if is_containerized_environment():
        # Use pre-installed ChromeDriver in container
        chromedriver_path = '/usr/local/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            print(f"🐳 Using containerized ChromeDriver: {chromedriver_path}")
            service = Service(chromedriver_path)
        else:
            raise RuntimeError(f"Expected ChromeDriver not found at {chromedriver_path}")
    else:
        # Use webdriver_manager for local development
        print("💻 Using webdriver_manager for local ChromeDriver")
        try:
            service = Service(ChromeDriverManager().install())
        except AttributeError:
            # Fallback: specify Chrome version if auto-detection fails
            from webdriver_manager.core.os_manager import ChromeType
            service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
    
    # Create driver
    driver = webdriver.Chrome(service=service, options=options)
    
    # Safer anti-detection (only if it works)
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        print(f"⚠️ Anti-detection script failed (this is OK): {e}")
        # Continue without anti-detection - modern Chrome blocks this anyway
    
    return driver

def get_firefox_driver(headless=False):
    """Get Firefox driver with auto-downloaded driver"""
    options = FirefoxOptions()
    
    if headless:
        options.add_argument('--headless')
    
    # Anti-detection
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference('useAutomationExtension', False)
    
    # Auto-download and set up GeckoDriver
    service = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)
    
    return driver

def get_edge_driver(headless=False):
    """Get Edge driver with auto-downloaded driver"""
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    
    options = EdgeOptions()
    
    if headless:
        options.add_argument('--headless')
    
    # Similar options as Chrome
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Auto-download and set up EdgeDriver
    service = EdgeService(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=options)
    
    return driver

if __name__ == "__main__":
    # Test driver setup
    print("Testing Chrome driver setup...")
    print(f"Containerized environment: {is_containerized_environment()}")
    try:
        driver = get_chrome_driver()
        print("Chrome driver setup successful!")
        driver.quit()
    except Exception as e:
        print(f"Chrome driver setup failed: {e}")