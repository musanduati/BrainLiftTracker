# CLAUDE.md - Workflowy Integration Module

This file provides guidance to Claude Code (claude.ai/code) when working with the Workflowy integration module in this repository.

## Overview

The Workflowy integration module scrapes content from Workflowy documents, processes DOK sections (DOK4 and DOK3), detects changes between runs, and generates Twitter-ready content. It integrates with the main Twitter Manager API to post tweets automatically.

## Architecture

### Core Components

1. **test_workflowy.py** - Workflowy scraper and change detection engine
   - Scrapes Workflowy URLs and extracts DOK content
   - Implements advanced change detection using diff-match-patch
   - Generates tweet-formatted content with change indicators
   - Maintains state between runs for incremental updates

2. **post_tweets.py** - Twitter posting orchestrator
   - Reads processed tweet data from workflowy runs
   - Posts to Twitter via the main API
   - Supports two posting modes: single (one priority thread) or all (all threads)
   - Handles thread creation for multi-part tweets

### Data Flow

1. **Scraping**: Workflowy URL → Markdown content → DOK sections extraction
2. **Change Detection**: Compare with previous state → Identify added/updated/deleted content
3. **Tweet Generation**: Format changes as tweets → Save to user directories
4. **Posting**: Read tweet files → Create threads/tweets → Post via API

## Directory Structure

```
workflowy/
├── test_workflowy.py    # Scraper and change detector
├── post_tweets.py       # Twitter posting client
└── users/               # Generated data directory
    └── {user_name}/     # Per-user data
        ├── {user_name}_scraped_workflowy_{timestamp}.txt  # Raw content
        └── {user_name}_change_tweets_{timestamp}.json     # Tweet data

instance/
└── brainlifts_snapshots.db  # SQLite database for snapshots and change history
```

## Key Features

### Change Detection
- First run: All content marked as "ADDED" with 🟢 prefix
- Subsequent runs: Detects changes with prefixes:
  - 🟢 ADDED: New content
  - 🔄 UPDATED: Modified content (with similarity %)
  - ❌ DELETED: Removed content
- Uses diff-match-patch for intelligent similarity detection

### Tweet Formatting
- Automatic thread creation for long content
- Character limit handling (240 chars)
- Thread indicators (🧵1/3)
- Section-specific hashtags
- Change type prefixes

### Posting Modes
- **Single Mode**: Posts highest priority thread per account
- **All Mode**: Posts all available threads with delays
- Priority order: DOK4 > DOK3, Added > Updated > Deleted

## Configuration

### User Mapping (in post_tweets.py)
```python
USER_ACCOUNT_MAPPING = {
    "agentic_frameworks": 2,    # Account ID 2
    "education_motivation": 3,   # Account ID 3
}
```

### Workflowy URLs (in test_workflowy.py)
```python
WORKFLOWY_URLS = [
    {
        'url': 'https://workflowy.com/s/...',
        'name': 'user_name'  # Maps to directory and account
    }
]
```

### API Configuration (in post_tweets.py)
- API endpoint and key are configured in the TweetPoster class
- Supports both local and remote API endpoints

## Running the Module

### Scraping Workflowy Content
```bash
# Scrape all configured URLs
python test_workflowy.py

# This will:
# - Create users/{user_name}/ directories
# - Generate timestamped content and tweet files
# - Maintain state for change detection
```

### Posting Tweets
```bash
# Preview what will be posted (no actual posting)
python post_tweets.py preview
python post_tweets.py preview --mode all

# Post single priority thread per user
python post_tweets.py
python post_tweets.py user_name

# Post all threads for users
python post_tweets.py --mode all
python post_tweets.py --mode all user_name
```

## Important Implementation Details

### State Management
- **Database-based snapshots**: All DOK content is stored in SQLite database
- **Tables**:
  - `dok_snapshots`: Stores each DOK point with timestamp and content hash
  - `change_history`: Tracks all changes with similarity scores and details
- **Snapshot comparison**: Compares current content with latest database snapshot
- **Change tracking**: Records added/updated/deleted items with metadata
- Content comparison uses normalized text signatures
- Similarity threshold of 50% for update detection
- Database location: `instance/brainlifts_snapshots.db`

### Thread Handling
- Single tweets use tweet API endpoints
- Multi-part content uses thread API endpoints
- Automatic detection based on content length
- Thread IDs generated deterministically

### Error Handling
- Graceful handling of API failures
- Partial success tracking for batch operations
- Detailed logging for debugging

### Demo Data Integration
- Generates demo-compatible session data
- Maintains historical timeline of all runs
- Tracks posting results and engagement metrics

## Data Formats

### Change Tweet Format
```json
{
    "id": "dok4_added_001",
    "section": "DOK4",
    "change_type": "added",
    "content_formatted": "🟢 ADDED: DOK4 (1): Content text...",
    "thread_id": "dok4_added_001_thread",
    "thread_part": 1,
    "total_thread_parts": 1,
    "similarity_score": 0.85,  // For updates only
    "created_at": "2024-01-01T12:00:00"
}
```

### Session Data Format
```json
{
    "session": {
        "id": "20240101-120000",
        "user": "user_name",
        "run_number": 1,
        "change_summary": {
            "added": 5,
            "updated": 2,
            "deleted": 1
        }
    },
    "tweets": [...]
}
```

## Best Practices

1. **Run Frequency**: Run test_workflowy.py periodically to detect changes
2. **Review Before Posting**: Use preview mode to check content
3. **State Backup**: Backup current_state.json files regularly
4. **Error Recovery**: Check logs for failed posts and retry
5. **Content Validation**: Ensure DOK sections are properly formatted in Workflowy

## Database Operations

### Viewing Snapshot History
```python
# Get snapshot history for a user
history = get_snapshot_history("user_name", section="DOK4", limit=10)

# Get change history
changes = get_change_history("user_name", limit=20)
```

### Database Schema
- **dok_snapshots**: id, user_name, url, section, snapshot_timestamp, content_hash, main_content, sub_points, point_number, section_title
- **change_history**: id, user_name, section, change_type, previous_snapshot_id, current_snapshot_id, similarity_score, change_details, detected_at

## Troubleshooting

- **No changes detected**: Check database for previous snapshots using `get_snapshot_history()`
- **Tweet too long**: Content will be automatically split into threads
- **API failures**: Check API key, endpoint URL, and account mappings
- **Missing tweets**: Verify user directory contains tweet files with correct timestamp
- **Database errors**: Check `instance/brainlifts_snapshots.db` exists and has correct permissions