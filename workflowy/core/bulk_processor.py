"""
Bulk URL Processor V2 - Project-based URL Processing
Handles bulk processing of Workflowy URLs using project-based identification.
Eliminates dependency on URL-derived parameters for identification.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional
from workflowy.storage.aws_storage import AWSStorageV2
from workflowy.storage.project_utils import is_valid_project_id
from workflowy.config.logger import logger


class BulkURLProcessorV2:
    """
    Updated bulk URL processor using project-based identification.
    Creates projects with internally generated IDs, eliminating URL dependency.
    """
    
    def __init__(self, environment: str = 'test'):
        self.storage = AWSStorageV2(environment)
        self.environment = environment
    
    def validate_workflowy_url(self, url: str) -> bool:
        """
        Validate that a URL is a valid Workflowy shared URL.
        This is the ONLY URL parsing we do - for validation, not identification.
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if valid Workflowy URL, False otherwise
        """
        try:
            if not isinstance(url, str):
                return False
            
            # Basic validation: must be a Workflowy shared URL
            if not url.startswith('https://workflowy.com/s/'):
                logger.error(f"❌ Invalid URL format: {url}")
                return False
            
            # Pattern to match: https://workflowy.com/s/{something}/{something}
            # We don't care about the content, just that it's properly formatted
            import re
            pattern = r'https://workflowy\.com/s/[^/]+/[^/#?]+'
            if not re.match(pattern, url):
                logger.error(f"❌ Invalid Workflowy URL structure: {url}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating URL {url}: {e}")
            return False
    
    def create_project_from_url(self, url: str, account_id: str, name: Optional[str] = None) -> Optional[str]:
        """
        Create a new project from a Workflowy URL.
        
        Args:
            url: Workflowy URL
            account_id: Twitter account ID
            name: Optional display name
            
        Returns:
            str: Generated project_id if successful, None if failed
        """
        # Validate URL format
        if not self.validate_workflowy_url(url):
            logger.error(f"❌ Invalid URL format: {url}")
            return None
        
        # Generate display name if not provided
        if not name:
            # Extract a basic name from URL for display (but not for identification!)
            try:
                url_parts = url.split('/')
                if len(url_parts) >= 5:
                    url_name = url_parts[4]  # The name part from URL
                    name = f"Project {url_name}"
                else:
                    name = "Workflowy Project"
            except:
                name = "Workflowy Project"
        
        try:
            project_id = self.storage.create_project(url, account_id, name)
            logger.info(f"✅ Created project: {project_id} -> {name} (Account: {account_id})")
            return project_id
            
        except Exception as e:
            logger.error(f"❌ Error creating project from URL {url}: {e}")
            return None
    
    def update_project_url(self, project_id: str, new_url: str) -> bool:
        """
        Update URL for an existing project (when share_id changes).
        
        Args:
            project_id: Project identifier
            new_url: New Workflowy URL
            
        Returns:
            bool: True if updated successfully
        """
        # Validate new URL
        if not self.validate_workflowy_url(new_url):
            logger.error(f"❌ Invalid new URL format: {new_url}")
            return False
        
        # Validate project_id
        if not is_valid_project_id(project_id):
            logger.error(f"❌ Invalid project_id format: {project_id}")
            return False
        
        return self.storage.update_project_url(project_id, new_url)
    
    def process_bulk_urls(self, url_entries: List[Dict]) -> Dict:
        """
        Process a list of Workflowy URL entries and create projects.
        Each entry creates a new project with generated project_id.
        
        Args:
            url_entries: List of dictionaries containing 'brainlift' URLs and 'account_id'
            
        Returns:
            dict: Processing results with successful and failed entries
        """
        logger.info(f"📝 Processing {len(url_entries)} Workflowy URLs for project creation")
        
        successful_projects = []
        failed_projects = []
        
        for i, entry in enumerate(url_entries, 1):
            # Validate entry format
            if not isinstance(entry, dict) or 'brainlift' not in entry:
                error_msg = f"Invalid entry format at index {i-1}: {entry}"
                logger.error(f"❌ {error_msg}")
                failed_projects.append({
                    'entry': entry,
                    'error': error_msg,
                    'index': i-1
                })
                continue
            
            url = entry['brainlift']
            account_id = entry.get('account_id', 'TBA')  # Default to 'TBA' if not provided
            name = entry.get('name')  # Optional name field
            
            logger.info(f"🔄 Processing URL {i}/{len(url_entries)}: {url}")
            logger.info(f"   Account ID: {account_id}")
            logger.info(f"   Name: {name}")
            
            # Create project (this generates a unique project_id internally)
            project_id = self.create_project_from_url(url, account_id, name)
            
            if project_id:
                successful_projects.append({
                    'project_id': project_id,
                    'url': url,
                    'name': name,
                    'account_id': account_id,
                    'index': i-1
                })
                logger.info(f"✅ Created project {project_id} for URL {i}")
            else:
                error_msg = f"Failed to create project for URL: {url}"
                logger.error(f"❌ {error_msg}")
                failed_projects.append({
                    'url': url,
                    'account_id': account_id,
                    'name': name,
                    'error': error_msg,
                    'index': i-1
                })
        
        # Prepare results summary
        results = {
            'operation': 'bulk_project_creation',
            'total_processed': len(url_entries),
            'successful': len(successful_projects),
            'failed': len(failed_projects),
            'successful_projects': successful_projects,
            'failed_projects': failed_projects,
            'environment': self.environment,
            'processed_at': datetime.now().isoformat()
        }
        
        logger.info(f"📊 Bulk URL processing complete:")
        logger.info(f"   ✅ Successful: {len(successful_projects)}")
        logger.info(f"   ❌ Failed: {len(failed_projects)}")
        
        return results
    
    def get_project_by_url(self, url: str) -> Optional[Dict]:
        """
        Find a project by its URL (useful for URL updates).
        
        Args:
            url: Workflowy URL to search for
            
        Returns:
            dict: Project configuration if found, None otherwise
        """
        try:
            # Get all projects and search for matching URL
            projects = self.storage.get_all_projects()
            
            for project in projects:
                if project.get('url') == url:
                    logger.info(f"Found project {project['project_id']} for URL: {url}")
                    return project
            
            logger.info(f"No project found for URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error searching for project by URL {url}: {e}")
            return None
    
    def get_project_statistics(self) -> Dict:
        """
        Get statistics about all projects.
        
        Returns:
            dict: Project statistics
        """
        try:
            projects = self.storage.get_all_projects()
            
            stats = {
                'total_projects': len(projects),
                'active_projects': len([p for p in projects if p.get('active', False)]),
                'inactive_projects': len([p for p in projects if not p.get('active', True)]),
                'projects_by_account': {},
                'urls_by_domain': {},
                'created_today': 0,
                'created_this_week': 0,
                'created_this_month': 0
            }
            
            # Count projects by account
            for project in projects:
                account_id = project.get('account_id', 'unknown')
                stats['projects_by_account'][account_id] = stats['projects_by_account'].get(account_id, 0) + 1
            
            # Count URLs by domain (should all be workflowy.com)
            for project in projects:
                url = project.get('url', '')
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    stats['urls_by_domain'][domain] = stats['urls_by_domain'].get(domain, 0) + 1
                except:
                    stats['urls_by_domain']['unknown'] = stats['urls_by_domain'].get('unknown', 0) + 1
            
            # Count recent projects
            from datetime import datetime, timedelta
            now = datetime.now()
            today = now.date()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            for project in projects:
                created_at_str = project.get('created_at', '')
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    created_date = created_at.date()
                    
                    if created_date == today:
                        stats['created_today'] += 1
                    if created_at >= week_ago:
                        stats['created_this_week'] += 1
                    if created_at >= month_ago:
                        stats['created_this_month'] += 1
                except:
                    pass  # Skip invalid dates
            
            logger.info(f"📊 Project statistics: {stats['total_projects']} total, {stats['active_projects']} active")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting project statistics: {e}")
            return {}
    
    def validate_bulk_url_format(self, url_entries: List[Dict]) -> Dict:
        """
        Validate the format of bulk URL entries without processing them.
        
        Args:
            url_entries: List of URL entries to validate
            
        Returns:
            dict: Validation results
        """
        validation = {
            'total_entries': len(url_entries),
            'valid_entries': 0,
            'invalid_entries': 0,
            'validation_errors': [],
            'valid_urls': [],
            'invalid_urls': []
        }
        
        for i, entry in enumerate(url_entries):
            entry_valid = True
            errors = []
            
            # Check entry structure
            if not isinstance(entry, dict):
                errors.append(f"Entry {i}: Not a dictionary")
                entry_valid = False
            else:
                # Check required fields
                if 'brainlift' not in entry:
                    errors.append(f"Entry {i}: Missing 'brainlift' field")
                    entry_valid = False
                else:
                    url = entry['brainlift']
                    # Validate URL format
                    if not self.validate_workflowy_url(url):
                        errors.append(f"Entry {i}: Invalid Workflowy URL format")
                        entry_valid = False
                    else:
                        validation['valid_urls'].append(url)
                
                # Check account_id if provided
                if 'account_id' in entry:
                    account_id = entry['account_id']
                    if not isinstance(account_id, (str, int)):
                        errors.append(f"Entry {i}: Invalid account_id type")
                        entry_valid = False
                
                # Check name if provided
                if 'name' in entry:
                    name = entry['name']
                    if not isinstance(name, str):
                        errors.append(f"Entry {i}: Invalid name type")
                        entry_valid = False
            
            if entry_valid:
                validation['valid_entries'] += 1
            else:
                validation['invalid_entries'] += 1
                validation['validation_errors'].extend(errors)
                if isinstance(entry, dict) and 'brainlift' in entry:
                    validation['invalid_urls'].append(entry['brainlift'])
        
        logger.info(f"📋 Validation complete: {validation['valid_entries']} valid, {validation['invalid_entries']} invalid")
        return validation


# ============================================================================
# Lambda Integration Functions
# ============================================================================

def is_bulk_url_request_v2(event: Dict) -> bool:
    """
    Check if this is a bulk URL processing request (updated for v2).
    
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


def handle_bulk_url_processing_v2(event: Dict, environment: str = 'test') -> Dict:
    """
    Handle bulk URL processing request (updated for v2).
    
    Args:
        event: Lambda event containing the bulk URL data
        environment: Environment to process in
        
    Returns:
        dict: Response with processing results
    """
    try:
        # Parse the body
        body = event['body']
        if isinstance(body, str):
            body = json.loads(body)
        
        # Validate format first
        processor = BulkURLProcessorV2(environment)
        validation = processor.validate_bulk_url_format(body)
        
        if validation['invalid_entries'] > 0:
            logger.warning(f"⚠️ Found {validation['invalid_entries']} invalid entries")
            logger.warning(f"Validation errors: {validation['validation_errors']}")
        
        # Process URLs (even if some are invalid, process the valid ones)
        if validation['valid_entries'] > 0:
            results = processor.process_bulk_urls(body)
            results['validation'] = validation
        else:
            results = {
                'operation': 'bulk_project_creation',
                'total_processed': len(body),
                'successful': 0,
                'failed': len(body),
                'successful_projects': [],
                'failed_projects': [{'error': 'No valid entries found', 'entries': body}],
                'validation': validation,
                'environment': environment
            }
        
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
                'operation': 'bulk_project_creation',
                'environment': environment
            })
        }


# ============================================================================
# Project Management Functions
# ============================================================================

def create_project_management_api():
    """
    Create project management API endpoints.
    
    Returns:
        dict: API endpoint definitions
    """
    return {
        'endpoints': {
            'POST /projects': {
                'description': 'Create a new project',
                'payload': {
                    'url': 'string (required) - Workflowy URL',
                    'account_id': 'string (required) - Twitter account ID',
                    'name': 'string (optional) - Display name'
                },
                'response': {
                    'project_id': 'string - Generated project ID',
                    'status': 'string - success/error'
                }
            },
            'GET /projects': {
                'description': 'List all active projects',
                'response': {
                    'projects': 'array - List of project objects',
                    'count': 'number - Total count'
                }
            },
            'GET /projects/{project_id}': {
                'description': 'Get specific project',
                'response': {
                    'project': 'object - Project details'
                }
            },
            'PUT /projects/{project_id}/url': {
                'description': 'Update project URL',
                'payload': {
                    'url': 'string (required) - New Workflowy URL'
                }
            },
            'DELETE /projects/{project_id}': {
                'description': 'Deactivate project',
                'response': {
                    'status': 'string - success/error'
                }
            },
            'POST /projects/bulk': {
                'description': 'Create multiple projects',
                'payload': [
                    {
                        'brainlift': 'string - Workflowy URL',
                        'account_id': 'string - Twitter account ID',
                        'name': 'string (optional) - Display name'
                    }
                ]
            },
            'GET /projects/stats': {
                'description': 'Get project statistics',
                'response': {
                    'total_projects': 'number',
                    'active_projects': 'number',
                    'projects_by_account': 'object'
                }
            }
        }
    }


if __name__ == "__main__":
    # Test the new bulk URL processor
    logger.info("Testing Bulk URL Processor V2 (Project-based)")
    
    # Initialize processor
    processor = BulkURLProcessorV2(environment='test')
    
    # Test data
    test_urls = [
        {
            "brainlift": "https://workflowy.com/s/wfx-test-sanket/Wrd3ZR9KgH1sGIh8",
            "account_id": "3",
            "name": "wfx-test-sanket"
        }
    ]
    
    # Test validation
    validation = processor.validate_bulk_url_format(test_urls)
    logger.info(f"Validation result: {validation}")
    
    # Test processing (in real scenario)
    results = processor.process_bulk_urls(test_urls)
    logger.info(f"Processing results: {results}")
    
    # Test statistics
    stats = processor.get_project_statistics()
    logger.info(f"Project statistics: {stats}")
