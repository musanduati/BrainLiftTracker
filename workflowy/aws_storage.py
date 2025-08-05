# aws_storage.py - Updated with configuration management
import boto3
import json
from typing import Dict, List
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from logger_config import logger

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

        logger.info(f"Saving scraped content to S3 Bucket: {self.bucket_name}")
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
            ContentType='text/plain'
        )
        
        # Clean up old scraped content files (keep only files from last 31 days)
        self.cleanup_old_scraped_content(user_name)
        
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
        try:
            response = self.state_table.get_item(
                Key={'user_name': user_name}
            )
            item = response.get('Item', {})
            state = item.get('state', {"dok4": [], "dok3": []})
            
            # Ensure the state has the expected structure
            if not isinstance(state, dict):
                logger.warning(f"Warning: Invalid state format for {user_name}, resetting to default")
                return {"dok4": [], "dok3": []}
            
            # Ensure both keys exist
            if "dok4" not in state:
                state["dok4"] = []
            if "dok3" not in state:
                state["dok3"] = []
                
            return state
            
        except Exception as e:
            logger.error(f"Error loading state for {user_name}: {e}")
            return {"dok4": [], "dok3": []}
    
    def save_current_state(self, user_name: str, state: Dict):
        self.state_table.put_item(
            Item={
                'user_name': user_name,
                'state': state,
                'last_updated': datetime.now().isoformat(),
                'ttl': int(datetime.now().timestamp()) + (365 * 24 * 60 * 60)  # 1 year
            }
        )
    
    def is_first_run(self, user_name: str) -> bool:
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
            logger.error(f"Error loading Workflowy URLs from DynamoDB: {e}")
            logger.info("Falling back to empty list")
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
            logger.error(f"Error loading user account mapping from DynamoDB: {e}")
            logger.info("Falling back to empty mapping")
            return {}

    def cleanup_old_scraped_content(self, user_name: str, days_to_keep: int = 31):
        """
        Clean up old scraped content files, keeping only files from the last N days.
        
        Args:
            user_name: The user name to clean up files for
            days_to_keep: Number of days to keep files for (default: 31)
        """
        try:
            # Calculate the cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            # List all scraped content files for this user
            prefix = f"{user_name}/scraped_content/"
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                logger.info(f"📄 No existing scraped content files found for {user_name}")
                return
            
            # Filter to only scraped content files (exclude other files that might be in the directory)
            scraped_files = [
                obj for obj in response['Contents'] 
                if '_scraped_workflowy_' in obj['Key'] and obj['Key'].endswith('.txt')
            ]
            
            # Filter files older than cutoff date
            files_to_delete = [
                obj for obj in scraped_files 
                if obj['LastModified'] < cutoff_date
            ]
            
            if not files_to_delete:
                logger.info(f"📄 No scraped content files older than {days_to_keep} days found for {user_name}, no cleanup needed")
                return
            
            logger.info(f"🗑️  Cleaning up {len(files_to_delete)} scraped content files older than {days_to_keep} days for {user_name}")
            
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
                logger.error(f"❌ Some files could not be deleted: {response['Errors']}")
            else:
                logger.info(f"✅ Successfully cleaned up {len(files_to_delete)} old files for {user_name}")
                
            # Log which files were kept
            files_kept = [obj for obj in scraped_files if obj not in files_to_delete]
            files_kept.sort(key=lambda x: x['LastModified'], reverse=True)
            logger.info(f"📋 Kept {len(files_kept)} files newer than {days_to_keep} days:")
            for file_obj in files_kept:
                logger.info(f"   • {file_obj['Key']} (modified: {file_obj['LastModified']})")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up old scraped content for {user_name}: {e}")
            # Don't raise the error - cleanup failure shouldn't break the main flow
