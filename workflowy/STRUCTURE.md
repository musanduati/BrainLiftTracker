# Workflowy X Integration - Project Structure

## Directory Organization

```
workflowy/
├── __init__.py              # Main package initialization
├── lambda_handler.py        # AWS Lambda entry point
│
├── core/                    # Core business logic
│   ├── __init__.py
│   ├── workflowy_scraper.py    # Workflowy content scraping (formerly test_workflowy_v2.py)
│   ├── tweet_poster.py         # Tweet posting logic (formerly post_tweets_v2.py)
│   ├── bulk_processor.py       # Bulk URL processing (formerly bulk_url_processor_v2.py)
│   └── llm_service.py          # LLM integration services
│
├── storage/                 # Storage and data layer
│   ├── __init__.py
│   ├── aws_storage.py          # AWS S3 & DynamoDB operations (formerly aws_storage_v2.py)
│   ├── schemas.py              # Database schemas (formerly schema_definitions.py)
│   └── project_utils.py       # Project ID utilities (formerly project_id_utils.py)
│
├── config/                  # Configuration management
│   ├── __init__.py
│   ├── environment.py          # Environment configurations (formerly environment_config_v2.py)
│   └── logger.py              # Logging configuration (formerly logger_config.py)
│
├── scripts/                 # Utility scripts (not included in Lambda package)
│   ├── create_tables.py       # DynamoDB table creation
│   ├── migrate_to_v2.py       # Migration script (formerly perform_migration_to_v2.py)
│   └── test_lambda_local.py   # Local testing (formerly test_lambda_local_v2.py)
│
├── test_data/              # Test data files (not included in Lambda package)
│   └── bulk_url_upload.json   # Sample bulk URL data
│
└── v1/                     # Deprecated V1 code (preserved for reference)
    └── ...
```

## Import Guidelines

### Direct Module Imports (Recommended)

Due to the modular structure, imports should be done directly from specific modules to avoid circular dependencies:

```python
# Import core classes directly from their modules
from workflowy.core.workflowy_scraper import WorkflowyTesterV2
from workflowy.core.tweet_poster import TweetPosterV2
from workflowy.core.bulk_processor import BulkURLProcessorV2

# Import storage classes
from workflowy.storage.aws_storage import AWSStorageV2

# Import utility functions from storage
from workflowy.storage.project_utils import generate_project_id, normalize_project_id
from workflowy.storage.schemas import get_table_names, validate_project_item

# Import configuration
from workflowy.config.logger import logger
from workflowy.config.environment import EnvironmentConfigV2

# Import Lambda handler
from workflowy.lambda_handler import lambda_handler
```

### Import Examples by Use Case

#### For Lambda Handler:
```python
from workflowy.core.workflowy_scraper import WorkflowyTesterV2
from workflowy.core.tweet_poster import TweetPosterV2
from workflowy.storage.aws_storage import AWSStorageV2
from workflowy.core.bulk_processor import is_bulk_url_request_v2, handle_bulk_url_processing_v2
from workflowy.config.logger import logger
```

#### For Scripts:
```python
# Add root to path first
import sys
from pathlib import Path
root_dir = Path(__file__).parent.parent.parent  # Navigate to root
sys.path.insert(0, str(root_dir))

# Then import workflowy modules
from workflowy.config.logger import logger
from workflowy.lambda_handler import lambda_handler
```

## Key Changes from V1 to V2

### File Renames
- `test_workflowy_v2.py` → `core/workflowy_scraper.py`
- `post_tweets_v2.py` → `core/tweet_poster.py`
- `bulk_url_processor_v2.py` → `core/bulk_processor.py`
- `aws_storage_v2.py` → `storage/aws_storage.py`
- `schema_definitions.py` → `storage/schemas.py`
- `project_id_utils.py` → `storage/project_utils.py`
- `environment_config_v2.py` → `config/environment.py`
- `logger_config.py` → `config/logger.py`
- `lambda_handler_v2.py` → `lambda_handler.py`
- `perform_migration_to_v2.py` → `scripts/migrate_to_v2.py`
- `test_lambda_local_v2.py` → `scripts/test_lambda_local.py`
- `test_bulk_url_upload.json` → `test_data/bulk_url_upload.json`

### Class Names (kept for backward compatibility)
- `WorkflowyTesterV2` - Main scraper class
- `TweetPosterV2` - Tweet posting class
- `BulkURLProcessorV2` - Bulk URL processor
- `AWSStorageV2` - AWS storage handler
- `EnvironmentConfigV2` - Environment configuration

Note: Class names still have V2 suffix to minimize code changes. These can be updated in a future refactoring.

## Benefits of New Structure

1. **Clear separation of concerns** - Core logic, storage, and config are separated
2. **Better discoverability** - It's immediately clear what each module does
3. **Cleaner Lambda package** - Scripts and test data are excluded
4. **No redundant versioning** - Removed unnecessary `_v2` suffixes from filenames
5. **Proper Python package structure** - With `__init__.py` files for clean imports
6. **Isolated deprecated code** - V1 remains untouched in its directory

## Lambda Deployment

The Lambda package now includes only necessary production code:
- Lambda handler at root level of package
- Core business logic modules
- Storage and configuration modules
- Required dependencies (installed via pip)

Scripts and test data are excluded from the Lambda deployment package.

## Running Scripts

### From root directory:
```bash
# Test imports
python test_imports.py

# Create Lambda package
./create_lambda_package_v2.sh

# Test Lambda locally
python workflowy/scripts/test_lambda_local.py posting

# Run migration
python workflowy/scripts/migrate_to_v2.py

# Create DynamoDB tables
python workflowy/scripts/create_tables.py create --environment test
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ENVIRONMENT=test
export OPENAI_API_KEY=your_key_here
```

## Testing Checklist

- [x] Module imports work correctly
- [x] Lambda handler imports resolve
- [x] Scripts can find workflowy modules
- [x] No circular import issues
- [x] Lambda package builds successfully
- [ ] Deploy and test in AWS Lambda
- [ ] Run full integration test

## Notes

- The `__init__.py` files are kept minimal to avoid circular imports
- Always import classes directly from their modules
- Scripts need to add the root directory to Python path before importing
- V1 code is preserved but isolated and not updated
