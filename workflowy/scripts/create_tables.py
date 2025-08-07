#!/usr/bin/env python3
"""
Standalone DynamoDB table creator.
This script creates the project-based tables without complex imports.
"""

import boto3
import time
import os
import sys
import argparse
import json
from typing import Dict, Any

def setup_logger():
    """Set up basic logging."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logger()

def get_table_names(environment: str = 'test') -> Dict[str, str]:
    """Get table names for environment."""
    return {
        'urls_config': f'workflowy-urls-config-v2-{environment}',
        'state': f'workflowy-state-v2-{environment}',
        'legacy_urls_config': f'workflowy-urls-config-{environment}',
        'legacy_user_mapping': f'workflowy-user-account-mapping-{environment}',
        'legacy_state': f'workflowy-state-table-{environment}'
    }

def get_urls_config_table_schema() -> Dict[str, Any]:
    """Get URLs configuration table schema."""
    return {
        'AttributeDefinitions': [
            {
                'AttributeName': 'project_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'account_id',
                'AttributeType': 'S'
            }
        ],
        'KeySchema': [
            {
                'AttributeName': 'project_id',
                'KeyType': 'HASH'
            }
        ],
        'GlobalSecondaryIndexes': [
            {
                'IndexName': 'AccountIdIndex',
                'KeySchema': [
                    {
                        'AttributeName': 'account_id',
                        'KeyType': 'HASH'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
                # Note: BillingMode is not allowed in GSI definition
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST'
    }

def get_state_table_schema() -> Dict[str, Any]:
    """Get state table schema."""
    return {
        'AttributeDefinitions': [
            {
                'AttributeName': 'project_id',
                'AttributeType': 'S'
            }
        ],
        'KeySchema': [
            {
                'AttributeName': 'project_id',
                'KeyType': 'HASH'
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST'
        # Note: TimeToLiveSpecification is set separately after table creation
    }

class DynamoTableCreator:
    """Creates DynamoDB tables for the project-based system."""
    
    def __init__(self, environment: str = 'test', region: str = 'us-east-1'):
        self.environment = environment
        self.region = region
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.table_names = get_table_names(environment)
        logger.info(f"🚀 DynamoDB Table Creator initialized for {environment} environment")
    
    def wait_for_table_active(self, table_name: str, timeout: int = 300) -> bool:
        """Wait for table to become active."""
        logger.info(f"⏳ Waiting for table {table_name} to become active...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.dynamodb.describe_table(TableName=table_name)
                status = response['Table']['TableStatus']
                
                if status == 'ACTIVE':
                    logger.info(f"✅ Table {table_name} is now active")
                    return True
                elif status in ['CREATING', 'UPDATING']:
                    logger.info(f"🔄 Table {table_name} status: {status}")
                    time.sleep(10)
                else:
                    logger.error(f"❌ Table {table_name} has unexpected status: {status}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error checking table status: {e}")
                return False
        
        logger.error(f"❌ Timeout waiting for table {table_name} to become active")
        return False
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        try:
            self.dynamodb.describe_table(TableName=table_name)
            return True
        except self.dynamodb.exceptions.ResourceNotFoundException:
            return False
        except Exception as e:
            logger.error(f"❌ Error checking if table exists: {e}")
            return False
    
    def set_ttl_on_table(self, table_name: str, ttl_attribute: str = 'ttl') -> bool:
        """Set TTL on a table after it's created."""
        try:
            logger.info(f"🕐 Setting TTL on table {table_name}")
            self.dynamodb.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': ttl_attribute,
                    'Enabled': True
                }
            )
            logger.info(f"✅ TTL set on table {table_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error setting TTL on table {table_name}: {e}")
            return False
    
    def create_urls_config_table(self) -> bool:
        """Create the URLs configuration table."""
        table_name = self.table_names['urls_config']
        
        if self.table_exists(table_name):
            logger.info(f"✅ Table {table_name} already exists")
            return True
        
        logger.info(f"🔨 Creating URLs config table: {table_name}")
        
        try:
            schema = get_urls_config_table_schema()
            
            self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=schema['KeySchema'],
                AttributeDefinitions=schema['AttributeDefinitions'],
                BillingMode=schema['BillingMode'],
                GlobalSecondaryIndexes=schema.get('GlobalSecondaryIndexes', []),
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Purpose', 'Value': 'Project-based URL configuration'},
                    {'Key': 'Version', 'Value': '2.0'}
                ]
            )
            
            # Wait for table to become active
            if self.wait_for_table_active(table_name):
                logger.info(f"✅ Successfully created table: {table_name}")
                return True
            else:
                logger.error(f"❌ Table creation failed for: {table_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating URLs config table: {e}")
            return False
    
    def create_state_table(self) -> bool:
        """Create the state table."""
        table_name = self.table_names['state']
        
        if self.table_exists(table_name):
            logger.info(f"✅ Table {table_name} already exists")
            return True
        
        logger.info(f"🔨 Creating state table: {table_name}")
        
        try:
            schema = get_state_table_schema()
            
            # Create the table first
            self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=schema['KeySchema'],
                AttributeDefinitions=schema['AttributeDefinitions'],
                BillingMode=schema['BillingMode'],
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Purpose', 'Value': 'Project-based state storage'},
                    {'Key': 'Version', 'Value': '2.0'}
                ]
            )
            
            # Wait for table to become active
            if self.wait_for_table_active(table_name):
                # Set TTL after table is active
                self.set_ttl_on_table(table_name, 'ttl')
                logger.info(f"✅ Successfully created table: {table_name}")
                return True
            else:
                logger.error(f"❌ Table creation failed for: {table_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating state table: {e}")
            return False
    
    def create_all_tables(self) -> bool:
        """Create all required tables."""
        logger.info(f"🚀 Creating all tables for {self.environment} environment")
        
        success = True
        
        # Create URLs config table
        if not self.create_urls_config_table():
            success = False
        
        # Create state table
        if not self.create_state_table():
            success = False
        
        if success:
            logger.info("✅ All tables created successfully")
        else:
            logger.error("❌ Some table creation failed")
        
        return success
    
    def delete_table(self, table_name: str) -> bool:
        """Delete a table."""
        if not self.table_exists(table_name):
            logger.info(f"✅ Table {table_name} does not exist")
            return True
        
        logger.info(f"🗑️ Deleting table: {table_name}")
        
        try:
            self.dynamodb.delete_table(TableName=table_name)
            logger.info(f"✅ Successfully deleted table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting table {table_name}: {e}")
            return False
    
    def delete_all_tables(self) -> bool:
        """Delete all tables for this environment."""
        logger.info(f"🗑️ Deleting all tables for {self.environment} environment")
        
        success = True
        
        for table_type, table_name in self.table_names.items():
            if table_type.startswith('legacy_'):
                continue  # Don't delete legacy tables
            if not self.delete_table(table_name):
                success = False
        
        if success:
            logger.info("✅ All tables deleted successfully")
        else:
            logger.error("❌ Some table deletion failed")
        
        return success
    
    def get_table_info(self) -> Dict[str, Any]:
        """Get information about all tables."""
        table_info = {
            'environment': self.environment,
            'region': self.region,
            'tables': {}
        }
        
        for table_type, table_name in self.table_names.items():
            if table_type.startswith('legacy_'):
                continue  # Skip legacy tables
                
            try:
                if self.table_exists(table_name):
                    response = self.dynamodb.describe_table(TableName=table_name)
                    table = response['Table']
                    
                    # Check TTL status
                    ttl_status = "UNKNOWN"
                    try:
                        ttl_response = self.dynamodb.describe_time_to_live(TableName=table_name)
                        ttl_status = ttl_response.get('TimeToLiveDescription', {}).get('TimeToLiveStatus', 'UNKNOWN')
                    except:
                        pass
                    
                    table_info['tables'][table_type] = {
                        'name': table_name,
                        'status': table['TableStatus'],
                        'item_count': table['ItemCount'],
                        'size_bytes': table['TableSizeBytes'],
                        'created_at': table['CreationDateTime'].isoformat() if 'CreationDateTime' in table else None,
                        'ttl_status': ttl_status
                    }
                else:
                    table_info['tables'][table_type] = {
                        'name': table_name,
                        'status': 'NOT_EXISTS'
                    }
            except Exception as e:
                table_info['tables'][table_type] = {
                    'name': table_name,
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        return table_info

def main():
    parser = argparse.ArgumentParser(description='Manage DynamoDB tables for project-based system')
    parser.add_argument('action', choices=['create', 'delete', 'info'], help='Action to perform')
    parser.add_argument('--environment', '-e', default='test', help='Environment (test/staging/production)')
    parser.add_argument('--region', '-r', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    logger.info(f"🚀 Running table {args.action} for {args.environment} environment")
    
    try:
        creator = DynamoTableCreator(args.environment, args.region)
        
        if args.action == 'create':
            success = creator.create_all_tables()
            if success:
                logger.info("✅ Table creation completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Table creation failed")
                sys.exit(1)
        
        elif args.action == 'delete':
            success = creator.delete_all_tables()
            if success:
                logger.info("✅ Table deletion completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Table deletion failed")
                sys.exit(1)
        
        elif args.action == 'info':
            info = creator.get_table_info()
            print("\n📊 Table Information:")
            print(json.dumps(info, indent=2, default=str))
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"❌ Error during {args.action}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 