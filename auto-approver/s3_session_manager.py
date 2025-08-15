#!/usr/bin/env python3
"""
S3-Based Session Manager for Twitter Automation
Handles session persistence across container restarts
"""

import json
import boto3
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError
from selenium.common.exceptions import WebDriverException

class S3SessionManager:
    """Manage Twitter sessions using S3 for containerized environments"""
    
    def __init__(self, bucket_name=None, sessions_prefix="twitter-sessions/"):
        """
        Initialize S3 session manager
        
        Args:
            bucket_name (str): S3 bucket name (defaults to env var)
            sessions_prefix (str): S3 key prefix for session files
        """
        import os
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME')
        self.sessions_prefix = sessions_prefix
        
        # Configurable session timeout - default to unlimited in controlled environments
        timeout_env = os.getenv('SESSION_TIMEOUT_HOURS', 'unlimited')
        if timeout_env.lower() in ['unlimited', 'none', '0']:
            self.session_timeout_hours = None  # Unlimited
            print(f"✅ S3 Session Manager initialized (bucket: {self.bucket_name}, timeout: unlimited)")
        else:
            try:
                self.session_timeout_hours = int(timeout_env)
                print(f"✅ S3 Session Manager initialized (bucket: {self.bucket_name}, timeout: {self.session_timeout_hours}h)")
            except ValueError:
                self.session_timeout_hours = 72  # Fallback
                print(f"⚠️ Invalid timeout value, using 72h default")
        
        try:
            self.s3_client = boto3.client('s3')
            self.s3_available = True
            print(f"✅ S3 Session Manager initialized (bucket: {self.bucket_name})")
        except (NoCredentialsError, Exception) as e:
            print(f"❌ S3 not available for session management: {str(e)}")
            self.s3_client = None
            self.s3_available = False
    
    def _get_session_key(self, username: str) -> str:
        """Get S3 key for username session"""
        clean_username = username.replace('@', '').replace('_', '-')
        return f"{self.sessions_prefix}{clean_username}.json"
    
    def _is_session_expired(self, session_data: Dict) -> bool:
        """Check if session has expired"""
        # In controlled environment, sessions don't expire automatically
        if self.session_timeout_hours is None:
            return False
        
        try:
            saved_time = datetime.fromisoformat(session_data.get('timestamp', ''))
            expiry_time = saved_time + timedelta(hours=self.session_timeout_hours)
            return datetime.now() > expiry_time
        except (ValueError, TypeError):
            return True  # If we can't parse, consider expired
    
    def save_session(self, username: str, driver) -> bool:
        """Save current session to S3"""
        if not self.s3_available or not self.bucket_name:
            print(f"   ⚠️ S3 not available, skipping session save for {username}")
            return False
        
        try:
            # Get all cookies
            cookies = driver.get_cookies()
            current_url = driver.current_url
            
            session_data = {
                'username': username,
                'timestamp': datetime.now().isoformat(),
                'cookies': cookies,
                'current_url': current_url,
                'user_agent': driver.execute_script("return navigator.userAgent;"),
                'session_storage': driver.execute_script("return JSON.stringify(sessionStorage);"),
                'local_storage': driver.execute_script("return JSON.stringify(localStorage);")
            }
            
            # Save to S3
            session_key = self._get_session_key(username)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=session_key,
                Body=json.dumps(session_data, indent=2),
                ContentType='application/json'
            )
            
            print(f"{username} - [INFO] ✅ Session saved to S3")
            return True
            
        except Exception as e:
            print(f"{username} - [ERROR] ❌ Failed to save session: {str(e)}")
            return False
    
    def load_session(self, username: str, driver) -> bool:
        """Load session from S3 and restore in browser"""
        if not self.s3_available or not self.bucket_name:
            return False
        
        try:
            session_key = self._get_session_key(username)
            
            # Download session from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=session_key
            )
            session_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Check if session is expired
            if self._is_session_expired(session_data):
                print(f"{username} - [INFO] ⏰ Session expired, will login normally")
                self.delete_session(username)  # Clean up expired session
                return False
            
            print(f"{username} - [INFO] 🔄 Loading saved session")
            
            # Navigate to Twitter first
            driver.get("https://x.com")
            time.sleep(2)
            
            # Restore cookies
            for cookie in session_data.get('cookies', []):
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"   ⚠️ Could not restore cookie: {str(e)}")
            
            # Restore storage
            try:
                session_storage = session_data.get('session_storage', '{}')
                local_storage = session_data.get('local_storage', '{}')
                
                driver.execute_script(f"""
                    try {{
                        const sessionData = {session_storage};
                        Object.keys(sessionData).forEach(key => {{
                            sessionStorage.setItem(key, sessionData[key]);
                        }});
                        
                        const localData = {local_storage};
                        Object.keys(localData).forEach(key => {{
                            localStorage.setItem(key, localData[key]);
                        }});
                    }} catch(e) {{
                        console.log('Could not restore storage:', e);
                    }}
                """)
            except Exception as e:
                print(f"   ⚠️ Could not restore storage: {str(e)}")
            
            # Navigate to the original URL or home page
            original_url = session_data.get('current_url', 'https://x.com/home')
            driver.get(original_url)
            time.sleep(3)
            
            # Verify session is valid by checking if we're logged in
            if self._verify_logged_in(driver):
                age_hours = (datetime.now() - datetime.fromisoformat(session_data['timestamp'])).total_seconds() / 3600
                print(f"{username} - [OK] Session restored successfully (age: {age_hours:.1f}h)")
                return True
            else:
                print(f"{username} - [ERROR] Session invalid, will login normally")
                self.delete_session(username)  # Clean up invalid session
                return False
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"{username} - [INFO] 📝 No saved session found")
            else:
                print(f"{username} - [ERROR] S3 error loading session: {str(e)}")
            return False
        except Exception as e:
            print(f"{username} - [ERROR] Error loading session: {str(e)}")
            return False
    
    def _verify_logged_in(self, driver) -> bool:
        """Verify that we're actually logged in"""
        try:
            # Check for elements that indicate we're logged in
            indicators = [
                "[data-testid='primaryColumn']",  # Home page main column
                "[data-testid='SideNav_AccountSwitcher_Button']",  # Account switcher
                "[data-testid='UserAvatar']"  # User avatar
            ]
            
            for indicator in indicators:
                elements = driver.find_elements("css selector", indicator)
                if elements and len(elements) > 0:
                    return True
            
            # Check URL patterns that indicate we're logged in
            current_url = driver.current_url.lower()
            if any(pattern in current_url for pattern in ['/home', '/notifications', '/explore']):
                return True
                
            return False
            
        except Exception:
            return False
    
    def delete_session(self, username: str) -> bool:
        """Delete session from S3"""
        if not self.s3_available or not self.bucket_name:
            return False
        
        try:
            session_key = self._get_session_key(username)
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=session_key
            )
            print(f"{username} - [INFO] 🗑️ Deleted session")
            return True
        except Exception as e:
            print(f"{username} - [ERROR] Could not delete session: {str(e)}")
            return False
    
    def list_sessions(self) -> List[str]:
        """List all saved sessions"""
        if not self.s3_available or not self.bucket_name:
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=self.sessions_prefix
            )
            
            sessions = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.json'):
                    username = key.replace(self.sessions_prefix, '').replace('.json', '')
                    sessions.append(username)
            
            return sessions
        except Exception as e:
            print(f"❌ Error listing sessions: {str(e)}")
            return []
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions from S3"""
        if not self.s3_available:
            return 0
        
        cleaned = 0
        sessions = self.list_sessions()
        
        for username in sessions:
            try:
                session_key = self._get_session_key(username)
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=session_key
                )
                session_data = json.loads(response['Body'].read().decode('utf-8'))
                
                if self._is_session_expired(session_data):
                    self.delete_session(username)
                    cleaned += 1
                    
            except Exception as e:
                print(f"{username} - [ERROR] Error checking session: {str(e)}")
        
        if cleaned > 0:
            print(f"🧹 Cleaned up {cleaned} expired sessions")
        
        return cleaned
