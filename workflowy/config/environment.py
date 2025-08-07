"""
Environment Configuration V2
Centralized configuration for different environments.
"""

import os
from typing import Dict, Any


class EnvironmentConfigV2:
    """Environment-specific configuration for V2 system."""
    
    @staticmethod
    def get_config(environment: str = 'test') -> Dict[str, Any]:
        """Get configuration for specified environment."""
        
        configs = {
            'test': {
                'bucket_name': 'workflowy-content-test',
                'urls_config_table': 'workflowy-urls-config-v2-test',
                'state_table': 'workflowy-state-v2-test',
                'legacy_urls_table': 'workflowy-urls-config-test',
                'legacy_mapping_table': 'workflowy-user-account-mapping-test',
                'legacy_state_table': 'workflowy-state-table-test'
            },
            'staging': {
                'bucket_name': 'workflowy-content-staging',
                'urls_config_table': 'workflowy-urls-config-v2-staging',
                'state_table': 'workflowy-state-v2-staging',
                'legacy_urls_table': 'workflowy-urls-config-staging',
                'legacy_mapping_table': 'workflowy-user-account-mapping-staging',
                'legacy_state_table': 'workflowy-state-table-staging'
            },
            'prod': {
                'bucket_name': 'workflowy-content',
                'urls_config_table': 'workflowy-urls-config-v2-prod',
                'state_table': 'workflowy-state-v2-prod',
                'legacy_urls_table': 'workflowy-urls-config',
                'legacy_mapping_table': 'workflowy-user-account-mapping',
                'legacy_state_table': 'workflowy-state-table'
            }
        }
        
        config = configs.get(environment, configs['test'])
        
        # Allow environment variable overrides
        # config['bucket_name'] = os.environ.get('WORKFLOWY_BUCKET', config['bucket_name'])
        
        return config


def apply_environment_config(storage_instance, environment: str):
    """Apply environment configuration to storage instance."""
    config = EnvironmentConfigV2.get_config(environment)
    
    # Update S3 bucket name
    storage_instance.bucket_name = config['bucket_name']
    
    # Update DynamoDB table names
    storage_instance.urls_config_table_name = config['urls_config_table']
    storage_instance.state_table_name = config['state_table']
    
    # Update the actual table connections
    storage_instance.urls_config_table = storage_instance.dynamodb.Table(config['urls_config_table'])
    storage_instance.state_table = storage_instance.dynamodb.Table(config['state_table'])
    
    # Update legacy table names too (for migration)
    if hasattr(storage_instance, 'legacy_urls_table_name'):
        storage_instance.legacy_urls_table_name = config['legacy_urls_table']
        storage_instance.legacy_mapping_table_name = config['legacy_mapping_table']
        storage_instance.legacy_state_table_name = config['legacy_state_table']
        
        # Update legacy table connections
        try:
            storage_instance.legacy_urls_table = storage_instance.dynamodb.Table(config['legacy_urls_table'])
            storage_instance.legacy_mapping_table = storage_instance.dynamodb.Table(config['legacy_mapping_table'])
            storage_instance.legacy_state_table = storage_instance.dynamodb.Table(config['legacy_state_table'])
        except Exception as e:
            from workflowy.config.logger import logger
            logger.warning(f"Legacy tables not available for {environment}: {e}")
    
    # Log the configuration
    from workflowy.config.logger import logger
    logger.info(f"🔧 Applied {environment} configuration:")
    logger.info(f"   🪣 S3 Bucket: {config['bucket_name']}")
    logger.info(f"   📋 URLs Table: {config['urls_config_table']}")
    logger.info(f"   🗄️ State Table: {config['state_table']}")
    logger.info(f"   📊 Legacy URLs Table: {config['legacy_urls_table']}")
    logger.info(f"   👥 Legacy Mapping Table: {config['legacy_mapping_table']}")
    logger.info(f"   🗂️ Legacy State Table: {config['legacy_state_table']}") 