# Workflowy X Integration - Project Structure

## Directory Organization

```
workflowy/
├── __init__.py              # Main package initialization
├── lambda_handler.py        # AWS Lambda entry point
│
├── core/                    # Core business logic
│   ├── __init__.py
│   ├── scraper/            # Modularized scraper components (NEW)
│   │   ├── __init__.py
│   │   ├── main.py             # Main WorkflowyTesterV2 class
│   │   ├── models.py           # Data models
│   │   ├── content_processing.py  # Content extraction
│   │   ├── api_utils.py        # API interactions
│   │   ├── dok_parser.py       # DOK parsing logic
│   │   └── tweet_generation.py # Tweet generation
│   ├── poster/             # Modularized poster components (NEW)
│   │   ├── __init__.py
│   │   ├── main.py             # Main TweetPosterV2 class
│   │   ├── storage_interface.py # Storage operations
│   │   ├── twitter_api.py      # Twitter API client
│   │   ├── thread_manager.py   # Thread handling
│   │   └── project_processor.py # Project processing
│   ├── workflowy_scraper.py    # Backward compatibility wrapper
│   ├── tweet_poster.py         # Backward compatibility wrapper
│   ├── bulk_processor.py       # Bulk URL processing
│   └── llm_service.py          # LLM integration services
│
├── storage/                 # Storage and data layer
│   ├── __init__.py
│   ├── aws_storage.py          # AWS S3 & DynamoDB operations
│   ├── schemas.py              # Database schemas
│   └── project_utils.py       # Project ID utilities
│
├── config/                  # Configuration management
│   ├── __init__.py
│   ├── environment.py          # Environment configurations
│   └── logger.py              # Logging configuration
│
├── scripts/                 # Utility scripts (not included in Lambda package)
│   ├── create_tables.py       # DynamoDB table creation
│   ├── migrate_to_v2.py       # Migration script
│   └── test_lambda_local.py   # Local testing
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
# Import from backward compatibility wrappers (preserves existing code)
from workflowy.core.workflowy_scraper import WorkflowyTesterV2
from workflowy.core.tweet_poster import TweetPosterV2

# Or import from new modular structure
from workflowy.core.scraper.main import WorkflowyTesterV2
from workflowy.core.poster.main import TweetPosterV2

# Import specific components
from workflowy.core.scraper.dok_parser import parse_dok_points
from workflowy.core.poster.twitter_api import TwitterAPIClient

# Import storage classes
from workflowy.storage.aws_storage import AWSStorageV2

# Import utility functions
from workflowy.storage.project_utils import generate_project_id, normalize_project_id
from workflowy.storage.schemas import get_table_names, validate_project_item

# Import configuration
from workflowy.config.logger import logger
from workflowy.config.environment import EnvironmentConfigV2
```

## Module Organization Details

### Scraper Module (`core/scraper/`)
- **main.py** - Main WorkflowyTesterV2 class
- **models.py** - Data models (WorkflowyNode, etc.)
- **content_processing.py** - HTML cleaning & content extraction
- **api_utils.py** - Workflowy API interactions
- **dok_parser.py** - DOK parsing & state management
- **tweet_generation.py** - Tweet formatting & generation

### Poster Module (`core/poster/`)
- **main.py** - Main TweetPosterV2 class
- **storage_interface.py** - Storage operations
- **twitter_api.py** - Twitter API client
- **thread_manager.py** - Thread handling logic
- **project_processor.py** - Project processing

## Lambda Deployment

The Lambda package now includes the new modular structure:
- Lambda handler at root level of package
- Core business logic with `scraper/` and `poster/` subdirectories
- Storage and configuration modules
- Required dependencies (installed via pip)

Scripts and test data are excluded from the Lambda deployment package.

## Running Scripts

### From root directory:
```bash
# Build Lambda package
./create_lambda_package_v2.sh

# Test Lambda locally
python workflowy/scripts/test_lambda_local.py posting

# Create DynamoDB tables
python workflowy/scripts/create_tables.py create --environment test
```

## Testing Checklist

- [x] Module imports work correctly
- [x] Lambda handler imports resolve
- [x] Scripts can find workflowy modules
- [x] Lambda package builds successfully
- [x] Scraper reorganization tested
- [x] Poster reorganization tested
- [x] Deploy and test in AWS Lambda
- [x] Run full integration test

## Notes

- The `__init__.py` files are kept minimal to avoid circular imports
- Always import classes directly from their modules or use backward compatibility wrappers
- Scripts need to add the root directory to Python path before importing
- V1 code is preserved but isolated and not updated
- Both major files (`workflowy_scraper.py` and `tweet_poster.py`) are now modularized
