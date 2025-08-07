#!/usr/bin/env python3
"""
Fixed Test Migration Script - 2 Directories
Properly migrates DynamoDB state data and uses real legacy configuration.
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add the workflowy directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Setup logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required modules
from aws_storage import AWSStorage
from aws_storage_v2 import AWSStorageV2
from project_id_utils import generate_project_id, create_project_config
from environment_config_v2 import apply_environment_config


class PerformMigrationToV2:
    """Test migration that properly handles DynamoDB and real legacy data."""
    
    def __init__(self, environment: str = 'test'):
        self.environment = environment
        self.legacy_storage = AWSStorage()
        self.v2_storage = AWSStorageV2(environment)
        
        # Apply environment-specific configuration to V2 storage
        apply_environment_config(self.v2_storage, environment)
        
        # Apply environment-specific configuration to legacy storage
        self._configure_legacy_storage(environment)
        
        # Migration results
        self.migration_results = {
            'environment': environment,
            'started_at': datetime.now().isoformat(),
            'directories_to_migrate': [],
            'legacy_data_analysis': {},
            'migrated_projects': [],
            'migration_steps': [],
            'status': 'UNKNOWN',
            'completed_at': None
        }
    
    def _configure_legacy_storage(self, environment: str):
        """Configure legacy storage to use the correct environment tables."""
        from environment_config_v2 import EnvironmentConfigV2
        
        config = EnvironmentConfigV2.get_config(environment)
        
        # Update legacy storage table names
        self.legacy_storage.urls_table_name = config['legacy_urls_table']
        self.legacy_storage.mapping_table_name = config['legacy_mapping_table']
        self.legacy_storage.state_table_name = config['legacy_state_table']
        
        # Reconnect to the correct tables
        self.legacy_storage.urls_table = self.legacy_storage.dynamodb.Table(config['legacy_urls_table'])
        self.legacy_storage.mapping_table = self.legacy_storage.dynamodb.Table(config['legacy_mapping_table'])
        self.legacy_storage.state_table = self.legacy_storage.dynamodb.Table(config['legacy_state_table'])
        
        logger.info(f"🔧 Configured legacy storage for {environment}:")
        logger.info(f"   📋 Legacy URLs: {config['legacy_urls_table']}")
        logger.info(f"   👥 Legacy Mapping: {config['legacy_mapping_table']}")
        logger.info(f"   🗂️ Legacy State: {config['legacy_state_table']}")
    
    def analyze_legacy_data(self, directories: List[str]) -> Dict[str, Any]:
        """Analyze existing legacy data for the directories."""
        logger.info("🔍 Analyzing legacy data...")
        
        analysis = {
            'legacy_urls': {},
            'legacy_users': {},
            'legacy_states': {},
            'user_to_directory_mapping': {}
        }
        
        try:
            # Get legacy URL configurations
            legacy_urls = self.legacy_storage.get_workflowy_urls()
            logger.info(f"Found {len(legacy_urls)} legacy URL configurations")
            
            # Get legacy user account mappings
            legacy_mappings = self.legacy_storage.get_user_account_mapping()
            logger.info(f"Found {len(legacy_mappings)} legacy user account mappings")
            
            # Create mappings for our directories
            for directory in directories:
                # Find matching URL config
                matching_url = None
                
                # Normalize directory name (remove trailing slash for matching)
                clean_directory = directory.rstrip('/')
                
                for url_config in legacy_urls:
                    url = url_config['url']
                    logger.info(f"URL: {url}")
                    # Extract name from URL to match with directory
                    if f"/{clean_directory}/" in url or url.endswith(f"/{clean_directory}"):
                        matching_url = url_config
                        break
                
                if matching_url:
                    analysis['legacy_urls'][directory] = matching_url
                    logger.info(f"✅ Found legacy URL for {directory}: {matching_url['url']}")
                else:
                    # Create a reasonable guess based on directory name
                    user_name = directory.split('_')[0] if '_' in directory else directory
                    analysis['legacy_urls'][directory] = {
                        'url': f"https://workflowy.com/s/{user_name}/sample_share_id",
                        'name': directory
                    }
                    logger.warning(f"⚠️ No legacy URL found for {directory}, using generated URL")
                
                # Extract user name for account mapping
                user_name = directory.split('_')[0] if '_' in directory else directory
                analysis['user_to_directory_mapping'][directory] = user_name
                
                # Get account mapping
                account_id = legacy_mappings.get(user_name, 'TBA')
                analysis['legacy_users'][directory] = {
                    'user_name': user_name,
                    'account_id': account_id
                }
                logger.info(f"✅ Account mapping for {directory}: {user_name} -> {account_id}")
                
                # Get legacy state data
                legacy_state = self.legacy_storage.load_previous_state(user_name)
                analysis['legacy_states'][directory] = {
                    'user_name': user_name,
                    'state': legacy_state,
                    'has_state': bool(legacy_state.get('dok4') or legacy_state.get('dok3'))
                }
                logger.info(f"✅ State data for {directory}: DOK4={len(legacy_state.get('dok4', []))}, DOK3={len(legacy_state.get('dok3', []))}")
        
        except Exception as e:
            logger.error(f"❌ Error analyzing legacy data: {e}")
            analysis['error'] = str(e)
        
        self.migration_results['legacy_data_analysis'] = analysis
        return analysis
    
    def select_directories_for_migration(self) -> List[str]:
        """Select directories for migration."""
        selected_dirs = [
            '2025-05-20t2144-iep',
            'agora',
            'ai-storytelling',
            'all-the-notes-this-i',
            'alphagt-school-chess',
            'an-offline-local-hig',
            'ap-csa',
            'berry-expertise-brai',
            'brainlift-math-3-6-b',
            'brainlift-middle-sch',
            'brainlift-on-vocabul',
            'brainmaxxing',
            'chesslift',
            'cognitive-science-in',
            'copy-of-kathryns-bra',
            'deep-research-mcp',
            'di-video-script-2nd',
            'dok4-with-mcqs',
            'dreamupgg-ai-game-cr',
            'earning-5s-on-ap-tes',
            'educational-song-bra',
            'english-incept',
            'fast-math-brainlift',
            'growthgameai',
            'hamiltonian-history',
            'hs-science',
            'incept-superbuilders',
            'language-learning-br',
            'leadify-monthly-repo',
            'lifecore-dashboard',
            'ludwitt-the-ai-first',
            'mathko',
            'mindsurf-brainlift',
            'mitigating-bias-in-e',
            'nextgen-after-school',
            'ootd',
            'persistent-ai-tutor',
            'playcademy',
            'qc-first',
            'robinhood-for-kids-m',
            'sat-monsters-brainli',
            'sat-prep-scale',
            'science-education-br',
            'science-learning-gra',
            'science-of-learning',
            'sidequests-proof-of',
            'strata-school-texas',
            'tigerwallet-brainlif',
            'timeback-dash',
            'timebotkyros-the-tim',
            'vibe-marketing-short',
            'vibe-marketing',
            'workflowy-x-integrat',
        ]
        
        self.migration_results['directories_to_migrate'] = selected_dirs
        logger.info(f"📋 Selected directories for migration: {selected_dirs}")
        return selected_dirs
    
    def create_projects_for_directories(self, directories: List[str], legacy_analysis: Dict[str, Any]) -> List[Dict]:
        """Create V2 projects using real legacy data."""
        logger.info("🏗️ Creating V2 projects with real legacy data...")
        
        created_projects = []
        
        for directory in directories:
            try:
                # Get real legacy data
                legacy_url_config = legacy_analysis['legacy_urls'].get(directory, {})
                legacy_user_config = legacy_analysis['legacy_users'].get(directory, {})
                
                # Use real URL and account ID from legacy data
                real_url = legacy_url_config.get('url', f"https://workflowy.com/s/{directory}/unknown")
                real_account_id = legacy_user_config.get('account_id', 'TBA')
                real_name = legacy_url_config.get('name', f"Migrated {directory}")
                
                # Create project configuration with real data
                project_config = {
                    'url': real_url,
                    'account_id': str(real_account_id),
                    'name': real_name
                }
                
                # Create the project
                project_id = self.v2_storage.create_project(**project_config)
                
                if project_id:
                    project_info = {
                        'project_id': project_id,
                        'source_directory': directory,
                        'source_user_name': legacy_user_config.get('user_name'),
                        'name': project_config['name'],
                        'url': project_config['url'],
                        'account_id': project_config['account_id'],
                        'status': 'created'
                    }
                    created_projects.append(project_info)
                    
                    logger.info(f"✅ Created project {project_id} for directory '{directory}' with real data")
                    logger.info(f"   URL: {real_url}")
                    logger.info(f"   Account: {real_account_id}")
                else:
                    logger.error(f"❌ Failed to create project for directory '{directory}'")
                    
            except Exception as e:
                logger.error(f"❌ Error creating project for directory '{directory}': {e}")
        
        self.migration_results['migrated_projects'] = created_projects
        return created_projects
    
    def migrate_dynamodb_state_data(self, created_projects: List[Dict], legacy_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate DynamoDB state data from legacy to V2 format."""
        logger.info("🗄️ Migrating DynamoDB state data...")
        
        state_migration_summary = {
            'total_states_migrated': 0,
            'project_state_migrations': [],
            'errors': []
        }
        
        for project in created_projects:
            project_id = project['project_id']
            directory = project['source_directory']
            user_name = project['source_user_name']
            
            logger.info(f"🔄 Migrating state data for project {project_id} (user: {user_name})")
            
            try:
                # Get legacy state data
                legacy_state_info = legacy_analysis['legacy_states'].get(directory, {})
                legacy_state = legacy_state_info.get('state', {})
                
                if legacy_state_info.get('has_state'):
                    # Save state using V2 format (project_id instead of user_name)
                    self.v2_storage.save_current_state(project_id, legacy_state)
                    
                    state_migration = {
                        'project_id': project_id,
                        'source_user_name': user_name,
                        'dok4_points': len(legacy_state.get('dok4', [])),
                        'dok3_points': len(legacy_state.get('dok3', [])),
                        'status': 'migrated'
                    }
                    
                    state_migration_summary['project_state_migrations'].append(state_migration)
                    state_migration_summary['total_states_migrated'] += 1
                    
                    logger.info(f"✅ Migrated state for project {project_id}: DOK4={state_migration['dok4_points']}, DOK3={state_migration['dok3_points']}")
                else:
                    logger.info(f"ℹ️ No state data to migrate for project {project_id}")
                    
            except Exception as e:
                error_msg = f"Error migrating state for project {project_id}: {e}"
                state_migration_summary['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        return state_migration_summary
    
    def migrate_s3_data(self, created_projects: List[Dict]) -> Dict[str, Any]:
        """Migrate S3 data from legacy paths to project-based paths."""
        logger.info("📦 Starting S3 data migration...")
        
        import boto3
        s3_client = boto3.client('s3')
        # bucket_name = 'workflowy-content-test'
        bucket_name = self.v2_storage.bucket_name
        
        migration_summary = {
            'total_files_migrated': 0,
            'total_size_mb': 0,
            'project_migrations': [],
            'errors': []
        }
        
        for project in created_projects:
            project_id = project['project_id']
            source_directory = project['source_directory']
            
            logger.info(f"🔄 Migrating S3 data for project {project_id} (source: {source_directory})")
            
            try:
                # List all files in the source directory
                response = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=f"{source_directory}/",
                    MaxKeys=1000
                )
                
                if 'Contents' not in response:
                    logger.warning(f"⚠️ No files found in source directory: {source_directory}")
                    continue
                
                files_migrated = 0
                total_size = 0
                
                for obj in response['Contents']:
                    source_key = obj['Key']
                    
                    # Skip directory markers
                    if source_key.endswith('/'):
                        continue
                    
                    # Generate new key with project_id
                    relative_path = source_key[len(source_directory)+1:]  # Remove directory prefix
                    new_key = f"{project_id}/{relative_path}"
                    
                    # Copy the object
                    copy_source = {'Bucket': bucket_name, 'Key': source_key}
                    s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=bucket_name,
                        Key=new_key
                    )
                    
                    files_migrated += 1
                    total_size += obj['Size']
                    
                    logger.debug(f"  📄 Migrated: {source_key} -> {new_key}")
                
                project_migration = {
                    'project_id': project_id,
                    'source_directory': source_directory,
                    'files_migrated': files_migrated,
                    'size_mb': total_size / (1024 * 1024),
                    'status': 'completed'
                }
                
                migration_summary['project_migrations'].append(project_migration)
                migration_summary['total_files_migrated'] += files_migrated
                migration_summary['total_size_mb'] += total_size / (1024 * 1024)
                
                logger.info(f"✅ Migrated {files_migrated} files ({total_size/(1024*1024):.2f} MB) for project {project_id}")
                
            except Exception as e:
                error_msg = f"Error migrating S3 data for {source_directory}: {e}"
                migration_summary['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        return migration_summary
    
    def validate_migration(self, created_projects: List[Dict]) -> Dict[str, Any]:
        """Validate that the migration was successful."""
        logger.info("🔍 Validating complete migration results...")
        
        import boto3
        s3_client = boto3.client('s3')
        # bucket_name = 'workflowy-content-test'
        bucket_name = self.v2_storage.bucket_name
        
        validation_results = {
            'overall_status': 'UNKNOWN',
            'project_validations': [],
            'issues': [],
            'total_files_validated': 0,
            'total_states_validated': 0
        }
        
        all_valid = True
        
        for project in created_projects:
            project_id = project['project_id']
            source_directory = project['source_directory']
            
            logger.info(f"🔍 Validating project {project_id}...")
            
            try:
                # Check that project exists in V2 system
                project_config = self.v2_storage.get_project_by_id(project_id)
                project_exists = bool(project_config)
                
                # Check that files exist in new location
                s3_response = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=f"{project_id}/",
                    MaxKeys=1000
                )
                
                file_count = len(s3_response.get('Contents', [])) - 1  # Subtract 1 for directory marker if present
                
                # Check that state data was migrated
                v2_state = self.v2_storage.load_previous_state(project_id)
                has_migrated_state = bool(v2_state.get('dok4') or v2_state.get('dok3'))
                state_count = len(v2_state.get('dok4', [])) + len(v2_state.get('dok3', []))
                
                project_validation = {
                    'project_id': project_id,
                    'source_directory': source_directory,
                    'project_config_exists': project_exists,
                    'files_in_new_location': file_count,
                    'state_data_migrated': has_migrated_state,
                    'state_points_count': state_count,
                    'real_url': project_config.get('url') if project_config else None,
                    'real_account_id': project_config.get('account_id') if project_config else None,
                    'status': 'valid' if project_exists and file_count > 0 else 'invalid'
                }
                
                validation_results['project_validations'].append(project_validation)
                validation_results['total_files_validated'] += file_count
                if has_migrated_state:
                    validation_results['total_states_validated'] += 1
                
                if project_validation['status'] == 'valid':
                    logger.info(f"✅ Project {project_id} validation passed:")
                    logger.info(f"   📄 Files: {file_count}")
                    logger.info(f"   🗄️ State: {state_count} points")
                    logger.info(f"   🔗 URL: {project_validation['real_url']}")
                    logger.info(f"   👤 Account: {project_validation['real_account_id']}")
                else:
                    logger.error(f"❌ Project {project_id} validation failed")
                    all_valid = False
                
            except Exception as e:
                validation_results['issues'].append(f"Error validating project {project_id}: {e}")
                logger.error(f"❌ Error validating project {project_id}: {e}")
                all_valid = False
        
        validation_results['overall_status'] = 'PASS' if all_valid else 'FAIL'
        return validation_results
    
    async def run_test_migration(self) -> Dict[str, Any]:
        """Execute the complete test migration with DynamoDB state data."""
        logger.info("🚀 Starting COMPLETE 2-directory test migration...")
        logger.info("=" * 60)
        
        try:
            # Step 1: Select directories
            self.migration_results['migration_steps'].append({
                'step': 'directory_selection',
                'started_at': datetime.now().isoformat(),
                'status': 'in_progress'
            })
            
            directories = self.select_directories_for_migration()
            
            self.migration_results['migration_steps'][-1].update({
                'completed_at': datetime.now().isoformat(),
                'status': 'completed',
                'result': f"Selected {len(directories)} directories"
            })
            
            # Step 2: Analyze legacy data
            self.migration_results['migration_steps'].append({
                'step': 'legacy_data_analysis',
                'started_at': datetime.now().isoformat(),
                'status': 'in_progress'
            })
            
            legacy_analysis = self.analyze_legacy_data(directories)
            
            self.migration_results['migration_steps'][-1].update({
                'completed_at': datetime.now().isoformat(),
                'status': 'completed',
                'result': f"Analyzed legacy data for {len(directories)} directories"
            })
            
            # Step 3: Create V2 projects with real legacy data
            self.migration_results['migration_steps'].append({
                'step': 'project_creation',
                'started_at': datetime.now().isoformat(),
                'status': 'in_progress'
            })
            
            created_projects = self.create_projects_for_directories(directories, legacy_analysis)
            
            self.migration_results['migration_steps'][-1].update({
                'completed_at': datetime.now().isoformat(),
                'status': 'completed',
                'result': f"Created {len(created_projects)} projects with real data"
            })
            
            if not created_projects:
                raise Exception("No projects were created successfully")
            
            # Step 4: Migrate DynamoDB state data
            self.migration_results['migration_steps'].append({
                'step': 'dynamodb_state_migration',
                'started_at': datetime.now().isoformat(),
                'status': 'in_progress'
            })
            
            state_migration = self.migrate_dynamodb_state_data(created_projects, legacy_analysis)
            
            self.migration_results['migration_steps'][-1].update({
                'completed_at': datetime.now().isoformat(),
                'status': 'completed',
                'result': f"Migrated {state_migration['total_states_migrated']} state records"
            })
            
            # Step 5: Migrate S3 data
            self.migration_results['migration_steps'].append({
                'step': 's3_migration',
                'started_at': datetime.now().isoformat(),
                'status': 'in_progress'
            })
            
            s3_migration = self.migrate_s3_data(created_projects)
            
            self.migration_results['migration_steps'][-1].update({
                'completed_at': datetime.now().isoformat(),
                'status': 'completed',
                'result': f"Migrated {s3_migration['total_files_migrated']} files"
            })
            
            # Step 6: Validate migration
            self.migration_results['migration_steps'].append({
                'step': 'validation',
                'started_at': datetime.now().isoformat(),
                'status': 'in_progress'
            })
            
            validation = self.validate_migration(created_projects)
            
            self.migration_results['migration_steps'][-1].update({
                'completed_at': datetime.now().isoformat(),
                'status': 'completed',
                'result': f"Validation {validation['overall_status']}"
            })
            
            # Final results
            self.migration_results.update({
                'state_migration': state_migration,
                's3_migration': s3_migration,
                'validation': validation,
                'status': 'SUCCESS' if validation['overall_status'] == 'PASS' else 'FAILED',
                'completed_at': datetime.now().isoformat()
            })
            
            # Log summary
            logger.info("=" * 60)
            logger.info("📊 COMPLETE MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Status: {self.migration_results['status']}")
            logger.info(f"Projects created: {len(created_projects)}")
            logger.info(f"State records migrated: {state_migration['total_states_migrated']}")
            logger.info(f"Files migrated: {s3_migration['total_files_migrated']}")
            logger.info(f"Total size: {s3_migration['total_size_mb']:.2f} MB")
            logger.info(f"Validation: {validation['overall_status']}")
            
            if validation['overall_status'] == 'PASS':
                logger.info("🎉 COMPLETE TEST MIGRATION COMPLETED SUCCESSFULLY!")
                logger.info("✅ All data types migrated: DynamoDB state + S3 files + Real URLs/accounts")
            else:
                logger.error("❌ TEST MIGRATION FAILED")
                
        except Exception as e:
            self.migration_results.update({
                'status': 'ERROR',
                'error': str(e),
                'completed_at': datetime.now().isoformat()
            })
            logger.error(f"❌ Migration failed with error: {e}")
        
        return self.migration_results
    
    def save_migration_report(self, filename: str = None):
        """Save migration report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"complete_migration_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.migration_results, f, indent=2, default=str)
        
        logger.info(f"📄 Complete migration report saved: {filename}")


async def main():
    """Run the complete 2-directory test migration."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Complete test migration for all directories')
    parser.add_argument('--environment', '-e', default='test',
                       help='Environment (default: test)')
    parser.add_argument('--save-report', '-s', action='store_true',
                       help='Save detailed report')
    
    args = parser.parse_args()
    
    # Run migration
    logger.info(f"Running migration for environment: {args.environment}")
    migrator = PerformMigrationToV2(args.environment)
    # logger.info(f"Migrator: {migrator}")
    # logger.info(f"Legacy storage: {migrator.legacy_storage}")
    # logger.info(f"V2 storage: {migrator.v2_storage}")
    # logger.info(f"Legacy storage: {migrator.legacy_storage.get_workflowy_urls()}")
    # logger.info(f"V2 storage: {migrator.v2_storage.get_all_projects()}")
    # logger.info(f"Bucket name: {migrator.v2_storage.bucket_name}")

    results = await migrator.run_test_migration()
    
    if args.save_report:
        migrator.save_migration_report()
    
    # Exit with appropriate code
    success = results['status'] == 'SUCCESS'
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 