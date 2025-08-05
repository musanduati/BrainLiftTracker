import json
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from aws_storage import AWSStorage
from logger_config import logger


class BulkURLProcessor:
    """
    Handles bulk processing of Workflowy URLs for DynamoDB storage.
    Adds entries to both URLS_CONFIG_TABLE and USER_MAPPING_TABLE.
    """
    
    def __init__(self):
        self.storage = AWSStorage()
    
    def parse_workflowy_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse a Workflowy URL to extract name and share ID.
        
        Args:
            url: Workflowy URL like "https://workflowy.com/s/kathryn/j25MB2FgBH6ePEzI"
            
        Returns:
            tuple: (name, share_id) or (None, None) if parsing fails
        """
        try:
            # Pattern to match: https://workflowy.com/s/{name}/{share_id}
            # Also handle URLs with fragments like #/fc779bda7458
            pattern = r'https://workflowy\.com/s/([^/]+)/([^/#?]+)'
            match = re.match(pattern, url)
            
            if match:
                name = match.group(1)
                share_id = match.group(2)
                return name, share_id
            else:
                logger.error(f"❌ Could not parse Workflowy URL: {url}")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error parsing URL {url}: {e}")
            return None, None
    
    def add_workflowy_url_with_share_id(self, url: str, name: str, share_id: str) -> bool:
        """
        Add a Workflowy URL to DynamoDB using share_id as url_id.
        
        Args:
            url: Full Workflowy URL
            name: Extracted name from URL
            share_id: Extracted share ID from URL
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use share_id as url_id (as per user's requirement)
            self.storage.urls_table.put_item(
                Item={
                    'url_id': share_id,
                    'url': url,
                    'name': name,
                    'active': True,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            )
            logger.info(f"✅ Added Workflowy URL: {name} -> {url} (ID: {share_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding Workflowy URL to DynamoDB: {e}")
            return False
    
    def add_user_account_mapping(self, user_name: str, account_id: str) -> bool:
        """
        Add a user account mapping to DynamoDB.
        
        Args:
            user_name: The user name (extracted from URL)
            account_id: The account ID or "TBA" if not provided
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.storage.mapping_table.put_item(
                Item={
                    'user_name': user_name,
                    'account_id': account_id,
                    'active': True,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            )
            logger.info(f"✅ Added user mapping: {user_name} -> Account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding user mapping to DynamoDB: {e}")
            return False
    
    def process_bulk_urls(self, url_entries: List[Dict]) -> Dict:
        """
        Process a list of Workflowy URL entries and add them to DynamoDB.
        Adds entries to both URLS_CONFIG_TABLE and USER_MAPPING_TABLE.
        
        Args:
            url_entries: List of dictionaries containing 'brainlift' URLs and optional 'account_id'
            
        Returns:
            dict: Processing results with successful and failed entries
        """
        logger.info(f"📝 Processing {len(url_entries)} Workflowy URLs")
        
        successful_urls = []
        failed_urls = []
        successful_mappings = []
        failed_mappings = []
        
        for i, entry in enumerate(url_entries, 1):
            if not isinstance(entry, dict) or 'brainlift' not in entry:
                error_msg = f"Invalid entry format at index {i-1}: {entry}"
                logger.error(f"❌ {error_msg}")
                failed_urls.append({
                    'entry': entry,
                    'error': error_msg
                })
                continue
            
            url = entry['brainlift']
            account_id = entry.get('account_id', 'TBA')  # Default to 'TBA' if not provided
            
            logger.info(f"🔄 Processing URL {i}/{len(url_entries)}: {url}")
            logger.info(f"   Account ID: {account_id}")
            
            # Parse the URL
            name, share_id = self.parse_workflowy_url(url)
            
            if not name or not share_id:
                error_msg = f"Could not parse URL: {url}"
                logger.error(f"❌ {error_msg}")
                failed_urls.append({
                    'url': url,
                    'account_id': account_id,
                    'error': error_msg
                })
                failed_mappings.append({
                    'url': url,
                    'account_id': account_id,
                    'error': error_msg
                })
                continue
            
            # Add to URLS_CONFIG_TABLE using the share_id as url_id
            url_success = self.add_workflowy_url_with_share_id(url, name, share_id)
            
            # Add to USER_MAPPING_TABLE using the name as user_name
            mapping_success = self.add_user_account_mapping(name, account_id)
            
            # Track results for URL config
            if url_success:
                successful_urls.append({
                    'url': url,
                    'name': name,
                    'url_id': share_id,
                    'account_id': account_id
                })
                logger.info(f"✅ Added URL config: {name} (ID: {share_id})")
            else:
                error_msg = f"Failed to add URL config to DynamoDB: {url}"
                logger.error(f"❌ {error_msg}")
                failed_urls.append({
                    'url': url,
                    'name': name,
                    'url_id': share_id,
                    'account_id': account_id,
                    'error': error_msg
                })
            
            # Track results for user mapping
            if mapping_success:
                successful_mappings.append({
                    'user_name': name,
                    'account_id': account_id,
                    'url': url
                })
                logger.info(f"✅ Added user mapping: {name} -> Account {account_id}")
            else:
                error_msg = f"Failed to add user mapping to DynamoDB: {name}"
                logger.error(f"❌ {error_msg}")
                failed_mappings.append({
                    'user_name': name,
                    'account_id': account_id,
                    'url': url,
                    'error': error_msg
                })
        
        # Prepare results summary
        results = {
            'operation': 'bulk_url_processing',
            'total_processed': len(url_entries),
            'url_config': {
                'successful': len(successful_urls),
                'failed': len(failed_urls),
                'successful_urls': successful_urls,
                'failed_urls': failed_urls
            },
            'user_mapping': {
                'successful': len(successful_mappings),
                'failed': len(failed_mappings),
                'successful_mappings': successful_mappings,
                'failed_mappings': failed_mappings
            }
        }
        
        logger.info(f"📊 Bulk URL processing complete:")
        logger.info(f"   ✅ URL Config - Successful: {len(successful_urls)}, Failed: {len(failed_urls)}")
        logger.info(f"   ✅ User Mapping - Successful: {len(successful_mappings)}, Failed: {len(failed_mappings)}")
        
        return results


def is_bulk_url_request(event: Dict) -> bool:
    """
    Check if this is a bulk URL processing request.
    
    Args:
        event: Lambda event object
        
    Returns:
        bool: True if this is a bulk URL request, False otherwise
    """
    try:
        # Check if event has a body
        if 'body' not in event:
            return False
        
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)
        
        # Check if body is a list and contains brainlift URLs
        if isinstance(body, list) and len(body) > 0:
            first_item = body[0]
            if isinstance(first_item, dict) and 'brainlift' in first_item:
                return True
        
        return False
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.debug(f"Not a bulk URL request: {e}")
        return False


def handle_bulk_url_processing(event: Dict) -> Dict:
    """
    Handle bulk URL processing request.
    
    Args:
        event: Lambda event containing the bulk URL data
        
    Returns:
        dict: Response with processing results
    """
    try:
        # Parse the body
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)
        
        # Create processor and process URLs
        processor = BulkURLProcessor()
        results = processor.process_bulk_urls(body)
        
        return {
            'statusCode': 200,
            'body': json.dumps(results, default=str)
        }
        
    except Exception as e:
        error_msg = f"Error processing bulk URLs: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'operation': 'bulk_url_processing'
            })
        }
