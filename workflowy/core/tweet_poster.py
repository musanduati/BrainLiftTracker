"""
Tweet Poster V2 - Main module
This is now a thin wrapper that imports from the modular poster package.
All functionality has been reorganized into the poster/ subdirectory.
"""

# Import everything from the poster package for backward compatibility
from workflowy.core.poster import (
    # Main class and functions
    TweetPosterV2,
    preview_what_will_be_posted_v2,
    
    # Sub-components (for any code that might import them)
    StorageInterface,
    TwitterAPIClient,
    ThreadManager,
    ProjectProcessor,
)

# Re-export everything for backward compatibility
__all__ = [
    'TweetPosterV2',
    'preview_what_will_be_posted_v2',
    'StorageInterface',
    'TwitterAPIClient',
    'ThreadManager',
    'ProjectProcessor',
]

# For testing - import the main function
if __name__ == "__main__":
    import asyncio
    from workflowy.core.poster.main import main
    asyncio.run(main())
