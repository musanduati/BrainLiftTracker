"""
Project ID Utilities
Provides functions for generating and managing unique project identifiers
that are independent of Workflowy URLs.
"""

import uuid
import re
from typing import Optional, Dict
from datetime import datetime
from workflowy.config.logger import logger


def generate_project_id() -> str:
    """
    Generate a unique project ID.
    
    Format: project_{uuid4_hex}
    Example: project_a1b2c3d4e5f67890abcdef1234567890
    
    Returns:
        str: Unique project ID
    """
    uuid_hex = uuid.uuid4().hex
    project_id = f"project_{uuid_hex}"
    logger.debug(f"Generated new project ID: {project_id}")
    return project_id


def is_valid_project_id(project_id: str) -> bool:
    """
    Validate if a string is a valid project ID format.
    
    Args:
        project_id: String to validate
        
    Returns:
        bool: True if valid project ID format, False otherwise
    """
    if not isinstance(project_id, str):
        return False
    
    # Pattern: project_ followed by 32 hex characters
    pattern = r'^project_[a-f0-9]{32}$'
    return bool(re.match(pattern, project_id.lower()))


def extract_uuid_from_project_id(project_id: str) -> Optional[str]:
    """
    Extract the UUID part from a project ID.
    
    Args:
        project_id: Project ID in format project_{uuid}
        
    Returns:
        str: UUID part if valid, None if invalid
    """
    if not is_valid_project_id(project_id):
        return None
    
    return project_id[7:]  # Remove 'project_' prefix


def normalize_project_id(project_id: str) -> Optional[str]:
    """
    Normalize a project ID to standard format (lowercase).
    
    Args:
        project_id: Project ID to normalize
        
    Returns:
        str: Normalized project ID if valid, None if invalid
    """
    if not isinstance(project_id, str):
        return None
    
    normalized = project_id.lower().strip()
    
    if is_valid_project_id(normalized):
        return normalized
    
    return None


def generate_display_name(project_id: str, fallback_name: str = "Unnamed Project") -> str:
    """
    Generate a human-readable display name from project ID.
    Used when no custom name is provided.
    
    Args:
        project_id: Project ID
        fallback_name: Default name if project_id is invalid
        
    Returns:
        str: Display name
    """
    if not is_valid_project_id(project_id):
        return fallback_name
    
    # Use first 8 characters of UUID for short display
    uuid_part = extract_uuid_from_project_id(project_id)
    if uuid_part:
        short_id = uuid_part[:8]
        return f"Project {short_id}"
    
    return fallback_name


def create_project_config(
    url: str, 
    account_id: str, 
    name: Optional[str] = None,
    project_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Create a complete project configuration dictionary.
    
    Args:
        url: Workflowy URL
        account_id: Twitter account ID
        name: Optional display name
        project_id: Optional existing project ID (generates new if None)
        
    Returns:
        dict: Complete project configuration
    """
    # Generate project ID if not provided
    if project_id is None:
        project_id = generate_project_id()
    elif not is_valid_project_id(project_id):
        logger.warning(f"Invalid project ID provided: {project_id}, generating new one")
        project_id = generate_project_id()
    
    # Generate display name if not provided
    if name is None:
        name = generate_display_name(project_id)
    
    now = datetime.now().isoformat()
    
    return {
        'project_id': project_id,
        'url': url,
        'name': name,
        'account_id': str(account_id),
        'active': True,
        'created_at': now,
        'updated_at': now
    }


# Validation constants
PROJECT_ID_PREFIX = "project_"
PROJECT_ID_UUID_LENGTH = 32
PROJECT_ID_TOTAL_LENGTH = len(PROJECT_ID_PREFIX) + PROJECT_ID_UUID_LENGTH


if __name__ == "__main__":
    # Basic testing
    from workflowy.config.logger import logger
    
    logger.info("Testing Project ID utilities...")
    
    # Test generation
    pid1 = generate_project_id()
    pid2 = generate_project_id()
    logger.info(f"Generated IDs: {pid1}, {pid2}")
    
    # Test validation
    logger.info(f"Valid {pid1}: {is_valid_project_id(pid1)}")
    logger.info(f"Valid 'invalid': {is_valid_project_id('invalid')}")
    
    # Test UUID extraction
    uuid_part = extract_uuid_from_project_id(pid1)
    logger.info(f"UUID from {pid1}: {uuid_part}")
    
    # Test display name
    display = generate_display_name(pid1)
    logger.info(f"Display name for {pid1}: {display}")
    
    # Test project config
    config = create_project_config(
        url="https://workflowy.com/s/test/abc123",
        account_id="123",
        name="Test Project"
    )
    logger.info(f"Project config: {config}")
