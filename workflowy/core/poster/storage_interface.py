"""
Storage interface methods for tweet posting
"""

from typing import List, Dict, Optional
from datetime import datetime
from workflowy.storage.aws_storage import AWSStorageV2
from workflowy.storage.project_utils import normalize_project_id
from workflowy.config.logger import structured_logger


class StorageInterface:
    """
    Handles all storage-related operations for tweet posting
    """
    
    def __init__(self, environment: str = 'test'):
        """Initialize storage interface."""
        self.storage = AWSStorageV2(environment)
        self.environment = environment
    
    def get_account_id_for_project(self, project_id: str) -> Optional[str]:
        """
        Get account ID for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            str: Account ID or None if not found
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            structured_logger.error_operation("get_account_id_for_project", f"❌ Invalid project_id format: {project_id}")
            return None
        
        account_id = self.storage.get_account_id_for_project(project_id)
        if not account_id:
            structured_logger.error_operation("get_account_id_for_project", f"❌ No account mapping found for project: {project_id}")
        
        return account_id
    
    def get_project_tweet_data(self, project_id: str) -> List[Dict]:
        """
        Load latest tweets for a project from S3.
        
        Args:
            project_id: Project identifier
            
        Returns:
            list: Tweet data for the project
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            structured_logger.error_operation("get_project_tweet_data", f"❌ Invalid project_id format: {project_id}")
            return []
        
        return self.storage.load_latest_tweets_from_s3(project_id)
    
    def save_updated_tweets_for_project(self, project_id: str, tweets: List[Dict]):
        """
        Save updated tweet data back to S3 after posting.
        
        Args:
            project_id: Project identifier
            tweets: Updated tweet data
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            structured_logger.error_operation("save_updated_tweets_for_project", f"❌ Invalid project_id format: {project_id}")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Save with updated status
            updated_url = self.storage.save_change_tweets(project_id, tweets, f"{timestamp}_updated")
            structured_logger.info_operation("save_updated_tweets_for_project", f"📄 Updated tweet statuses saved to S3: {updated_url}")
            
        except Exception as e:
            structured_logger.error_operation("save_updated_tweets_for_project", f"❌ Error saving updated tweets for project {project_id}: {e}")
    
    def get_all_projects(self) -> List[Dict]:
        """Get all projects from storage."""
        return self.storage.get_all_projects()
    
    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """Get project configuration by ID."""
        return self.storage.get_project_by_id(project_id)
