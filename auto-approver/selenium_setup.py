#!/usr/bin/env python3
"""
Enhanced Selenium setup with automatic driver management
"""

import os
import random
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
    """Enhanced Chrome driver with direct ChromeDriver path for macOS"""
    options = ChromeOptions()
    
    # ===== ENHANCED ANTI-DETECTION =====
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Additional stealth options
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-client-side-phishing-detection')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-hang-monitor')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-sync')
    options.add_argument('--no-first-run')
    options.add_argument('--password-store=basic')
    
    # Container-specific
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # ===== RANDOMIZATION =====
    width = random.randint(1200, 1400)
    height = random.randint(800, 1000)
    options.add_argument(f'--window-size={width},{height}')
    
    # Randomize user agent
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    if headless:
        options.add_argument('--headless=new')
    
    # ===== IMPROVED DRIVER SETUP =====
    if is_containerized_environment():
        # Container path (for production)
        chromedriver_path = '/usr/local/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            print(f"🐳 Using containerized ChromeDriver: {chromedriver_path}")
            service = Service(chromedriver_path)
        else:
            raise RuntimeError(f"Expected ChromeDriver not found at {chromedriver_path}")
    else:
        # Local development - try multiple approaches
        print("💻 Setting up ChromeDriver for local development...")
        
        # Try system ChromeDriver first (via Homebrew)
        system_chromedriver_paths = [
            '/opt/homebrew/bin/chromedriver',  # ARM64 Homebrew
            '/usr/local/bin/chromedriver',     # Intel Homebrew
            '/usr/bin/chromedriver'            # System path
        ]
        
        chromedriver_found = False
        for path in system_chromedriver_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print(f"✅ Using system ChromeDriver: {path}")
                service = Service(path)
                chromedriver_found = True
                break
        
        if not chromedriver_found:
            # Fallback to webdriver-manager with better error handling
            print("🔄 Trying webdriver-manager...")
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.os_manager import ChromeType
                
                # Force download for correct architecture
                driver_path = ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install()
                print(f"📥 Downloaded ChromeDriver: {driver_path}")
                service = Service(driver_path)
                
            except Exception as e:
                print(f"❌ WebDriver Manager failed: {e}")
                raise RuntimeError("Could not set up ChromeDriver. Please install via 'brew install chromedriver'")
    
    # Create driver
    try:
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ ChromeDriver initialized successfully")
    except Exception as e:
        print(f"❌ ChromeDriver initialization failed: {e}")
        raise
    
    # ===== ENHANCED STEALTH INJECTION =====
    try:
        def get_enhanced_stealth_script():
            """Generate advanced stealth JavaScript with error handling"""
            # Randomize screen properties
            screen_width = random.randint(1920, 2560)
            screen_height = random.randint(1080, 1440)
            color_depth = random.choice([24, 32])
            pixel_ratio = random.choice([1, 1.25, 1.5, 2])
            timezone_offset = random.choice([-480, -420, -360, -300, -240, -180, -120, 0, 60, 120])
            
            return f"""
            (function() {{
                'use strict';
                
                try {{
                    // Core webdriver removal - multiple methods
                    Object.defineProperty(navigator, 'webdriver', {{
                        get: () => undefined,
                        configurable: true
                    }});
                    
                    delete navigator.__proto__.webdriver;
                    delete navigator.webdriver;
                    
                    // Override webdriver property on prototype
                    if (navigator.__proto__) {{
                        delete navigator.__proto__.webdriver;
                    }}
                    
                    // Randomized screen properties
                    Object.defineProperty(screen, 'width', {{
                        get: () => {screen_width},
                        configurable: true
                    }});
                    Object.defineProperty(screen, 'height', {{
                        get: () => {screen_height},
                        configurable: true
                    }});
                    Object.defineProperty(screen, 'colorDepth', {{
                        get: () => {color_depth},
                        configurable: true
                    }});
                    Object.defineProperty(window, 'devicePixelRatio', {{
                        get: () => {pixel_ratio},
                        configurable: true
                    }});
                    
                    // Enhanced navigator properties
                    Object.defineProperty(navigator, 'plugins', {{
                        get: () => [
                            {{name: 'Chrome PDF Plugin', length: 2, description: 'Portable Document Format'}},
                            {{name: 'Chrome PDF Viewer', length: 1, description: 'PDF Viewer'}},
                            {{name: 'Native Client', length: 2, description: 'Native Client'}}
                        ],
                        configurable: true
                    }});
                    
                    Object.defineProperty(navigator, 'languages', {{
                        get: () => ['en-US', 'en'],
                        configurable: true
                    }});
                    
                    // Chrome runtime simulation
                    window.chrome = {{
                        runtime: {{
                            onConnect: null,
                            onMessage: null
                        }},
                        loadTimes: function() {{ return {{}}; }},
                        csi: function() {{ return {{}}; }}
                    }};
                    
                    // Permissions API override
                    if (navigator.permissions && navigator.permissions.query) {{
                        const originalQuery = navigator.permissions.query;
                        navigator.permissions.query = function(parameters) {{
                            if (parameters.name === 'notifications') {{
                                return Promise.resolve({{state: Notification.permission}});
                            }}
                            return originalQuery.apply(navigator.permissions, arguments);
                        }};
                    }}
                    
                    // Random timezone offset
                    const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
                    Date.prototype.getTimezoneOffset = function() {{
                        return {timezone_offset};
                    }};
                    
                    // Canvas fingerprinting protection with better randomization
                    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                    HTMLCanvasElement.prototype.toDataURL = function() {{
                        const context = this.getContext('2d');
                        if (context) {{
                            const imageData = context.getImageData(0, 0, 1, 1);
                            const data = imageData.data;
                            data[0] = {random.randint(0, 255)};  // Red
                            data[1] = {random.randint(0, 255)};  // Green  
                            data[2] = {random.randint(0, 255)};  // Blue
                            data[3] = {random.randint(230, 255)}; // Alpha
                            context.putImageData(imageData, 0, 0);
                        }}
                        return originalToDataURL.apply(this, arguments);
                    }};
                    
                    // WebRTC leak protection
                    Object.defineProperty(navigator, 'mediaDevices', {{
                        get: () => undefined,
                        configurable: true
                    }});
                    
                    // WebGL fingerprinting protection
                    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                        if (parameter === 37445) {{ // UNMASKED_VENDOR_WEBGL
                            return 'Google Inc. (Intel)';
                        }}
                        if (parameter === 37446) {{ // UNMASKED_RENDERER_WEBGL
                            return 'ANGLE (Intel, Intel(R) HD Graphics 630 (0x00005912) Direct3D11 vs_5_0 ps_5_0, D3D11)';
                        }}
                        return originalGetParameter.apply(this, arguments);
                    }};
                    
                    // AudioContext fingerprinting protection
                    if (window.AudioContext || window.webkitAudioContext) {{
                        const AudioContext = window.AudioContext || window.webkitAudioContext;
                        const originalCreateOscillator = AudioContext.prototype.createOscillator;
                        AudioContext.prototype.createOscillator = function() {{
                            const oscillator = originalCreateOscillator.apply(this, arguments);
                            const originalStart = oscillator.start;
                            oscillator.start = function() {{
                                // Add slight random variation to audio fingerprinting
                                this.frequency.value = this.frequency.value + Math.random() * 0.1;
                                return originalStart.apply(this, arguments);
                            }};
                            return oscillator;
                        }};
                    }}
                    
                    console.log('✅ Enhanced stealth measures applied successfully');
                    
                }} catch (error) {{
                    console.warn('⚠️ Some stealth measures failed:', error.message);
                }}
            }})();
            """
        
        stealth_js = get_enhanced_stealth_script()
        driver.execute_script(stealth_js)
        print("✅ Enhanced stealth injection successful")
        
        # Verify stealth is working
        try:
            webdriver_detected = driver.execute_script("return navigator.webdriver")
            if webdriver_detected is None:
                print("✅ WebDriver property successfully hidden")
            else:
                print(f"⚠️ WebDriver property still detected: {webdriver_detected}")
        except Exception as e:
            print(f"⚠️ Could not verify stealth status: {e}")
            
    except Exception as e:
        print(f"⚠️ Stealth injection warning: {e}")
        # Fallback basic stealth
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            print("✅ Fallback stealth applied")
        except:
            print("❌ All stealth measures failed")
    
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