"""
Workflowy Scraper V2 - Main module
This is now a thin wrapper that imports from the modular scraper package.
All functionality has been reorganized into the scraper/ subdirectory.
"""

# Import everything from the scraper package for backward compatibility
from workflowy.core.scraper import (
    # Main class
    WorkflowyTesterV2,
    extract_single_dok_section_llm,
    
    # Models
    WorkflowyNode,
    AuxiliaryProject,
    ProjectTreeData,
    InitializationData,
    
    # Content processing functions
    _clean_html_content,
    _extract_node_content,
    
    # DOK parsing functions
    parse_dok_points,
    get_timestamp,
    create_content_hash,
    create_dok_state_from_points,
    create_content_signature,
    calculate_similarity_score,
    detect_content_changes,
    advanced_compare_dok_states,
    
    # Tweet generation functions
    create_combined_content,
    split_content_for_twitter,
    generate_advanced_change_tweets,
    
    # API utilities
    extract_share_id,
    extract_top_level_nodes,
)

# Re-export everything for backward compatibility
__all__ = [
    'WorkflowyTesterV2',
    'extract_single_dok_section_llm',
    'WorkflowyNode',
    'AuxiliaryProject',
    'ProjectTreeData',
    'InitializationData',
    '_clean_html_content',
    '_extract_node_content',
    'parse_dok_points',
    'get_timestamp',
    'create_content_hash',
    'create_dok_state_from_points',
    'create_content_signature',
    'calculate_similarity_score',
    'detect_content_changes',
    'advanced_compare_dok_states',
    'create_combined_content',
    'split_content_for_twitter',
    'generate_advanced_change_tweets',
    'extract_share_id',
    'extract_top_level_nodes',
]

# For testing - import the test function
if __name__ == "__main__":
    import asyncio
    from workflowy.core.scraper.main import test_project_processing
    asyncio.run(test_project_processing())
