import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional, List, Dict
from datetime import datetime
import aiohttp
import diff_match_patch as dmp_module
import html

from aws_storage import AWSStorage
from logger_config import logger

# Import LLM service components
from llm_service import (
    extract_node_id_using_llm,
    get_lm_service
)

# Global LLM service instance
lm_service = get_lm_service()

# Replace with these simple classes:
class AuxiliaryProject:
    def __init__(self, shareId: str):
        self.shareId = shareId

class ProjectTreeData:
    def __init__(self, auxiliaryProjectTreeInfos: list):
        self.auxiliaryProjectTreeInfos = [
            AuxiliaryProject(info.get('shareId', '')) if isinstance(info, dict) else 
            AuxiliaryProject(info.shareId) if hasattr(info, 'shareId') else
            info 
            for info in auxiliaryProjectTreeInfos
        ]

class InitializationData:
    def __init__(self, projectTreeData: dict):
        self.projectTreeData = ProjectTreeData(
            projectTreeData.get('auxiliaryProjectTreeInfos', [])
        )

    def transform(self) -> list[str]:
        return [info.shareId for info in self.projectTreeData.auxiliaryProjectTreeInfos]

class WorkflowyNode:
    def __init__(self, node_id: str, node_name: str, content: str, timestamp: float = None):
        self.node_id = node_id
        self.node_name = node_name
        self.content = content
        self.timestamp = timestamp

async def extract_top_level_nodes(item_data_list: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Extract the main nodes such as: Purpose, Owner, Experts, SPOVs, Knowledge Tree from a project's BrainLift

    Args:
        item_data_list: List of item data from Workflowy

    Returns:
        List of dictionaries containing node names and their IDs
        [{"name": "Purpose", "id": "123"}, {"name": "Experts", "id": "456"}, ...]
    """
    # Find the root node (node with no parent or parent key doesn't exist)
    root_node = next((item for item in item_data_list if "prnt" not in item or item.get("prnt") is None), None)

    if not root_node:
        logger.error("No root node found")
        return []

    # Get all direct children of the root node
    main_nodes = []
    for item in item_data_list:
        if item.get("prnt") == root_node["id"]:
            main_nodes.append({"name": item["nm"], "id": item["id"]})
            logger.debug(f"Found main node: {item['nm']}")

    return main_nodes

def get_regex_matching_pattern(node_names: list[str] | str) -> re.Pattern:
    if isinstance(node_names, str):
        node_names = [node_names]
    node_names = [name.strip().lower() for name in node_names]
    pattern = r"^\s*[\-:;,.]*\s*(" + "|".join(re.escape(name) for name in node_names) + r")\s*[\-:;,.]*\s*$"
    return re.compile(pattern, re.IGNORECASE)

def _clean_html_content(content: str) -> str:
    """Clean HTML content and convert to markdown (standalone version)."""
    if not content:
        return ""
    
    # Remove mention tags
    content = re.sub(r"<mention[^>]*>[^<]*</mention>", "", content)

    # Convert hyperlinks to markdown format
    def replace_link(match):
        href = re.search(r'href=["\'](.*?)["\']', match.group(0))
        text = re.sub(r"<[^>]+>", "", match.group(0))
        if href:
            return f"[{text.strip()}]({href.group(1)})"
        return text.strip()

    content = re.sub(r"<a[^>]+>.*?</a>", replace_link, content)
    
    # Remove all remaining HTML tags
    content = re.sub(r"<[^>]+>", "", content)
    
    # Decode HTML entities (THIS IS THE KEY FIX)
    content = html.unescape(content)
    
    return content.strip()

def _extract_node_content(item_data_list: list[dict[str, str]], node_id: str, header_prefix: str) -> str:
    """
    Extract content for a specific node and its children in markdown format.
    Now with HTML tag cleaning!
    
    Args:
        item_data_list: List of item data from Workflowy
        node_id: ID of the node to extract
        header_prefix: Prefix for the section header
        
    Returns:
        str: Formatted content for the node (cleaned of HTML tags)
    """
    def get_node_by_id(target_id: str) -> dict | None:
        return next((item for item in item_data_list if item["id"] == target_id), None)
    
    def get_children(parent_id: str) -> list[dict]:
        return [item for item in item_data_list if item.get("prnt") == parent_id]
    
    def format_node_content(node: dict, indent_level: int = 0) -> str:
        indent = "  " * indent_level
        
        # Clean HTML tags from node name
        node_name = _clean_html_content(node.get('nm', '').strip())
        content = f"{indent}- {node_name}\n"
        
        # Add note content if present (also clean HTML)
        if node.get('no'):
            note_content = _clean_html_content(node['no'].strip())
            content += f"{indent}  {note_content}\n"
        
        # Recursively add children
        children = get_children(node["id"])
        for child in sorted(children, key=lambda x: x.get("pr", 0)):
            content += format_node_content(child, indent_level + 1)
            
        return content
    
    # Get the main node
    main_node = get_node_by_id(node_id)
    if not main_node:
        return ""
    
    # Start with header (clean HTML from main node name)
    main_node_name = _clean_html_content(main_node.get('nm', '').strip())
    result = f"{header_prefix} - {main_node_name}\n"
    
    # Add children content
    children = get_children(node_id)
    for child in sorted(children, key=lambda x: x.get("pr", 0)):
        result += format_node_content(child, 2)  # Start with 2-space indent for DOK children
    
    return result

async def extract_single_dok_section_llm(item_data_list: list[dict[str, str]], section_prefix: str) -> str:
    """
    Extract a single DOK section using LLM-based node identification.
    
    Args:
        item_data_list: List of item data from Workflowy
        section_prefix: "DOK4" or "DOK3"
        
    Returns:
        str: Content for the specified DOK section
    """
    try:
        # Get top-level nodes
        main_nodes = await extract_top_level_nodes(item_data_list)
        logger.info(f"Main nodes: {main_nodes}")
        
        # Find the specific DOK node using LLM
        dok_node_id = await extract_node_id_using_llm(section_prefix, main_nodes)
        logger.info(f"Dok node id: {dok_node_id}")
        if dok_node_id:
            return _extract_node_content(item_data_list, dok_node_id, f"  - {section_prefix}")

        else:
            logger.warning("Could not find %s node", section_prefix)
            return ""
            
    except Exception as e:
        logger.error("Error extracting %s section with LLM: %s", section_prefix, e)
        return ""

def extract_single_dok_section(content: str, section_prefix: str) -> str:
    """
    Extract a single DOK section (DOK4 or DOK3) from content.
    """
    lines = content.split('\n')
    filtered_lines = []
    capturing = False
    dok_indent_level = 2  # DOK sections are at 2 spaces indentation
    
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            
            # Check if this is the target DOK section at the correct level
            if (indent == dok_indent_level and 
                stripped.startswith(f'- {section_prefix}')):
                capturing = True
                filtered_lines.append(line)
            
            # If we're capturing and this line has greater indentation, include it
            elif capturing and indent > dok_indent_level:
                filtered_lines.append(line)
            
            # If we hit a line at DOK level or less, stop capturing
            elif capturing and indent <= dok_indent_level:
                break
        else:
            # Empty line - include if we're currently capturing
            if capturing:
                filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def parse_dok_points(dok_content: str, section_name: str) -> List[Dict]:
    """
    Parse DOK content into structured main points with sub-points.
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
    
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            
            # Main point (4 spaces indentation)
            if indent == main_indent and stripped.startswith('- '):
                # Save previous point if exists
                if current_point:
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
                current_point["sub_points"].append(sub_text)
    
    # Don't forget the last point
    if current_point:
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

def create_combined_content(main_content: str, sub_points: List[str]) -> str:
    """Combine main point with sub-points into one text block."""
    combined = main_content
    
    if sub_points:
        for sub_point in sub_points:
            combined += f" {sub_point}"
    
    return combined.strip()

def split_content_for_twitter(content: str, max_chars: int = 240) -> List[str]:
    """
    Split content into Twitter-sized chunks at sentence boundaries.
    Leaves room for thread indicators and formatting.
    """
    if len(content) <= max_chars:
        return [content]
    
    # Try to split at sentence boundaries first
    sentences = re.split(r'(?<=[.!?])\s+', content)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed limit, start new chunk
        if current_chunk and len(current_chunk + " " + sentence) > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # If any individual chunk is still too long, split by words
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            # Split long chunk by words
            words = chunk.split()
            word_chunk = ""
            for word in words:
                if word_chunk and len(word_chunk + " " + word) > max_chars:
                    final_chunks.append(word_chunk.strip())
                    word_chunk = word
                else:
                    if word_chunk:
                        word_chunk += " " + word
                    else:
                        word_chunk = word
            if word_chunk:
                final_chunks.append(word_chunk.strip())
    
    return final_chunks

def generate_tweet_data(points: List[Dict]) -> List[Dict]:
    """
    Generate tweet-ready data from parsed DOK points.
    """
    tweets = []
    
    for point in points:
        section = point["section"]
        section_title = point["section_title"]
        point_num = point["point_number"]
        total_points = point["total_points"]
        
        # Combine main content with sub-points
        combined_content = create_combined_content(
            point["main_content"], 
            point["sub_points"]
        )
        
        # Split content if too long
        content_chunks = split_content_for_twitter(combined_content)
        
        # Generate thread ID
        thread_id = f"{section.lower()}_{point_num:03d}_thread"
        
        # Create tweets for each chunk
        for chunk_idx, chunk in enumerate(content_chunks, 1):
            is_main_tweet = chunk_idx == 1
            total_parts = len(content_chunks)
            
            # Format content with prefixes and indicators
            if total_parts == 1:
                # Standalone tweet
                formatted_content = f"🔍 {section} ({point_num}/{total_points}): {chunk}"
            else:
                # Thread tweet
                thread_indicator = f"🧵{chunk_idx}/{total_parts}"
                if is_main_tweet:
                    formatted_content = f"🔍 {section} ({point_num}/{total_points}): {chunk} {thread_indicator}"
                else:
                    formatted_content = f"{chunk} {thread_indicator}"
            
            # Create tweet data
            tweet_data = {
                "id": f"{section.lower()}_{point_num:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "section_title": section_title,
                "logical_tweet_number": point_num,
                "thread_part": chunk_idx,
                "total_thread_parts": total_parts,
                "thread_id": thread_id,
                "content_raw": chunk,
                "content_formatted": formatted_content,
                "character_count": len(formatted_content),
                "is_main_tweet": is_main_tweet,
                "parent_tweet_id": f"{section.lower()}_{point_num:03d}" if not is_main_tweet else None,
                "status": "pending",
                "scheduled_for": None,
                "posted_at": None,
                "twitter_id": None,
                "created_at": datetime.now().isoformat()
            }
            
            tweets.append(tweet_data)
    
    return tweets

def extract_url_identifier(url: str) -> str:
    """Extract a unique identifier from the URL for file naming."""
    # Extract the share ID from URL like "https://workflowy.com/s/sanket-ghia/ehJL5sj6EXqV4LJR"
    match = re.search(r'/s/([^/]+)/([^/?]+)', url)
    if match:
        return f"{match.group(1)}_{match.group(2)}"
    
    # Fallback: use hash of URL
    return hashlib.md5(url.encode()).hexdigest()[:8]

# Add these utility functions BEFORE the WorkflowyTester class (around line 350)
def get_timestamp() -> str:
    """Generate timestamp in YYYYMMDD-HHMMSS format."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def is_first_run() -> bool:
    """Check if this is the first run by checking if users directory exists."""
    users_dir = Path("users")
    return not users_dir.exists() or not any(users_dir.iterdir())

def create_content_hash(main_content: str, sub_points: List[str]) -> str:
    """Create a hash for DOK point content to identify unique points."""
    combined = main_content + "||" + "||".join(sub_points)
    return hashlib.md5(combined.encode('utf-8')).hexdigest()

def load_previous_state(user_dir: Path) -> Dict:
    """Load previous DOK state from current_state.json file."""
    state_file = user_dir / "current_state.json"
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"dok4": [], "dok3": []}

def save_current_state(user_dir: Path, dok_data: Dict):
    """Save current DOK state for next comparison."""
    state_file = user_dir / "current_state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(dok_data, f, indent=2, ensure_ascii=False)

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
    
    # Clearly added content (new signatures)
    clearly_added = []
    for signature in curr_signatures:
        if signature not in prev_signatures:
            clearly_added.append(curr_signatures[signature])
    logger.info(f"Clearly added: {clearly_added}")

    # Clearly deleted content (missing signatures) 
    clearly_deleted = []
    for signature in prev_signatures:
        if signature not in curr_signatures:
            clearly_deleted.append(prev_signatures[signature])
    logger.info(f"Clearly deleted: {clearly_deleted}")

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

def generate_advanced_change_tweets(changes: Dict, section: str, is_first_run: bool = False) -> List[Dict]:
    """
    Generate tweets with advanced change detection information.
    """
    tweets = []
    timestamp = datetime.now().isoformat()
    
    # Handle first run - all content is "added"
    if is_first_run:
        for point in changes.get("added", []):
            combined_content = create_combined_content(point["main_content"], point["sub_points"])
            content_chunks = split_content_for_twitter(combined_content)
            
            thread_id = f"{section.lower()}_added_{point['point_number']:03d}_thread"
            
            for chunk_idx, chunk in enumerate(content_chunks, 1):
                is_main_tweet = chunk_idx == 1
                total_parts = len(content_chunks)
                
                # Add ADDED prefix for first run
                if total_parts == 1:
                    formatted_content = f"🟢 ADDED: {section} ({point['point_number']}): {chunk}"
                else:
                    thread_indicator = f"🧵{chunk_idx}/{total_parts}"
                    if is_main_tweet:
                        formatted_content = f"🟢 ADDED: {section} ({point['point_number']}): {chunk} {thread_indicator}"
                    else:
                        formatted_content = f"{chunk} {thread_indicator}"
                
                tweet_data = {
                    "id": f"{section.lower()}_added_{point['point_number']:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                    "section": section,
                    "change_type": "added",
                    "logical_tweet_number": point['point_number'],
                    "thread_part": chunk_idx,
                    "total_thread_parts": total_parts,
                    "thread_id": thread_id,
                    "content_raw": chunk,
                    "content_formatted": formatted_content,
                    "character_count": len(formatted_content),
                    "is_main_tweet": is_main_tweet,
                    "parent_tweet_id": f"{section.lower()}_added_{point['point_number']:03d}" if not is_main_tweet else None,
                    "status": "pending",
                    "created_at": timestamp
                }
                tweets.append(tweet_data)
        return tweets
    
    # Handle subsequent runs with advanced change detection
    tweet_counter = 1
    
    # Added points (completely new)
    for point in changes.get("added", []):
        combined_content = create_combined_content(point["main_content"], point["sub_points"])
        content_chunks = split_content_for_twitter(combined_content)
        
        thread_id = f"{section.lower()}_added_{tweet_counter:03d}_thread"
        
        for chunk_idx, chunk in enumerate(content_chunks, 1):
            formatted_content = f"🟢 ADDED: {section}: {chunk}"
            if chunk_idx > 1:
                formatted_content = f"{chunk} 🧵{chunk_idx}/{len(content_chunks)}"
            elif len(content_chunks) > 1:
                formatted_content += f" 🧵1/{len(content_chunks)}"
            
            tweets.append({
                "id": f"{section.lower()}_added_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "added",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
                "thread_part": chunk_idx,
                "total_thread_parts": len(content_chunks),
                "status": "pending",
                "created_at": timestamp
            })
        tweet_counter += 1
    
    # Updated points (with similarity information)
    for update_info in changes.get("updated", []):
        current_point = update_info["current"]
        similarity_score = update_info.get("similarity_score", 0)
        change_details = update_info.get("change_details", {})
        
        combined_content = create_combined_content(current_point["main_content"], current_point["sub_points"])
        content_chunks = split_content_for_twitter(combined_content)
        
        thread_id = f"{section.lower()}_updated_{tweet_counter:03d}_thread"
        
        # Add similarity info to the first tweet
        similarity_indicator = f"({similarity_score:.0%} similarity)"
        
        for chunk_idx, chunk in enumerate(content_chunks, 1):
            if chunk_idx == 1:
                # Add similarity info to first tweet
                formatted_content = f"🔄 UPDATED: {section} {similarity_indicator}: {chunk}"
            else:
                formatted_content = f"{chunk}"
                
            if chunk_idx > 1:
                formatted_content += f" 🧵{chunk_idx}/{len(content_chunks)}"
            elif len(content_chunks) > 1:
                formatted_content += f" 🧵1/{len(content_chunks)}"
            
            tweets.append({
                "id": f"{section.lower()}_updated_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "updated",
                "similarity_score": similarity_score,
                "change_details": change_details,
                "content_formatted": formatted_content,
                "thread_id": thread_id,
                "thread_part": chunk_idx,
                "total_thread_parts": len(content_chunks),
                "status": "pending",
                "created_at": timestamp
            })
        tweet_counter += 1
    
    # Deleted points
    for point in changes.get("deleted", []):
        combined_content = create_combined_content(point["main_content"], point["sub_points"])
        content_chunks = split_content_for_twitter(combined_content)
        
        thread_id = f"{section.lower()}_deleted_{tweet_counter:03d}_thread"
        
        for chunk_idx, chunk in enumerate(content_chunks, 1):
            formatted_content = f"❌ DELETED: {section}: {chunk}"
            if chunk_idx > 1:
                formatted_content = f"{chunk} 🧵{chunk_idx}/{len(content_chunks)}"
            elif len(content_chunks) > 1:
                formatted_content += f" 🧵1/{len(content_chunks)}"

            tweets.append({
                "id": f"{section.lower()}_deleted_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "deleted",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
                "thread_part": chunk_idx,
                "total_thread_parts": len(content_chunks),
                "status": "pending",
                "created_at": timestamp
            })
        tweet_counter += 1
    
    return tweets

class WorkflowyTester:
    WORKFLOWY_URL = "https://workflowy.com"
    LOGIN_URL = f"{WORKFLOWY_URL}/ajax_login"

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._default_timeout = aiohttp.ClientTimeout(total=10, connect=10, sock_connect=10, sock_read=10)
        # Add AWS storage
        self.storage = AWSStorage()

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._default_timeout)
        return self._session

    # @retry(
    #     stop=stop_after_attempt(3),
    #     wait=wait_exponential(),
    #     retry=retry_if_exception_type(aiohttp.ClientError),
    # )
    async def make_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Makes an async HTTP request with retry logic."""
        timeout = kwargs.pop("timeout", None)
        if isinstance(timeout, int | float):
            timeout = aiohttp.ClientTimeout(total=timeout)
        if timeout is not None:
            kwargs["timeout"] = timeout

        session = await self.get_session()
        response = await session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    async def extract_share_id(self, url: str) -> tuple[str, str]:
        """Extract session ID and share ID from Workflowy URL."""
        response = await self.make_request("GET", url)
        html_text = await response.text()
        
        cookie = response.cookies.get("sessionid")
        if not cookie:
            raise Exception("No cookie found in response headers.")

        match = re.search(r"PROJECT_TREE_DATA_URL_PARAMS = (\{.*?\});", html_text)
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            return str(cookie.value), data.get("share_id")
        else:
            raise Exception("No match found for PROJECT_TREE_DATA_URL_PARAMS.")

    async def filter_nodes_llm(self, nodes, exclude_names):
        """Recursively filter out nodes using LLM-based identification."""
        if not exclude_names:
            return nodes
            
        exclude_ids = set()
        
        # Get top-level nodes for LLM matching
        main_nodes = await extract_top_level_nodes(nodes)

        def collect_children(parent_id):
            for node in nodes:
                if node.get("prnt") == parent_id:
                    exclude_ids.add(node["id"])
                    collect_children(node["id"])

        # Use LLM-based matching to find nodes to exclude
        for exclude_name in exclude_names:
            node_id = await extract_node_id_using_llm(exclude_name, main_nodes)
            if node_id:
                exclude_ids.add(node_id)
                collect_children(node_id)
                logger.debug("Excluding node '%s' with ID: %s", exclude_name, node_id)

        return [node for node in nodes if node["id"] not in exclude_ids]

    async def get_tree_data(self, session_id: str, share_id: str | None = None, exclude_node_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Fetch tree data from Workflowy."""
        if not session_id:
            raise ValueError("No sessionId provided.")

        url = f"{self.WORKFLOWY_URL}/get_tree_data/"
        if share_id:
            url += f"?share_id={share_id}"
            
        response = await self.make_request("GET", url, headers={"Cookie": f"sessionid={session_id}"}, timeout=10)
        data = await response.json()
        items = data.get("items", [])

        if exclude_node_names:
            filtered_items = await self.filter_nodes_llm(items, exclude_node_names)
        else:
            filtered_items = items

        return filtered_items

    async def get_initial_data(self, session_id: str, share_id: str) -> list[str]:
        """Get initialization data from Workflowy."""
        url = f"{self.WORKFLOWY_URL}/get_initialization_data?share_id={share_id}&client_version=21&client_version_v2=28&no_root_children=1&include_main_tree=1"
        
        response = await self.make_request("GET", url, headers={"Cookie": f"sessionid={session_id}"}, timeout=10)
        data = await response.json()
        return InitializationData(**data).transform()

    def remove_unnecessary_html_tags(self, content: str) -> str:
        """Clean HTML content and convert to markdown."""
        # Remove mention tags
        content = re.sub(r"<mention[^>]*>[^<]*</mention>", "", content)

        # Convert hyperlinks to markdown format
        def replace_link(match):
            href = re.search(r'href=["\'](.*?)["\']', match.group(0))
            text = re.sub(r"<[^>]+>", "", match.group(0))
            if href:
                return f"[{text.strip()}]({href.group(1)})"
            return text.strip()

        content = re.sub(r"<a[^>]+>.*?</a>", replace_link, content)
        content = re.sub(r"<[^>]+>", "", content)
        content = html.unescape(content) # Decode HTML entities
        return content.strip()

    def node_to_markdown(self, node: dict[str, Any], breadcrumb: str = "", level: int = 0) -> str:
        """Convert a Workflowy node to markdown format."""
        markdown = ""
        bullet = "#" * (level + 1) if level < 3 else "-"

        current_name = node.get("nm", "").strip()
        current_breadcrumb = f"{breadcrumb} -> {current_name}" if breadcrumb else current_name

        if current_name:
            markdown += f"{bullet} {current_breadcrumb}\n"
            if node.get("no"):
                markdown += f"{node['no']}\n"
            markdown += "\n"

        # Process children recursively, limit to 6 levels
        if level < 6:
            for child in node.get("children", []):
                markdown += self.node_to_markdown(child, breadcrumb=current_breadcrumb, level=level + 1)
        else:
            # Append deeper nodes' content to the 6th level
            for child in node.get("children", []):
                markdown += f"- {child.get('nm', '').strip()}\n"
                if child.get("no"):
                    markdown += f"{child['no']}\n"
                markdown += "\n"

        return markdown

    def url_to_markdown(self, data: list[dict[str, Any]], is_breadcrumb_format: bool = True) -> WorkflowyNode:
        """Convert URL data to markdown format."""
        items_by_id = {item["id"]: item for item in data}
        tree = {}
        top_parent_name = ""
        top_parent_node_id = ""

        # Build the tree structure
        for item in data:
            parent_id = item.get("prnt")
            if parent_id:
                parent = items_by_id.get(parent_id)
                if parent:
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(item)
            else:
                tree[item["id"]] = item

        # Generate markdown for all root nodes
        markdown_content = ""
        for root_id, root_item in tree.items():
            if not top_parent_name:
                top_parent_name = root_item.get("nm", "")
                top_parent_node_id = root_item["id"]
            
            if is_breadcrumb_format:
                markdown_content += self.node_to_markdown(root_item)
            else:
                # Simple format without breadcrumbs
                markdown_content += self.generate_plain_markdown(root_item)

        return WorkflowyNode(
            node_id=top_parent_node_id,
            node_name=top_parent_name,
            content=markdown_content
        )

    def generate_plain_markdown(self, item: dict[str, Any], level: int = 0) -> str:
        """Generate plain markdown without breadcrumbs."""
        indent = "  " * level
        name = item.get("nm", "").strip()
        markdown = f"{indent}- {name}\n"
        
        if item.get("no"):
            markdown += f"{indent}  {item['no']}\n"
        
        if "children" in item:
            for child in sorted(item["children"], key=lambda x: x.get("pr", 0)):
                markdown += self.generate_plain_markdown(child, level + 1)
        
        return markdown

    async def scrape_workflowy_raw_data(self, url: str, exclude_node_names: list[str] | None = None) -> list[dict[str, str]]:
        """
        Get raw Workflowy data for LLM processing.
        """
        try:
            # Extract session and share IDs
            session_id, share_id = await self.extract_share_id(url)
            
            # Get tree data using the original share_id
            item_data_list = await self.get_tree_data(
                session_id, 
                share_id=share_id,
                exclude_node_names=exclude_node_names
            )
            logger.info(f"Successfully grabbed {len(item_data_list)} items from tree data")

            return item_data_list
            
        except Exception as e:
            logger.error(f"Error getting raw Workflowy data: {str(e)}")
            raise

    async def scrape_workflowy(self, url: str, exclude_node_names: list[str] | None = None) -> WorkflowyNode:
        """
        Main function to scrape Workflowy content.
        """
        try:
            logger.info(f"Starting to scrape Workflowy URL: {url}")
            
            # Extract session and share IDs
            session_id, share_id = await self.extract_share_id(url)
            logger.info(f"Extracted - Session ID: {session_id[:20]}..., Share ID: {share_id}")
            
            # Get initialization data
            root_node_ids = await self.get_initial_data(session_id, share_id)
            logger.info(f"Got root node IDs: {root_node_ids}")
            
            # Get tree data using the original share_id
            item_data_list = await self.get_tree_data(
                session_id, 
                share_id=share_id,
                exclude_node_names=exclude_node_names
            )
            logger.info(f"Successfully grabbed {len(item_data_list)} items from tree data")
            
            # Convert to markdown
            workflowy_node = self.url_to_markdown(item_data_list, is_breadcrumb_format=False)
            logger.info(f"Created WorkflowyNode: {workflowy_node.node_name}")
            
            # Clean HTML tags
            workflowy_node.content = self.remove_unnecessary_html_tags(workflowy_node.content)
            workflowy_node.timestamp = time.time()
            
            logger.info(f"Final content length: {len(workflowy_node.content)} characters")
            return workflowy_node
            
        except Exception as e:
            logger.error(f"Error scraping Workflowy: {str(e)}")
            raise

    async def process_single_url(self, url_config: Dict, exclude_node_names: list[str] | None = None):
        """
        Modified to use AWS storage instead of local files
        """
        url = url_config['url']
        custom_name = url_config.get('name')
        
        if custom_name:
            user_name = custom_name
        else:
            user_name = extract_url_identifier(url)
        
        # Check if this is first run using AWS
        first_run = self.storage.is_first_run(user_name)
        timestamp = get_timestamp()
        
        logger.info(f"{'='*60}")
        logger.info(f"PROCESSING: {url}")
        logger.info(f"USER: {user_name}")
        logger.info(f"FIRST RUN: {first_run}")
        logger.info(f"TIMESTAMP: {timestamp}")
        logger.info(f"{'='*60}")
        
        try:
            # Load previous state from DynamoDB with validation
            if not first_run:
                previous_state = self.storage.load_previous_state(user_name)
                # Ensure previous_state has the expected structure
                if not isinstance(previous_state, dict):
                    previous_state = {"dok4": [], "dok3": []}
                if "dok4" not in previous_state:
                    previous_state["dok4"] = []
                if "dok3" not in previous_state:
                    previous_state["dok3"] = []
            else:
                previous_state = {"dok4": [], "dok3": []}
            
            # Scrape content (unchanged)
            result = await self.scrape_workflowy(url, exclude_node_names)
            
            logger.info(f"📄 SCRAPING RESULTS:")
            logger.info(f"\tNode ID: {result.node_id}")
            logger.info(f"\tNode Name: {result.node_name}")
            logger.info(f"\tTotal Content Length: {len(result.content)} characters")
            # logger.debug(f"\tResult Content: {result.content}")
            
            # Save full content to S3
            content_s3_url = self.storage.save_scraped_content(user_name, result.content, timestamp)
            logger.info(f"✅ Full content saved to S3: {content_s3_url}")
            
            logger.info(f"📋 PROCESSING DOK SECTIONS:")
            
            current_state = {"dok4": [], "dok3": []}
            all_change_tweets = []
            
            # Scrape once, use multiple times
            raw_data = await self.scrape_workflowy_raw_data(url, exclude_node_names)
            # logger.info(f"Raw data: {raw_data}")

            # DOK4 processing using the cached raw data
            dok4_content = await extract_single_dok_section_llm(raw_data, "DOK4")
            logger.info(f"DOK4 Content: {dok4_content}")
            if dok4_content.strip():
                dok4_points = parse_dok_points(dok4_content, "DOK4")
                logger.info(f"DOK4 Points: {dok4_points}")
                current_state["dok4"] = create_dok_state_from_points(dok4_points)
                logger.info(f"DOK4 Current State: {current_state['dok4']}")
                logger.info(f"DOK4 Previous State: {previous_state['dok4']}")
                
                if first_run:
                    # First run: just establish baseline, no tweets
                    logger.info(f"DOK4 Baseline: {len(current_state['dok4'])} points established (no tweets generated)")
                else:
                    # Subsequent runs: generate tweets for changes
                    changes = advanced_compare_dok_states(previous_state["dok4"], current_state["dok4"])
                    logger.info(f"DOK4 Changes: {changes}")
                    dok4_tweets = generate_advanced_change_tweets(changes, "DOK4", first_run)
                    logger.info(f"DOK4 Tweets: {dok4_tweets}")
                    all_change_tweets.extend(dok4_tweets)
                    
                    stats = changes.get("stats", {})
                    logger.info(f"DOK4 Changes: +{stats.get('added', 0)} ~{stats.get('updated', 0)} -{stats.get('deleted', 0)} ={stats.get('unchanged', 0)}")
            
            # DOK3 processing using the same cached raw data  
            dok3_content = await extract_single_dok_section_llm(raw_data, "DOK3")
            logger.info(f"DOK3 Content: {dok3_content}")
            if dok3_content.strip():
                dok3_points = parse_dok_points(dok3_content, "DOK3")
                logger.info(f"DOK3 Points: {dok3_points}")
                current_state["dok3"] = create_dok_state_from_points(dok3_points)
                logger.info(f"DOK3 Current State: {current_state['dok3']}")
                logger.info(f"DOK3 Previous State: {previous_state['dok3']}")
                
                if first_run:
                    # First run: just establish baseline, no tweets
                    logger.info(f"DOK3 Baseline: {len(current_state['dok3'])} points established (no tweets generated)")
                else:
                    # Subsequent runs: generate tweets for changes
                    changes = advanced_compare_dok_states(previous_state["dok3"], current_state["dok3"])
                    logger.info(f"DOK3 Changes: {changes}")
                    dok3_tweets = generate_advanced_change_tweets(changes, "DOK3", first_run)
                    logger.info(f"DOK3 Tweets: {dok3_tweets}")
                    all_change_tweets.extend(dok3_tweets)
                    
                    stats = changes.get("stats", {})
                    logger.info(f"DOK3 Changes: +{stats.get('added', 0)} ~{stats.get('updated', 0)} -{stats.get('deleted', 0)} ={stats.get('unchanged', 0)}")
            
            # Save tweets to S3 only if there are tweets to save
            tweets_s3_url = None
            if all_change_tweets:
                tweets_s3_url = self.storage.save_change_tweets(user_name, all_change_tweets, timestamp)
                logger.info(f"✅ Change tweets saved to S3: {tweets_s3_url} ({len(all_change_tweets)} tweets)")
                
                first_tweet = all_change_tweets[0]
                logger.info(f"   Preview: {first_tweet['content_formatted'][:100]}...")
            elif first_run:
                logger.info(f"ℹ️ First run: No tweets generated (baseline established)")
            else:
                logger.info(f"ℹ️ No changes detected: No tweets generated")
            
            # Save current state to DynamoDB
            self.storage.save_current_state(user_name, current_state)
            logger.info(f"✅ Current state saved to DynamoDB")
            
            # Summary
            total_changes = len(all_change_tweets)
            if first_run:
                change_type = "FIRST RUN (BASELINE ESTABLISHED)"
                logger.info(f"🎉 URL PROCESSING COMPLETE! ({change_type})")
                logger.info(f"📊 Baseline established for {user_name} - no tweets generated")
                logger.info(f"🔄 Future runs will detect and post changes to Twitter")
            else:
                change_type = "INCREMENTAL UPDATE"
                logger.info(f"🎉 URL PROCESSING COMPLETE! ({change_type})")
                logger.info(f"📊 Generated {total_changes} change-based tweets for {user_name}")

            return {
                'url': url,
                'user_name': user_name,
                'status': 'success',
                'is_first_run': first_run,
                'total_change_tweets': total_changes,
                'timestamp': timestamp,
                'files_created': {
                    'full_content': content_s3_url,
                    'change_tweets': tweets_s3_url,
                    'state_location': f"DynamoDB:{self.storage.state_table_name}",
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing {url}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'url': url,
                'user_name': user_name,
                'status': 'error',
                'error': str(e)
            }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

async def test_multiple_workflowy_urls():
    """Test multiple Workflowy URLs and generate separate files for each."""
    
    logger.info("🚀 MULTI-URL WORKFLOWY SCRAPER")
    logger.info("="*60)
    
    # Load URLs from DynamoDB instead of hardcoded constant
    storage = AWSStorage()
    workflowy_urls = storage.get_workflowy_urls()
    
    if not workflowy_urls:
        logger.error("❌ No active Workflowy URLs found in DynamoDB!")
        return
    
    logger.info(f"📋 Found {len(workflowy_urls)} active URL(s) from DynamoDB:")
    for url_config in workflowy_urls:
        logger.info(f"  • {url_config['name']}: {url_config['url']}")
    
    logger.info(f"Output directory structure: users/{{user_name}}/")
    
    results = []
    
    async with WorkflowyTester() as tester:
        for i, url_config in enumerate(workflowy_urls, 1):
            logger.info(f"🔄 PROCESSING URL {i}/{len(workflowy_urls)}")
            
            result = await tester.process_single_url(
                url_config
                # exclude_node_names=["SpikyPOVs", "Private Notes"]
            )
            results.append(result)
            
            # Add delay between URLs to be respectful
            if i < len(workflowy_urls):
                logger.info(f"⏱️ Waiting 2 seconds before next URL...")
                await asyncio.sleep(2)
    
    # Final summary
    logger.info(f"{'='*60}")
    logger.info("🏁 FINAL SUMMARY")
    logger.info(f"{'='*60}")
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']
    
    logger.info(f"✅ Successful: {len(successful)}/{len(results)}")
    logger.info(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        logger.info(f"\n📁 AWS STORAGE STRUCTURE CREATED:")
        for result in successful:
            logger.info(f"\n  👤 {result['user_name']} ({result['total_change_tweets']} tweets)")
            for file_type, filepath in result['files_created'].items():
                if filepath:
                    if file_type == 'state_location':
                        logger.info(f"    - State: {filepath}")
                    else:
                        # Extract just the key from S3 URL for display
                        if filepath.startswith('s3://'):
                            key = filepath.split('/', 3)[-1] if '/' in filepath else filepath
                            logger.info(f"    - {file_type}: s3://.../.../{key.split('/')[-1]}")
                        else:
                            logger.info(f"    - {file_type}: {filepath}")
    
    if failed:
        logger.info(f"\n❌ FAILED URLS:")
        for result in failed:
            logger.info(f"  - {result['url']}: {result['error']}")
    
    total_tweets = sum(r.get('total_change_tweets', 0) for r in successful)
    logger.info(f"\n🎉 GRAND TOTAL: {total_tweets} tweets generated!")
    logger.info(f"☁️ Check your S3 bucket and DynamoDB table for all generated content")

async def test_single_url():
    """Test with a single URL (for compatibility)."""
    storage = AWSStorage()
    workflowy_urls = storage.get_workflowy_urls()
    
    if workflowy_urls:
        url_config = workflowy_urls[0]
        
        async with WorkflowyTester() as tester:
            await tester.process_single_url(
                url_config
                # exclude_node_names=["SpikyPOVs", "Private Notes"]
            )
    else:
        logger.error("❌ No URLs configured in DynamoDB")

if __name__ == "__main__":
    logger.info("Workflowy Scraper Test")
    logger.info("=====================")
    
    # Choose which test to run:
    
    # Process all configured URLs
    asyncio.run(test_multiple_workflowy_urls())
    
    # Or process just the first URL
    # asyncio.run(test_single_url())