# aws_storage.py - Updated with configuration management
import boto3
import json
from typing import Dict, List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class AWSStorage:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        
        # Get from environment variables (set these manually in Lambda/EC2)
        self.bucket_name = os.environ.get('WORKFLOWY_BUCKET', 'workflowy-content-test')
        self.state_table_name = os.environ.get('STATE_TABLE', 'workflowy-state-table-test')
        self.state_table = self.dynamodb.Table(self.state_table_name)
        
        # Configuration tables
        self.urls_table_name = os.environ.get('URLS_CONFIG_TABLE', 'workflowy-urls-config-test')
        self.mapping_table_name = os.environ.get('USER_MAPPING_TABLE', 'workflowy-user-account-mapping-test')
        self.urls_table = self.dynamodb.Table(self.urls_table_name)
        self.mapping_table = self.dynamodb.Table(self.mapping_table_name)
    
    def save_scraped_content(self, user_name: str, content: str, timestamp: str) -> str:
        """Replace: user_dir / f"{user_name}_scraped_workflowy_{timestamp}.txt" """
        key = f"{user_name}/scraped_content/{user_name}_scraped_workflowy_{timestamp}.txt"

        print("Bucket name: ", self.bucket_name)
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
            ContentType='text/plain'
        )
        
        # Clean up old scraped content files (keep only latest 2)
        self.cleanup_old_scraped_content(user_name, max_files=2)
        
        return f"s3://{self.bucket_name}/{key}"
    
    def save_change_tweets(self, user_name: str, tweets: List[Dict], timestamp: str) -> str:
        """Replace: user_dir / f"{user_name}_change_tweets_{timestamp}.json" """
        key = f"{user_name}/change_tweets/{user_name}_change_tweets_{timestamp}.json"
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(tweets, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        return f"s3://{self.bucket_name}/{key}"
    
    def load_previous_state(self, user_name: str) -> Dict:
        """Replace: load_previous_state(user_dir) """
        try:
            response = self.state_table.get_item(
                Key={'user_name': user_name}
            )
            item = response.get('Item', {})
            state = item.get('state', {"dok4": [], "dok3": []})
            
            # Ensure the state has the expected structure
            if not isinstance(state, dict):
                print(f"Warning: Invalid state format for {user_name}, resetting to default")
                return {"dok4": [], "dok3": []}
            
            # Ensure both keys exist
            if "dok4" not in state:
                state["dok4"] = []
            if "dok3" not in state:
                state["dok3"] = []
                
            return state
            
        except Exception as e:
            print(f"Error loading state for {user_name}: {e}")
            return {"dok4": [], "dok3": []}
    
    def save_current_state(self, user_name: str, state: Dict):
        """Replace: save_current_state(user_dir, current_state) """
        self.state_table.put_item(
            Item={
                'user_name': user_name,
                'state': state,
                'last_updated': datetime.now().isoformat(),
                'ttl': int(datetime.now().timestamp()) + (365 * 24 * 60 * 60)  # 1 year
            }
        )
    
    def is_first_run(self, user_name: str) -> bool:
        """Replace: is_first_run() """
        try:
            response = self.state_table.get_item(
                Key={'user_name': user_name}
            )
            return 'Item' not in response
        except:
            return True

    # ============================================================================
    # Configuration Management Methods
    # ============================================================================
    
    def get_workflowy_urls(self) -> List[Dict]:
        """
        Get all active Workflowy URLs from DynamoDB.
        
        Returns:
            List of dicts with 'url' and 'name' keys
        """
        try:
            response = self.urls_table.scan(
                FilterExpression='active = :active',
                ExpressionAttributeValues={':active': True}
            )
            
            urls = []
            for item in response.get('Items', []):
                urls.append({
                    'url': item['url'],
                    'name': item['name']
                })
            
            return urls
            
        except Exception as e:
            print(f"Error loading Workflowy URLs from DynamoDB: {e}")
            print("Falling back to empty list")
            return []
    
    def get_user_account_mapping(self) -> Dict[str, int]:
        """
        Get user to account ID mapping from DynamoDB.
        
        Returns:
            Dict mapping user names to account IDs
        """
        try:
            response = self.mapping_table.scan(
                FilterExpression='active = :active',
                ExpressionAttributeValues={':active': True}
            )
            
            mapping = {}
            for item in response.get('Items', []):
                mapping[item['user_name']] = int(item['account_id'])
            
            return mapping
            
        except Exception as e:
            print(f"Error loading user account mapping from DynamoDB: {e}")
            print("Falling back to empty mapping")
            return {}
    
    def add_workflowy_url(self, url: str, name: str, active: bool = True) -> bool:
        """
        Add a new Workflowy URL configuration.
        
        Args:
            url: The Workflowy URL
            name: Friendly name for the URL
            active: Whether this URL should be processed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate URL ID from name
            url_id = name.lower().replace(' ', '_').replace('-', '_')
            
            self.urls_table.put_item(
                Item={
                    'url_id': url_id,
                    'url': url,
                    'name': name,
                    'active': active,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            )
            print(f"✅ Added Workflowy URL: {name} -> {url}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding Workflowy URL: {e}")
            return False
    
    def add_user_account_mapping(self, user_name: str, account_id: int, active: bool = True) -> bool:
        """
        Add a new user to account ID mapping.
        
        Args:
            user_name: The user name (should match Workflowy URL name)
            account_id: The Twitter account ID to use for posting
            active: Whether this mapping should be used
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.mapping_table.put_item(
                Item={
                    'user_name': user_name,
                    'account_id': account_id,
                    'active': active,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            )
            print(f"✅ Added user mapping: {user_name} -> Account {account_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding user mapping: {e}")
            return False
    
    def update_url_status(self, url_id: str, active: bool) -> bool:
        """Update the active status of a Workflowy URL."""
        try:
            self.urls_table.update_item(
                Key={'url_id': url_id},
                UpdateExpression='SET active = :active, updated_at = :updated',
                ExpressionAttributeValues={
                    ':active': active,
                    ':updated': datetime.now().isoformat()
                }
            )
            print(f"✅ Updated URL {url_id} active status to {active}")
            return True
        except Exception as e:
            print(f"❌ Error updating URL status: {e}")
            return False
    
    def update_user_mapping_status(self, user_name: str, active: bool) -> bool:
        """Update the active status of a user mapping."""
        try:
            self.mapping_table.update_item(
                Key={'user_name': user_name},
                UpdateExpression='SET active = :active, updated_at = :updated',
                ExpressionAttributeValues={
                    ':active': active,
                    ':updated': datetime.now().isoformat()
                }
            )
            print(f"✅ Updated user {user_name} mapping active status to {active}")
            return True
        except Exception as e:
            print(f"❌ Error updating user mapping status: {e}")
            return False

    def setup_initial_configuration(self):
        """
        Setup initial configuration data from existing constants.
        This is a one-time migration helper.
        """
        print("🔧 Setting up initial configuration in DynamoDB...")
        
        # Initial Workflowy URLs (from current WORKFLOWY_URLS constant)
        initial_urls = [
            {
                'url': 'https://workflowy.com/s/new-pk-2-reading-cou/bjSyw1MzswiIsciE',
                'name': 'new_pk_2_reading_course'
            }
        ]
        
        # Initial user mappings (from current USER_ACCOUNT_MAPPING constant)
        initial_mappings = {
            "new_pk_2_reading_course": 3,
        }
        
        # Add URLs
        for url_config in initial_urls:
            self.add_workflowy_url(url_config['url'], url_config['name'])
        
        # Add user mappings
        for user_name, account_id in initial_mappings.items():
            self.add_user_account_mapping(user_name, account_id)
        
        print("✅ Initial configuration setup complete!")

    def list_all_configurations(self):
        """List all current configurations for debugging."""
        print("\n📋 Current Workflowy URLs Configuration:")
        urls = self.get_workflowy_urls()
        for i, url_config in enumerate(urls, 1):
            print(f"  {i}. {url_config['name']}: {url_config['url']}")
        
        print(f"\n🔗 Current User Account Mappings:")
        mappings = self.get_user_account_mapping()
        for user_name, account_id in mappings.items():
            print(f"  • {user_name} -> Account {account_id}")
        
        if not urls and not mappings:
            print("  (No configurations found)")

    def cleanup_old_scraped_content(self, user_name: str, max_files: int = 2):
        """
        Clean up old scraped content files, keeping only the latest N files.
        
        Args:
            user_name: The user name to clean up files for
            max_files: Maximum number of files to keep (default: 3)
        """
        try:
            # List all scraped content files for this user
            prefix = f"{user_name}/scraped_content/"
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                print(f"📄 No existing scraped content files found for {user_name}")
                return
            
            # Filter to only scraped content files (exclude other files that might be in the directory)
            scraped_files = [
                obj for obj in response['Contents'] 
                if '_scraped_workflowy_' in obj['Key'] and obj['Key'].endswith('.txt')
            ]
            
            if len(scraped_files) <= max_files:
                print(f"📄 Only {len(scraped_files)} scraped content files found for {user_name}, no cleanup needed")
                return
            
            # Sort by last modified date (newest first)
            scraped_files.sort(key=lambda x: x['LastModified'], reverse=True)
            
            # Files to delete (everything beyond the max_files limit)
            files_to_delete = scraped_files[max_files:]
            
            if files_to_delete:
                print(f"🗑️  Cleaning up {len(files_to_delete)} old scraped content files for {user_name}")
                
                # Delete old files
                delete_keys = [{'Key': obj['Key']} for obj in files_to_delete]
                
                # S3 batch delete (more efficient than individual deletes)
                response = self.s3.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={
                        'Objects': delete_keys,
                        'Quiet': True  # Don't return info about successful deletes
                    }
                )
                
                # Check for any deletion errors
                if 'Errors' in response and response['Errors']:
                    print(f"❌ Some files could not be deleted: {response['Errors']}")
                else:
                    print(f"✅ Successfully cleaned up {len(files_to_delete)} old files for {user_name}")
                    
                # Log which files were kept
                kept_files = scraped_files[:max_files]
                print(f"📋 Kept latest {len(kept_files)} files:")
                for file_obj in kept_files:
                    print(f"   • {file_obj['Key']} (modified: {file_obj['LastModified']})")
            
        except Exception as e:
            print(f"❌ Error cleaning up old scraped content for {user_name}: {e}")
            # Don't raise the error - cleanup failure shouldn't break the main flow



