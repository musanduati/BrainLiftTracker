"""
DynamoDB Schema Definitions for Project-Based System
Defines the new table structures that eliminate URL dependency.
"""

from typing import Dict, Any
from workflowy.config.logger import structured_logger


def get_urls_config_table_schema() -> Dict[str, Any]:
    """
    Define the new URLS_CONFIG_TABLE schema with project_id as primary key.
    This replaces both the old URLS_CONFIG_TABLE and USER_MAPPING_TABLE.
    
    Returns:
        dict: DynamoDB table schema definition
    """
    return {
        'TableName': 'workflowy-urls-config-v2',
        'KeySchema': [
            {
                'AttributeName': 'project_id',
                'KeyType': 'HASH'  # Primary key
            }
        ],
        'AttributeDefinitions': [
            {
                'AttributeName': 'project_id',
                'AttributeType': 'S'  # String
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST',
        'GlobalSecondaryIndexes': [
            {
                'IndexName': 'url-index',
                'KeySchema': [
                    {
                        'AttributeName': 'url',
                        'KeyType': 'HASH'
                    }
                ],
                'AttributeDefinitions': [
                    {
                        'AttributeName': 'url',
                        'AttributeType': 'S'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
            },
            {
                'IndexName': 'account-index',
                'KeySchema': [
                    {
                        'AttributeName': 'account_id',
                        'KeyType': 'HASH'
                    }
                ],
                'AttributeDefinitions': [
                    {
                        'AttributeName': 'account_id',
                        'AttributeType': 'S'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
            }
        ],
        'Tags': [
            {
                'Key': 'Environment',
                'Value': 'test'
            },
            {
                'Key': 'Purpose',
                'Value': 'workflowy-project-management'
            }
        ]
    }


def get_state_table_schema() -> Dict[str, Any]:
    """
    Define the updated STATE_TABLE schema with project_id as primary key.
    
    Returns:
        dict: DynamoDB table schema definition
    """
    return {
        'TableName': 'workflowy-state-table-v2',
        'KeySchema': [
            {
                'AttributeName': 'project_id',
                'KeyType': 'HASH'  # Primary key
            }
        ],
        'AttributeDefinitions': [
            {
                'AttributeName': 'project_id',
                'AttributeType': 'S'  # String
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST',
        'TimeToLiveSpecification': {
            'AttributeName': 'ttl',
            'Enabled': True
        },
        'Tags': [
            {
                'Key': 'Environment',
                'Value': 'test'
            },
            {
                'Key': 'Purpose',
                'Value': 'workflowy-state-tracking'
            }
        ]
    }


def get_project_item_schema() -> Dict[str, str]:
    """
    Define the structure of a project item in URLS_CONFIG_TABLE.
    
    Returns:
        dict: Project item field definitions
    """
    return {
        'project_id': 'String (Primary Key) - Internal unique identifier',
        'url': 'String - Current Workflowy URL (can change)',
        'name': 'String - Display name for the project',
        'account_id': 'String - Twitter account ID for posting',
        'active': 'Boolean - Whether project is active',
        'created_at': 'String - ISO timestamp when project was created',
        'updated_at': 'String - ISO timestamp when project was last updated'
    }


def get_state_item_schema() -> Dict[str, str]:
    """
    Define the structure of a state item in STATE_TABLE.
    
    Returns:
        dict: State item field definitions
    """
    return {
        'project_id': 'String (Primary Key) - Internal unique identifier',
        'state': 'Map - DOK4 and DOK3 content state',
        'last_updated': 'String - ISO timestamp of last update',
        'ttl': 'Number - TTL expiration timestamp (1 year)'
    }


def validate_project_item(item: Dict[str, Any]) -> bool:
    """
    Validate that a project item has all required fields.
    
    Args:
        item: Project item dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['project_id', 'url', 'name', 'account_id', 'active', 'created_at', 'updated_at']
    
    for field in required_fields:
        if field not in item:
            structured_logger.error_operation("validate_project_item", f"Missing required field in project item: {field}")
            return False
    
    # Validate field types
    if not isinstance(item['project_id'], str) or not item['project_id'].startswith('project_'):
        structured_logger.error_operation("validate_project_item", f"Invalid project_id format: {item['project_id']}")
        return False
    
    if not isinstance(item['url'], str) or not item['url'].startswith('https://workflowy.com'):
        structured_logger.error_operation("validate_project_item", f"Invalid URL format: {item['url']}")
        return False
    
    if not isinstance(item['active'], bool):
        structured_logger.error_operation("validate_project_item", f"Invalid active field type: {type(item['active'])}")
        return False
    
    return True


def validate_state_item(item: Dict[str, Any]) -> bool:
    """
    Validate that a state item has all required fields.
    
    Args:
        item: State item dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['project_id', 'state', 'last_updated', 'ttl']
    
    for field in required_fields:
        if field not in item:
            structured_logger.error_operation("validate_state_item", f"Missing required field in state item: {field}")
            return False
    
    # Validate project_id format
    if not isinstance(item['project_id'], str) or not item['project_id'].startswith('project_'):
        structured_logger.error_operation("validate_state_item", f"Invalid project_id format: {item['project_id']}")
        return False
    
    # Validate state structure
    if not isinstance(item['state'], dict):
        structured_logger.error_operation("validate_state_item", f"Invalid state field type: {type(item['state'])}")
        return False
    
    # State should have dok4 and dok3 keys
    state = item['state']
    if 'dok4' not in state or 'dok3' not in state:
        structured_logger.error_operation("validate_state_item", f"State missing required dok4/dok3 keys: {list(state.keys())}")
        return False
    
    return True


# Environment-specific table names
def get_table_names(environment: str = 'test') -> Dict[str, str]:
    """
    Get table names for different environments.
    
    Args:
        environment: Environment name (test, staging, prod)
        
    Returns:
        dict: Table name mappings
    """
    return {
        'urls_config': f'workflowy-urls-config-{environment}',
        'state': f'workflowy-state-table-{environment}',
        # Legacy tables (to be deprecated)
        'legacy_urls_config': f'workflowy-urls-config-test',
        'legacy_user_mapping': f'workflowy-user-account-mapping-test',
        'legacy_state': f'workflowy-state-table-test'
    }


if __name__ == "__main__":
    # Example usage and validation
    structured_logger.info_operation("main", "DynamoDB Schema Definitions")
    
    # Print schemas
    urls_schema = get_urls_config_table_schema()
    state_schema = get_state_table_schema()
    
    structured_logger.info_operation("main", f"URLs Config Table: {urls_schema['TableName']}")
    structured_logger.info_operation("main", f"State Table: {state_schema['TableName']}")
    
    # Print field definitions
    project_fields = get_project_item_schema()
    state_fields = get_state_item_schema()
    
    structured_logger.info_operation("main", "Project item fields:")
    for field, description in project_fields.items():
        structured_logger.info_operation("main", f"  {field}: {description}")
    
    structured_logger.info_operation("main", "State item fields:")
    for field, description in state_fields.items():
        structured_logger.info_operation("main", f"  {field}: {description}")
