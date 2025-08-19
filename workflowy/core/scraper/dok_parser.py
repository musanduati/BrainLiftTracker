"""
DOK content parsing and state management
"""

import hashlib
import html
import re
from datetime import datetime
from typing import List, Dict
import diff_match_patch as dmp_module
from workflowy.config.logger import logger


def parse_dok_points(dok_content: str, section_name: str) -> List[Dict]:
    """
    Parse DOK content into structured main points with sub-points.
    Filters out empty nodes that have no meaningful content.
    """
    lines = dok_content.split('\n')
    points = []
    current_point = None
    main_indent = 4  # Main points are at 4 spaces
    sub_indent = 6   # Sub-points start at 6+ spaces
    
    # Extract section title
    section_title = ""
    for line in lines:
        if line.strip().startswith(f'- {section_name}'):
            # Extract title after the hyphen (e.g., "DOK4 - SPOV" -> "SPOV")
            title_match = re.search(rf'- {section_name}\s*-\s*(.+)', line.strip())
            if title_match:
                section_title = title_match.group(1).strip()
            break
    
    def has_meaningful_content(point: Dict) -> bool:
        """Check if a DOK point has meaningful content."""
        if not point:
            return False
            
        main_content = point.get("main_content", "").strip()
        sub_points = point.get("sub_points", [])
        
        # Filter out empty main content
        if not main_content:
            logger.debug(f"🚫 Filtering out empty DOK point")
            return False
            
        # Filter out points that are just whitespace or minimal content
        if len(main_content) < 2:  # Less than 2 characters
            logger.debug(f"🚫 Filtering out minimal content DOK point: '{main_content}'")
            return False
            
        # Filter out sub-points that are empty
        meaningful_sub_points = [sub.strip() for sub in sub_points if sub.strip()]
        filtered_count = len(sub_points) - len(meaningful_sub_points)
        
        if filtered_count > 0:
            logger.debug(f"🧹 Filtered out {filtered_count} empty sub-points")
        
        # Update sub_points to only include meaningful ones
        point["sub_points"] = meaningful_sub_points
        
        return True
    
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            
            # Main point (4 spaces indentation)
            if indent == main_indent and stripped.startswith('- '):
                # Save previous point if exists AND has meaningful content
                if current_point and has_meaningful_content(current_point):
                    points.append(current_point)
                
                # Start new point
                main_text = stripped[2:].strip()  # Remove "- "
                current_point = {
                    "main_content": main_text,
                    "sub_points": []
                }
            
            # Sub-point (6+ spaces indentation)
            elif current_point and indent >= sub_indent and stripped.startswith('- '):
                sub_text = stripped[2:].strip()  # Remove "- "
                # Only add non-empty sub-points
                if sub_text:
                    current_point["sub_points"].append(sub_text)
    
    # Don't forget the last point (but only if it has meaningful content)
    if current_point and has_meaningful_content(current_point):
        points.append(current_point)
    
    # Add metadata to each point
    for i, point in enumerate(points, 1):
        point.update({
            "section": section_name,
            "section_title": section_title,
            "point_number": i,
            "total_points": len(points)
        })
    
    return points


def get_timestamp() -> str:
    """Generate timestamp in YYYYMMDD-HHMMSS format."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_content_hash(main_content: str, sub_points: List[str]) -> str:
    """Create a hash for DOK point content to identify unique points."""
    combined = main_content + "||" + "||".join(sub_points)
    return hashlib.md5(combined.encode('utf-8')).hexdigest()


def create_dok_state_from_points(points: List[Dict]) -> List[Dict]:
    """Convert DOK points to state format for comparison."""
    state_points = []
    for point in points:
        state_point = {
            "content_hash": create_content_hash(point["main_content"], point["sub_points"]),
            "main_content": point["main_content"],
            "sub_points": point["sub_points"],
            "section": point["section"],
            "section_title": point["section_title"],
            "point_number": point["point_number"]
        }
        state_points.append(state_point)
    return state_points


def create_content_signature(main_content: str, sub_points: List[str]) -> str:
    """Create a normalized content signature for comparison."""
    
    # Normalize the content for comparison AND decode HTML entities
    normalized_main = html.unescape(main_content.strip().lower())
    normalized_subs = [html.unescape(sub.strip().lower()) for sub in sub_points]
    return normalized_main + " " + " ".join(normalized_subs)


def calculate_similarity_score(text1: str, text2: str) -> float:
    """Calculate similarity score between two texts using diff-match-patch."""
    dmp = dmp_module.diff_match_patch()
    diffs = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diffs)
    
    # Calculate similarity based on unchanged vs total text
    total_chars = max(len(text1), len(text2))
    if total_chars == 0:
        return 1.0
    
    unchanged_chars = 0
    for op, text in diffs:
        if op == dmp.DIFF_EQUAL:
            unchanged_chars += len(text)
    
    return unchanged_chars / total_chars


def detect_content_changes(prev_text: str, curr_text: str, threshold: float = 0.7) -> Dict:
    """
    Detect what type of change occurred between two texts.
    
    Args:
        prev_text: Previous version of text
        curr_text: Current version of text  
        threshold: Similarity threshold to consider content as "updated" vs "replaced"
        
    Returns:
        Dict with change info including type and details
    """
    dmp = dmp_module.diff_match_patch()
    diffs = dmp.diff_main(prev_text, curr_text)
    dmp.diff_cleanupSemantic(diffs)
    
    similarity = calculate_similarity_score(prev_text, curr_text)
    
    # Analyze the diffs to understand change nature
    additions = []
    deletions = []
    unchanged = []
    
    for op, text in diffs:
        if op == dmp.DIFF_INSERT:
            additions.append(text)
        elif op == dmp.DIFF_DELETE:
            deletions.append(text)
        elif op == dmp.DIFF_EQUAL:
            unchanged.append(text)
    
    # Determine change type based on similarity and diff patterns
    if similarity >= threshold:
        change_type = "updated"
    elif similarity < 0.3:
        change_type = "replaced"  # Major rewrite
    else:
        change_type = "modified"  # Significant changes but recognizable
    
    return {
        "change_type": change_type,
        "similarity_score": similarity,
        "additions": additions,
        "deletions": deletions,
        "unchanged": unchanged,
        "diff_summary": f"Added: {len(''.join(additions))} chars, Deleted: {len(''.join(deletions))} chars"
    }


def advanced_compare_dok_states(previous_state: List[Dict], current_state: List[Dict]) -> Dict:
    """
    Advanced comparison using diff-match-patch for better change detection.
    """
    # Create lookup dictionaries with normalized content
    prev_signatures = {}
    curr_signatures = {}

    logger.info(f"Number of items in previous_state: {len(previous_state)}")
    logger.info(f"Number of items in current_state: {len(current_state)}")
    
    # Build signature maps
    for point in previous_state:
        signature = create_content_signature(point["main_content"], point["sub_points"])
        prev_signatures[signature] = point
    
    for point in current_state:
        signature = create_content_signature(point["main_content"], point["sub_points"])
        curr_signatures[signature] = point
    
    # Exact matches (unchanged content)
    exact_matches = set(prev_signatures.keys()) & set(curr_signatures.keys())
    logger.info(f"Exact matches: {exact_matches}")
    logger.info(f"Number of exact matches: {len(exact_matches)}")
    
    # Clearly added content (new signatures)
    clearly_added = []
    for signature in curr_signatures:
        if signature not in prev_signatures:
            clearly_added.append(curr_signatures[signature])
    logger.info(f"Number of clearly added: {len(clearly_added)}")
    logger.info(f"Clearly added: {clearly_added}")

    # Clearly deleted content (missing signatures) 
    clearly_deleted = []
    for signature in prev_signatures:
        if signature not in curr_signatures:
            clearly_deleted.append(prev_signatures[signature])
    logger.info(f"Number of clearly deleted: {len(clearly_deleted)}")
    logger.info(f"Clearly deleted: {clearly_deleted}")

    if len(clearly_deleted) * len(clearly_added) > 1000:
        logger.warning("⚠️ This is a large changeset. Lambda may timeout.")

    # Add a reasonable limit to prevent runaway processing
    # if len(clearly_deleted) * len(clearly_added) > 1000:
    #     # TODO: Uncomment this when we have a better way to handle large changesets (rare scenario)
    #     O(n^2) v/s O(n * log n)
    #     logger.warning("⚠️ Skipping similarity matching for large changesets")
        
    #     # Return early with pure adds/deletes, no similarity matching
    #     return {
    #         "added": clearly_added,
    #         "updated": [],  # Skip similarity matching = no updates detected
    #         "deleted": clearly_deleted,
    #         "stats": {
    #             "unchanged": len(exact_matches),
    #             "added": len(clearly_added),
    #             "updated": 0,
    #             "deleted": len(clearly_deleted)
    #         }
    #     }
    # else:
    # Advanced similarity matching for potential updates
    updated = []
    added = []
    deleted = []
    
    # For each "deleted" item, check if it's similar to any "added" item
    for deleted_point in clearly_deleted[:]:  # Copy list to modify during iteration
        best_match = None
        best_similarity = 0
        best_match_signature = None
        
        deleted_signature = create_content_signature(
            deleted_point["main_content"], 
            deleted_point["sub_points"]
        )
        
        for added_point in clearly_added[:]:  # Copy list to modify during iteration
            added_signature = create_content_signature(
                added_point["main_content"],
                added_point["sub_points"]
            )

            similarity = calculate_similarity_score(deleted_signature, added_signature)
            
            if similarity > best_similarity and similarity > 0.5:  # 50% similarity threshold
                best_match = added_point
                best_similarity = similarity
                best_match_signature = added_signature
        
        if best_match:
            # This is an update, not add/delete
            change_details = detect_content_changes(deleted_signature, best_match_signature)
            
            updated.append({
                "previous": deleted_point,
                "current": best_match,
                "similarity_score": best_similarity,
                "change_details": change_details
            })
            
            # Remove from add/delete lists
            clearly_deleted.remove(deleted_point)
            clearly_added.remove(best_match)
    
    # Remaining items are truly added/deleted
    added.extend(clearly_added)
    deleted.extend(clearly_deleted)
    
    return {
        "added": added,
        "updated": updated,
        "deleted": deleted,
        "stats": {
            "unchanged": len(exact_matches),
            "added": len(added),
            "updated": len(updated),
            "deleted": len(deleted)
        }
    }
