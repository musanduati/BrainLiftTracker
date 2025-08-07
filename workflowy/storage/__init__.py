"""
Storage layer for AWS S3 and DynamoDB operations
"""

# Only import simple functions that don't have dependencies
from .project_utils import (
    generate_project_id,
    normalize_project_id,
    is_valid_project_id,
)

from .schemas import (
    get_table_names,
    get_urls_config_table_schema,
    get_state_table_schema
)

# Don't import AWSStorageV2 here to avoid circular dependency
# Users should import it directly: from workflowy.storage.aws_storage import AWSStorageV2

__all__ = [
    'generate_project_id',
    'normalize_project_id',
    'is_valid_project_id',
    'get_table_names',
    'get_urls_config_table_schema',
    'get_state_table_schema'
]
