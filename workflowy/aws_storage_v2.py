# aws_storage_v2.py - Project-based AWS Storage (replaces aws_storage.py)
import boto3
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from logger_config import logger
from project_id_utils import normalize_project_id
from schema_definitions import validate_project_item, validate_state_item, get_table_names

load_dotenv()

class AWSStorageV2:
    """
    Updated AWS Storage class using project-based identification.
    Eliminates dependency on URL-derived user names.
    """
    
    def __init__(self, environment: str = 'test'):
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.environment = environment
        
        # Get from environment variables
        self.bucket_name = os.environ.get('WORKFLOWY_BUCKET', 'workflowy-content-test')
        
        # Get table names for current environment
        table_names = get_table_names(environment)
        
        # New project-based tables
        self.urls_config_table_name = os.environ.get('URLS_CONFIG_TABLE_V2', table_names['urls_config'])
        self.state_table_name = os.environ.get('STATE_TABLE_V2', table_names['state'])
        
        # Initialize table connections
        self.urls_config_table = self.dynamodb.Table(self.urls_config_table_name)
        self.state_table = self.dynamodb.Table(self.state_table_name)
        
        # Legacy table connections (for migration)
        self.legacy_urls_table_name = os.environ.get('URLS_CONFIG_TABLE', table_names['legacy_urls_config'])
        self.legacy_mapping_table_name = os.environ.get('USER_MAPPING_TABLE', table_names['legacy_user_mapping'])
        self.legacy_state_table_name = os.environ.get('STATE_TABLE', table_names['legacy_state'])
        
        # Only connect to legacy tables if they exist (for migration)
        try:
            self.legacy_urls_table = self.dynamodb.Table(self.legacy_urls_table_name)
            self.legacy_mapping_table = self.dynamodb.Table(self.legacy_mapping_table_name)
            self.legacy_state_table = self.dynamodb.Table(self.legacy_state_table_name)
        except Exception as e:
            logger.warning(f"Legacy tables not available: {e}")
            self.legacy_urls_table = None
            self.legacy_mapping_table = None
            self.legacy_state_table = None

    # ============================================================================
    # Project Management Methods
    # ============================================================================
    
    def create_project(self, url: str, account_id: str, name: Optional[str] = None) -> str:
        """
        Create a new project with generated project_id.
        
        Args:
            url: Workflowy URL
            account_id: Twitter account ID
            name: Optional display name
            
        Returns:
            str: Generated project_id
        """
        from project_id_utils import create_project_config
        
        project_config = create_project_config(url, account_id, name)
        project_id = project_config['project_id']
        logger.info(f"Project Config: {project_config}")
        
        # Validate before saving
        if not validate_project_item(project_config):
            raise ValueError(f"Invalid project configuration: {project_config}")
        
        try:
            self.urls_config_table.put_item(Item=project_config)
            logger.info(f"✅ Created project: {project_id} -> {name} (Account: {account_id})")
            return project_id
            
        except Exception as e:
            logger.error(f"❌ Error creating project: {e}")
            raise

    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """
        Get project configuration by project_id.
        
        Args:
            project_id: Project identifier
            
        Returns:
            dict: Project configuration or None if not found
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return None
        
        try:
            response = self.urls_config_table.get_item(
                Key={'project_id': project_id}
            )
            return response.get('Item')
            
        except Exception as e:
            logger.error(f"Error getting project {project_id}: {e}")
            return None

    def get_all_projects(self) -> List[Dict]:
        """
        Get all active projects.
        
        Returns:
            list: List of active project configurations
        """
        try:
            response = self.urls_config_table.scan(
                FilterExpression='active = :active',
                ExpressionAttributeValues={':active': True}
            )
            
            projects = response.get('Items', [])
            logger.info(f"📋 Found {len(projects)} active projects")
            
            for project in projects:
                logger.debug(f"  • {project['name']} ({project['project_id']}): {project['url']}")
            
            return projects
            
        except Exception as e:
            logger.error(f"Error loading projects: {e}")
            return []

    def get_account_id_for_project(self, project_id: str) -> Optional[str]:
        """
        Get Twitter account ID for a specific project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            str: Account ID or None if not found
        """
        project = self.get_project_by_id(project_id)
        return project.get('account_id') if project else None

    def update_project_url(self, project_id: str, new_url: str) -> bool:
        """
        Update URL for an existing project (when share_id changes).
        
        Args:
            project_id: Project identifier
            new_url: New Workflowy URL
            
        Returns:
            bool: True if updated successfully
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return False
        
        try:
            self.urls_config_table.update_item(
                Key={'project_id': project_id},
                UpdateExpression='SET #url = :url, updated_at = :updated_at',
                ExpressionAttributeNames={'#url': 'url'},
                ExpressionAttributeValues={
                    ':url': new_url,
                    ':updated_at': datetime.now().isoformat()
                }
            )
            logger.info(f"✅ Updated URL for project {project_id}: {new_url}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating project URL: {e}")
            return False

    def deactivate_project(self, project_id: str) -> bool:
        """
        Deactivate a project (mark as inactive).
        
        Args:
            project_id: Project identifier
            
        Returns:
            bool: True if deactivated successfully
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return False
        
        try:
            self.urls_config_table.update_item(
                Key={'project_id': project_id},
                UpdateExpression='SET active = :active, updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':active': False,
                    ':updated_at': datetime.now().isoformat()
                }
            )
            logger.info(f"✅ Deactivated project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deactivating project: {e}")
            return False

    # ============================================================================
    # Content Storage Methods (Updated for project_id)
    # ============================================================================
    
    def save_scraped_content(self, project_id: str, content: str, timestamp: str) -> str:
        """
        Save scraped content using project_id instead of user_name.
        
        Args:
            project_id: Project identifier
            content: Scraped content
            timestamp: Timestamp string
            
        Returns:
            str: S3 URL of saved content
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            raise ValueError(f"Invalid project_id format: {project_id}")
        
        key = f"{project_id}/scraped_content/{project_id}_scraped_workflowy_{timestamp}.txt"

        logger.info(f"Saving scraped content to S3 Bucket: {self.bucket_name}")
        logger.debug(f"Key: {key}")
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
            ContentType='text/plain'
        )
        
        # Clean up old scraped content files (keep only files from last 31 days)
        self.cleanup_old_scraped_content(project_id)
        
        return f"s3://{self.bucket_name}/{key}"
    
    def save_change_tweets(self, project_id: str, tweets: List[Dict], timestamp: str) -> str:
        """
        Save change tweets using project_id instead of user_name.
        
        Args:
            project_id: Project identifier
            tweets: List of tweet dictionaries
            timestamp: Timestamp string
            
        Returns:
            str: S3 URL of saved tweets
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            raise ValueError(f"Invalid project_id format: {project_id}")
        
        key = f"{project_id}/change_tweets/{project_id}_change_tweets_{timestamp}.json"
        
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(tweets, indent=2, ensure_ascii=False),
            ContentType='application/json'
        )
        
        logger.info(f"📄 Saved {len(tweets)} tweets to S3: {key}")
        return f"s3://{self.bucket_name}/{key}"

    def load_latest_tweets_from_s3(self, project_id: str) -> List[Dict]:
        """
        Load latest tweets from S3 for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            list: Latest tweets data
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return []
        
        try:
            # List objects in S3 to find latest file
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{project_id}/change_tweets/",
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                logger.info(f"📄 No tweet files found in S3 for project {project_id}")
                return []
            
            # Sort by last modified and get latest
            latest_object = max(response['Contents'], key=lambda x: x['LastModified'])
            
            # Get the latest tweets file
            obj = self.s3.get_object(
                Bucket=self.bucket_name,
                Key=latest_object['Key']
            )
            
            tweets_data = json.loads(obj['Body'].read())
            logger.info(f"📄 Loaded {len(tweets_data)} tweets from S3: {latest_object['Key']}")
            return tweets_data
            
        except Exception as e:
            logger.error(f"❌ Error loading tweets from S3 for project {project_id}: {e}")
            return []

    # ============================================================================
    # State Management Methods (Updated for project_id)
    # ============================================================================
    
    def load_previous_state(self, project_id: str) -> Dict:
        """
        Load previous state using project_id instead of user_name.
        
        Args:
            project_id: Project identifier
            
        Returns:
            dict: Previous state or default state
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return {"dok4": [], "dok3": []}
        
        try:
            response = self.state_table.get_item(
                Key={'project_id': project_id}
            )
            item = response.get('Item', {})
            state = item.get('state', {"dok4": [], "dok3": []})
            
            # Ensure the state has the expected structure
            if not isinstance(state, dict):
                logger.warning(f"Warning: Invalid state format for {project_id}, resetting to default")
                return {"dok4": [], "dok3": []}
            
            # Ensure both keys exist
            if "dok4" not in state:
                state["dok4"] = []
            if "dok3" not in state:
                state["dok3"] = []
                
            logger.debug(f"Loaded state for project {project_id}: {len(state.get('dok4', []))} DOK4, {len(state.get('dok3', []))} DOK3")
            return state
            
        except Exception as e:
            logger.error(f"Error loading state for project {project_id}: {e}")
            return {"dok4": [], "dok3": []}
    
    def save_current_state(self, project_id: str, state: Dict):
        """
        Save current state using project_id instead of user_name.
        
        Args:
            project_id: Project identifier
            state: State dictionary to save
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return
        
        state_item = {
            'project_id': project_id,
            'state': state,
            'last_updated': datetime.now().isoformat(),
            'ttl': int(datetime.now().timestamp()) + (365 * 24 * 60 * 60)  # 1 year
        }
        
        # Validate before saving
        if not validate_state_item(state_item):
            logger.error(f"Invalid state item for project {project_id}")
            return
        
        try:
            self.state_table.put_item(Item=state_item)
            logger.debug(f"Saved state for project {project_id}")
        except Exception as e:
            logger.error(f"Error saving state for project {project_id}: {e}")
    
    def is_first_run(self, project_id: str) -> bool:
        """
        Check if this is the first run for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            bool: True if first run, False otherwise
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return True
        
        try:
            response = self.state_table.get_item(
                Key={'project_id': project_id}
            )
            return 'Item' not in response
        except:
            return True

    # ============================================================================
    # Cleanup and Maintenance Methods
    # ============================================================================

    def cleanup_old_scraped_content(self, project_id: str, days_to_keep: int = 31):
        """
        Clean up old scraped content files for a project.
        
        Args:
            project_id: Project identifier
            days_to_keep: Number of days to keep files for (default: 31)
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return
        
        try:
            # Calculate the cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            # List all scraped content files for this project
            prefix = f"{project_id}/scraped_content/"
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=1000
            )
            
            if 'Contents' not in response:
                logger.info(f"📄 No existing scraped content files found for project {project_id}")
                return
            
            # Filter to only scraped content files
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
                logger.info(f"📄 No scraped content files older than {days_to_keep} days found for project {project_id}")
                return
            
            logger.info(f"🗑️  Cleaning up {len(files_to_delete)} scraped content files older than {days_to_keep} days for project {project_id}")
            
            # Delete old files
            delete_keys = [{'Key': obj['Key']} for obj in files_to_delete]
            
            # S3 batch delete
            response = self.s3.delete_objects(
                Bucket=self.bucket_name,
                Delete={
                    'Objects': delete_keys,
                    'Quiet': True
                }
            )
            
            # Check for any deletion errors
            if 'Errors' in response and response['Errors']:
                logger.error(f"❌ Some files could not be deleted: {response['Errors']}")
            else:
                logger.info(f"✅ Successfully cleaned up {len(files_to_delete)} old files for project {project_id}")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up old scraped content for project {project_id}: {e}")

    def get_project_storage_info(self, project_id: str) -> Dict:
        """
        Get storage information for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            dict: Storage information
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            logger.error(f"Invalid project_id format: {project_id}")
            return {}
        
        try:
            info = {
                'project_id': project_id,
                'scraped_content_files': 0,
                'change_tweet_files': 0,
                'total_files': 0,
                'total_size_mb': 0
            }
            
            # Check scraped content
            scraped_response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{project_id}/scraped_content/",
                MaxKeys=1000
            )
            
            if 'Contents' in scraped_response:
                info['scraped_content_files'] = len(scraped_response['Contents'])
                info['total_size_mb'] += sum(obj['Size'] for obj in scraped_response['Contents']) / (1024 * 1024)
            
            # Check change tweets
            tweets_response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{project_id}/change_tweets/",
                MaxKeys=1000
            )
            
            if 'Contents' in tweets_response:
                info['change_tweet_files'] = len(tweets_response['Contents'])
                info['total_size_mb'] += sum(obj['Size'] for obj in tweets_response['Contents']) / (1024 * 1024)
            
            info['total_files'] = info['scraped_content_files'] + info['change_tweet_files']
            
            logger.info(f"📊 Storage info for project {project_id}: {info['total_files']} files, {info['total_size_mb']:.2f} MB")
            return info
            
        except Exception as e:
            logger.error(f"❌ Error getting storage info for project {project_id}: {e}")
            return {}

    # ============================================================================
    # Migration Support Methods
    # ============================================================================

    def get_projects_for_migration(self) -> List[Dict]:
        """
        Get all projects that need data migration from legacy format.
        
        Returns:
            list: Projects that need migration
        """
        projects = self.get_all_projects()
        migration_needed = []
        
        for project in projects:
            project_id = project['project_id']
            
            # Check if project has any legacy data paths
            has_legacy_data = self._check_legacy_data_exists(project_id)
            
            if has_legacy_data:
                migration_needed.append(project)
        
        logger.info(f"📋 Found {len(migration_needed)} projects needing data migration")
        return migration_needed

    def _check_legacy_data_exists(self, project_id: str) -> bool:
        """
        Check if legacy data exists for a project (for migration).
        
        Args:
            project_id: Project identifier
            
        Returns:
            bool: True if legacy data exists
        """
        # This would check for old user_name-based paths
        # Implementation depends on migration strategy
        return False


if __name__ == "__main__":
    # Test the new storage system
    logger.info("Testing AWS Storage V2 (Project-based)")
    
    # Initialize storage
    storage = AWSStorageV2(environment='test')
    
    # Test project creation
    project_id = storage.create_project(
        url="https://workflowy.com/s/test/abc123",
        account_id="123",
        name="Test Project"
    )
    
    logger.info(f"Created test project: {project_id}")
    
    # Test project retrieval
    project = storage.get_project_by_id(project_id)
    logger.info(f"Retrieved project: {project}")
    
    # Test getting all projects
    all_projects = storage.get_all_projects()
    logger.info(f"All projects: {len(all_projects)}")
