# test_workflowy.py
import asyncio
import base64
import hashlib
import html
import json
import logging
import re
import time
import os
from pathlib import Path
from typing import Any, Optional, List, Dict
from datetime import datetime

import aiohttp

import diff_match_patch as dmp_module

# Add AWS storage import
from aws_storage import AWSStorage

logger = logging.getLogger("workflowy_test")

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

def get_regex_matching_pattern(node_names: list[str] | str) -> re.Pattern:
    if isinstance(node_names, str):
        node_names = [node_names]
    node_names = [name.strip().lower() for name in node_names]
    pattern = r"^\s*[\-:;,.]*\s*(" + "|".join(re.escape(name) for name in node_names) + r")\s*[\-:;,.]*\s*$"
    return re.compile(pattern, re.IGNORECASE)

def extract_dok_sections_from_content(content: str) -> str:
    """
    Extract only DOK4 and DOK3 sections from the clean markdown content.
    Only looks for DOK4/DOK3 at the correct high-level indentation (2 spaces).
    """
    lines = content.split('\n')
    filtered_lines = []
    capturing = False
    dok_indent_level = 2  # DOK4 and DOK3 are at 2 spaces indentation
    
    for line in lines:
        # Calculate the indentation level
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            
            # Check if this is a DOK4 or DOK3 section header at the correct level
            if (indent == dok_indent_level and 
                (stripped.startswith('- DOK4') or stripped.startswith('- DOK3'))):
                capturing = True
                filtered_lines.append(line)
            
            # If we're capturing and this line has greater indentation than DOK level, include it
            elif capturing and indent > dok_indent_level:
                filtered_lines.append(line)
            
            # If we hit a line at DOK level or less that's not DOK4/DOK3, stop capturing
            elif capturing and indent <= dok_indent_level:
                if (indent == dok_indent_level and 
                    (stripped.startswith('- DOK4') or stripped.startswith('- DOK3'))):
                    # Start a new DOK section
                    filtered_lines.append(line)
                else:
                    # End of current DOK section
                    capturing = False
        else:
            # Empty line - include if we're currently capturing
            if capturing:
                filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

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
                if section == "DOK4":
                    formatted_content += " #AI #Strategy #Innovation"
                else:  # DOK3
                    formatted_content += " #Insights #Strategy #Tech"
            else:
                # Thread tweet
                thread_indicator = f"🧵{chunk_idx}/{total_parts}"
                if is_main_tweet:
                    formatted_content = f"🔍 {section} ({point_num}/{total_points}): {chunk} {thread_indicator}"
                else:
                    formatted_content = f"{chunk} {thread_indicator}"
                
                # Add hashtags only to the last tweet in thread
                if chunk_idx == total_parts:
                    if section == "DOK4":
                        formatted_content += " #AI #Strategy #Innovation"
                    else:
                        formatted_content += " #Insights #Strategy #Tech"
            
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

def process_dok_content_to_tweets(full_content: str) -> Dict[str, List[Dict]]:
    """
    Process full DOK content and generate tweet data for both DOK4 and DOK3.
    """
    results = {}
    
    # Process DOK4
    dok4_content = extract_single_dok_section(full_content, "DOK4")
    if dok4_content.strip():
        dok4_points = parse_dok_points(dok4_content, "DOK4")
        dok4_tweets = generate_tweet_data(dok4_points)
        results["dok4"] = dok4_tweets
        print(f"Generated {len(dok4_tweets)} tweets from {len(dok4_points)} DOK4 points")
    
    # Process DOK3
    dok3_content = extract_single_dok_section(full_content, "DOK3")
    if dok3_content.strip():
        dok3_points = parse_dok_points(dok3_content, "DOK3")
        dok3_tweets = generate_tweet_data(dok3_points)
        results["dok3"] = dok3_tweets
        print(f"Generated {len(dok3_tweets)} tweets from {len(dok3_points)} DOK3 points")
    
    return results

def extract_url_identifier(url: str) -> str:
    """Extract a unique identifier from the URL for file naming."""
    # Extract the share ID from URL like "https://workflowy.com/s/sanket-ghia/ehJL5sj6EXqV4LJR"
    match = re.search(r'/s/([^/]+)/([^/?]+)', url)
    if match:
        return f"{match.group(1)}_{match.group(2)}"
    
    # Fallback: use hash of URL
    return hashlib.md5(url.encode()).hexdigest()[:8]

def create_user_directory(user_name: str) -> Path:
    """
    Create and return the user directory path.
    
    Args:
        user_name: Name for the user directory
        
    Returns:
        Path object for the user directory
    """
    # Create users directory if it doesn't exist
    users_dir = Path("users")
    users_dir.mkdir(exist_ok=True)
    
    # Create user-specific directory
    user_dir = users_dir / user_name
    user_dir.mkdir(exist_ok=True)
    
    return user_dir

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

def compare_dok_states(previous_state: List[Dict], current_state: List[Dict]) -> Dict:
    """Compare previous and current DOK states to identify changes."""
    prev_hashes = {point["content_hash"]: point for point in previous_state}
    curr_hashes = {point["content_hash"]: point for point in current_state}
    
    added = [point for hash_key, point in curr_hashes.items() if hash_key not in prev_hashes]
    deleted = [point for hash_key, point in prev_hashes.items() if hash_key not in curr_hashes]
    
    # For updated detection, we need to check if content with same position has changed
    updated = []
    # We'll use a simpler approach: if main_content is similar but hash is different
    for curr_point in current_state:
        curr_main = curr_point["main_content"].lower().strip()
        # Look for similar content in previous state
        for prev_point in previous_state:
            prev_main = prev_point["main_content"].lower().strip()
            # If main content is very similar (first 50 chars) but hash is different
            if (curr_main[:50] == prev_main[:50] and 
                curr_point["content_hash"] != prev_point["content_hash"] and
                curr_point["content_hash"] not in prev_hashes):
                updated.append({
                    "current": curr_point,
                    "previous": prev_point
                })
                # Remove from added since it's an update
                added = [p for p in added if p["content_hash"] != curr_point["content_hash"]]
                break
    
    return {
        "added": added,
        "updated": updated,
        "deleted": deleted
    }

def generate_change_tweets(changes: Dict, section: str, is_first_run: bool = False) -> List[Dict]:
    """Generate tweets based on detected changes with appropriate prefixes."""
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
                
                # Add ADDED prefix
                if total_parts == 1:
                    formatted_content = f"🟢 ADDED: {section} ({point['point_number']}): {chunk}"
                else:
                    thread_indicator = f"🧵{chunk_idx}/{total_parts}"
                    if is_main_tweet:
                        formatted_content = f"🟢 ADDED: {section} ({point['point_number']}): {chunk} {thread_indicator}"
                    else:
                        formatted_content = f"{chunk} {thread_indicator}"
                
                # Add hashtags
                if chunk_idx == total_parts:
                    if section == "DOK4":
                        formatted_content += " #AI #Strategy #Innovation"
                    else:
                        formatted_content += " #Insights #Strategy #Tech"
                
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
    
    # Handle subsequent runs with change detection
    tweet_counter = 1
    
    # Added points
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
            
            if chunk_idx == len(content_chunks):
                formatted_content += f" #{section.replace('DOK', 'DOK')}"
            
            tweets.append({
                "id": f"{section.lower()}_added_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "added",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
                "created_at": timestamp
            })
        tweet_counter += 1
    
    # Updated points
    for update_info in changes.get("updated", []):
        current_point = update_info["current"]
        combined_content = create_combined_content(current_point["main_content"], current_point["sub_points"])
        content_chunks = split_content_for_twitter(combined_content)
        
        thread_id = f"{section.lower()}_updated_{tweet_counter:03d}_thread"
        
        for chunk_idx, chunk in enumerate(content_chunks, 1):
            formatted_content = f"🔄 UPDATED: {section}: {chunk}"
            if chunk_idx > 1:
                formatted_content = f"{chunk} 🧵{chunk_idx}/{len(content_chunks)}"
            elif len(content_chunks) > 1:
                formatted_content += f" 🧵1/{len(content_chunks)}"
            
            if chunk_idx == len(content_chunks):
                formatted_content += f" #{section.replace('DOK', 'DOK')}"
            
            tweets.append({
                "id": f"{section.lower()}_updated_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "updated",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
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
            
            if chunk_idx == len(content_chunks):
                formatted_content += f" #{section.replace('DOK', 'DOK')}"
            
            tweets.append({
                "id": f"{section.lower()}_deleted_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "deleted",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
                "created_at": timestamp
            })
        tweet_counter += 1
    
    return tweets

def create_content_signature(main_content: str, sub_points: List[str]) -> str:
    """Create a normalized content signature for comparison."""
    # Normalize the content for comparison
    normalized_main = main_content.strip().lower()
    normalized_subs = [sub.strip().lower() for sub in sub_points]
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
    
    # Clearly added content (new signatures)
    clearly_added = []
    for signature in curr_signatures:
        if signature not in prev_signatures:
            clearly_added.append(curr_signatures[signature])
    
    # Clearly deleted content (missing signatures) 
    clearly_deleted = []
    for signature in prev_signatures:
        if signature not in curr_signatures:
            clearly_deleted.append(prev_signatures[signature])
    
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
                
                # Add hashtags
                if chunk_idx == total_parts:
                    if section == "DOK4":
                        formatted_content += " #AI #Strategy #Innovation"
                    else:
                        formatted_content += " #Insights #Strategy #Tech"
                
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
            
            if chunk_idx == len(content_chunks):
                hashtag = "#AI #Strategy #Innovation" if section == "DOK4" else "#Insights #Strategy #Tech"
                formatted_content += f" {hashtag}"
            
            tweets.append({
                "id": f"{section.lower()}_added_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "added",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
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
            
            if chunk_idx == len(content_chunks):
                hashtag = "#AI #Strategy #Innovation" if section == "DOK4" else "#Insights #Strategy #Tech"
                formatted_content += f" {hashtag}"
            
            tweets.append({
                "id": f"{section.lower()}_updated_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "updated",
                "similarity_score": similarity_score,
                "change_details": change_details,
                "content_formatted": formatted_content,
                "thread_id": thread_id,
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
            
            if chunk_idx == len(content_chunks):
                hashtag = "#AI #Strategy #Innovation" if section == "DOK4" else "#Insights #Strategy #Tech"
                formatted_content += f" {hashtag}"
            
            tweets.append({
                "id": f"{section.lower()}_deleted_{tweet_counter:03d}" + (f"_reply{chunk_idx-1}" if chunk_idx > 1 else ""),
                "section": section,
                "change_type": "deleted",
                "content_formatted": formatted_content,
                "thread_id": thread_id,
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

    def filter_nodes(self, nodes, exclude_names):
        """Recursively filter out nodes with the specified name and their children."""
        if not exclude_names:
            return nodes
            
        exclude_ids = set()
        exclude_patterns = [get_regex_matching_pattern([name]) for name in exclude_names]

        def collect_children(parent_id):
            for node in nodes:
                if node.get("prnt") == parent_id:
                    exclude_ids.add(node["id"])
                    collect_children(node["id"])

        for node in nodes:
            node_name = node.get("nm", "").strip()
            if node_name and any(pattern.match(node_name) for pattern in exclude_patterns):
                exclude_ids.add(node["id"])
                collect_children(node["id"])

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
            filtered_items = self.filter_nodes(items, exclude_node_names)
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

    async def scrape_workflowy(self, url: str, exclude_node_names: list[str] | None = None) -> WorkflowyNode:
        """
        Main function to scrape Workflowy content.
        """
        try:
            print(f"Starting to scrape Workflowy URL: {url}")
            
            # Extract session and share IDs
            session_id, share_id = await self.extract_share_id(url)
            print(f"Extracted - Session ID: {session_id[:20]}..., Share ID: {share_id}")
            
            # Get initialization data
            root_node_ids = await self.get_initial_data(session_id, share_id)
            print(f"Got root node IDs: {root_node_ids}")
            
            # Get tree data using the original share_id
            item_data_list = await self.get_tree_data(
                session_id, 
                share_id=share_id,
                exclude_node_names=exclude_node_names
            )
            print(f"Successfully grabbed {len(item_data_list)} items from tree data")
            
            # Convert to markdown
            workflowy_node = self.url_to_markdown(item_data_list, is_breadcrumb_format=False)
            print(f"Created WorkflowyNode: {workflowy_node.node_name}")
            
            # Clean HTML tags
            workflowy_node.content = self.remove_unnecessary_html_tags(workflowy_node.content)
            workflowy_node.timestamp = time.time()
            
            print(f"Final content length: {len(workflowy_node.content)} characters")
            return workflowy_node
            
        except Exception as e:
            print(f"Error scraping Workflowy: {str(e)}")
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
        
        print(f"\n{'='*60}")
        print(f"PROCESSING: {url}")
        print(f"USER: {user_name}")
        print(f"FIRST RUN: {first_run}")
        print(f"TIMESTAMP: {timestamp}")
        print(f"{'='*60}")
        
        try:
            # Load previous state from DynamoDB
            previous_state = self.storage.load_previous_state(user_name) if not first_run else {"dok4": [], "dok3": []}
            
            # Scrape content (unchanged)
            result = await self.scrape_workflowy(url, exclude_node_names)
            
            print(f"\n📄 SCRAPING RESULTS:")
            print(f"Node ID: {result.node_id}")
            print(f"Node Name: {result.node_name}")
            print(f"Total Content Length: {len(result.content)} characters")
            
            # Save full content to S3 instead of local file
            content_s3_url = self.storage.save_scraped_content(user_name, result.content, timestamp)
            print(f"✅ Full content saved to S3: {content_s3_url}")
            
            # Process DOK sections (logic unchanged)
            print(f"\n📋 PROCESSING DOK SECTIONS:")
            
            current_state = {"dok4": [], "dok3": []}
            all_change_tweets = []
            
            # DOK4 processing (unchanged logic)
            dok4_content = extract_single_dok_section(result.content, "DOK4")
            if dok4_content.strip():
                dok4_points = parse_dok_points(dok4_content, "DOK4")
                current_state["dok4"] = create_dok_state_from_points(dok4_points)
                
                if first_run:
                    changes = {"added": current_state["dok4"], "updated": [], "deleted": []}
                else:
                    changes = advanced_compare_dok_states(previous_state["dok4"], current_state["dok4"])
                
                dok4_tweets = generate_advanced_change_tweets(changes, "DOK4", first_run)
                all_change_tweets.extend(dok4_tweets)
                
                stats = changes.get("stats", {})
                print(f"DOK4 Changes: +{stats.get('added', 0)} ~{stats.get('updated', 0)} -{stats.get('deleted', 0)} ={stats.get('unchanged', 0)}")
            
            # DOK3 processing (unchanged logic)
            dok3_content = extract_single_dok_section(result.content, "DOK3")
            if dok3_content.strip():
                dok3_points = parse_dok_points(dok3_content, "DOK3")
                current_state["dok3"] = create_dok_state_from_points(dok3_points)
                
                if first_run:
                    changes = {"added": current_state["dok3"], "updated": [], "deleted": []}
                else:
                    changes = advanced_compare_dok_states(previous_state["dok3"], current_state["dok3"])
                
                dok3_tweets = generate_advanced_change_tweets(changes, "DOK3", first_run)
                all_change_tweets.extend(dok3_tweets)
                
                stats = changes.get("stats", {})
                print(f"DOK3 Changes: +{stats.get('added', 0)} ~{stats.get('updated', 0)} -{stats.get('deleted', 0)} ={stats.get('unchanged', 0)}")
            
            # Save tweets to S3 instead of local file
            tweets_s3_url = None
            if all_change_tweets:
                tweets_s3_url = self.storage.save_change_tweets(user_name, all_change_tweets, timestamp)
                print(f"✅ Change tweets saved to S3: {tweets_s3_url} ({len(all_change_tweets)} tweets)")
                
                if all_change_tweets:
                    first_tweet = all_change_tweets[0]
                    print(f"   Preview: {first_tweet['content_formatted'][:100]}...")
            
            # Save current state to DynamoDB
            self.storage.save_current_state(user_name, current_state)
            print(f"✅ Current state saved to DynamoDB")
            
            # Summary
            total_changes = len(all_change_tweets)
            change_type = "FIRST RUN" if first_run else "INCREMENTAL UPDATE"
            print(f"\n🎉 URL PROCESSING COMPLETE! ({change_type})")
            print(f"📊 Generated {total_changes} change-based tweets for {user_name}")

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
            print(f"❌ Error processing {url}: {str(e)}")
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

# Add these functions after create_user_directory() function

def create_demo_directory():
    """Create demo directory structure if it doesn't exist."""
    demo_dir = Path("demo")
    demo_dir.mkdir(exist_ok=True)
    
    (demo_dir / "data").mkdir(exist_ok=True)
    (demo_dir / "assets" / "avatars").mkdir(parents=True, exist_ok=True)
    
    return demo_dir

def get_next_run_number(user_name: str) -> int:
    """Get the next run number for a user."""
    demo_dir = Path("demo/data")
    if not demo_dir.exists():
        return 1
    
    # Look for existing session files for this user
    pattern = f"session_*_{user_name}.json"
    existing_files = list(demo_dir.glob(pattern))
    
    if not existing_files:
        return 1
    
    # Extract run numbers from existing files
    run_numbers = []
    for file in existing_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                run_num = data.get("session", {}).get("run_number", 0)
                run_numbers.append(run_num)
        except (json.JSONDecodeError, FileNotFoundError):
            continue
    
    return max(run_numbers, default=0) + 1

def generate_demo_tweet_data(tweets: List[Dict], user_name: str, section: str, timestamp: str, run_number: int) -> List[Dict]:
    """Convert tweet data to demo-compatible format."""
    demo_tweets = []
    
    for tweet in tweets:
        # Create realistic Twitter user data
        username = user_name.replace("_", "")
        display_name = user_name.replace("_", " ").title()
        
        demo_tweet = {
            "id": tweet.get("id", f"tweet_{len(demo_tweets)+1}"),
            "session_id": timestamp,
            "run_number": run_number,
            "user": {
                "username": username,
                "display_name": display_name,
                "handle": f"@{username}",
                "avatar": f"./assets/avatars/{user_name}.jpg",
                "verified": False
            },
            "content": {
                "text": tweet.get("content_formatted", ""),
                "raw_text": tweet.get("content_raw", ""),
                "character_count": tweet.get("character_count", len(tweet.get("content_formatted", "")))
            },
            "metadata": {
                "section": section,
                "change_type": tweet.get("change_type", "added"),
                "similarity_score": tweet.get("similarity_score"),
                "change_details": tweet.get("change_details"),
                "logical_tweet_number": tweet.get("logical_tweet_number"),
                "thread_id": tweet.get("thread_id"),
                "thread_part": tweet.get("thread_part", 1),
                "total_thread_parts": tweet.get("total_thread_parts", 1),
                "is_main_tweet": tweet.get("is_main_tweet", True),
                "parent_tweet_id": tweet.get("parent_tweet_id")
            },
            "timestamps": {
                "created_at": tweet.get("created_at", datetime.now().isoformat()),
                "scheduled_for": tweet.get("scheduled_for"),
                "posted_at": tweet.get("posted_at")
            },
            "status": {
                "current": tweet.get("status", "pending"),
                "twitter_id": tweet.get("twitter_id"),
                "posting_session": None
            },
            "engagement": {
                "likes": 0,
                "retweets": 0, 
                "replies": 0,
                "views": 0
            }
        }
        demo_tweets.append(demo_tweet)
    
    return demo_tweets

def save_session_data(user_name: str, timestamp: str, all_change_tweets: List[Dict], run_number: int):
    """Save session data for demo purposes."""
    demo_dir = create_demo_directory()
    
    # Process tweets by section
    dok4_tweets = [t for t in all_change_tweets if t.get("section") == "DOK4"]
    dok3_tweets = [t for t in all_change_tweets if t.get("section") == "DOK3"]
    
    # Generate demo-compatible data
    demo_dok4 = generate_demo_tweet_data(dok4_tweets, user_name, "DOK4", timestamp, run_number)
    demo_dok3 = generate_demo_tweet_data(dok3_tweets, user_name, "DOK3", timestamp, run_number)
    
    all_demo_tweets = demo_dok4 + demo_dok3
    
    # Create session metadata
    session_data = {
        "session": {
            "id": timestamp,
            "user": user_name,
            "timestamp": timestamp,
            "run_number": run_number,
            "total_tweets": len(all_demo_tweets),
            "sections_processed": ["DOK4", "DOK3"],
            "change_summary": {
                "added": len([t for t in all_change_tweets if t.get("change_type") == "added"]),
                "updated": len([t for t in all_change_tweets if t.get("change_type") == "updated"]),
                "deleted": len([t for t in all_change_tweets if t.get("change_type") == "deleted"])
            }
        },
        "tweets": all_demo_tweets,
        "user_info": {
            "username": user_name.replace("_", ""),
            "display_name": user_name.replace("_", " ").title(),
            "handle": f"@{user_name.replace('_', '')}",
            "avatar": f"./assets/avatars/{user_name}.jpg"
        }
    }
    
    # Save session file
    session_file = demo_dir / "data" / f"session_{timestamp}_{user_name}.json"
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Demo session data saved to '{session_file}'")
    
    return session_data

# Configuration for multiple URLs
WORKFLOWY_URLS = [
    # {
    #     'url': 'https://workflowy.com/s/sanket-ghia/ehJL5sj6EXqV4LJR',
    #     'name': 'sanket_ghia'
    # },
    # {
    #     'url': 'https://workflowy.com/s/musa-nduati/m65mhjMinJVpppGF',
    #     'name': 'musa_nduati'
    # },
    {
        'url': 'https://workflowy.com/s/agentic-frameworks-i/5VJixY76Ppm2BXvk',
        'name': 'agentic_frameworks'
    },
    # {
    #     'url': 'https://workflowy.com/s/education-motivation/qigeXHtSSY5wwDC7',
    #     'name': 'education_motivation'
    # },
    # {
    #     'url': 'https://workflowy.com/s/new-pk-2-reading-cou/bjSyw1MzswiIsciE',
    #     'name': 'new_pk_2_reading_course'
    # }
]

async def test_multiple_workflowy_urls():
    """Test multiple Workflowy URLs and generate separate files for each."""
    
    print("🚀 MULTI-URL WORKFLOWY SCRAPER")
    print("="*60)
    print(f"Processing {len(WORKFLOWY_URLS)} URL(s)")
    print(f"Output directory structure: users/{{user_name}}/")
    
    results = []
    
    async with WorkflowyTester() as tester:
        for i, url_config in enumerate(WORKFLOWY_URLS, 1):
            print(f"\n🔄 PROCESSING URL {i}/{len(WORKFLOWY_URLS)}")
            
            result = await tester.process_single_url(
                url_config,
                exclude_node_names=["SpikyPOVs", "Private Notes"]
            )
            results.append(result)
            
            # Add delay between URLs to be respectful
            if i < len(WORKFLOWY_URLS):
                print(f"⏱️ Waiting 2 seconds before next URL...")
                await asyncio.sleep(2)
    
    # Final summary
    print(f"{'='*60}")
    print("🏁 FINAL SUMMARY")
    print(f"{'='*60}")
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        print(f"\n📁 DIRECTORY STRUCTURE CREATED:")
        for result in successful:
            print(f"\n  📂 {result['user_dir']}/ ({result['total_change_tweets']} tweets)")
            for file_type, filepath in result['files_created'].items():
                if filepath:
                    filename = Path(filepath).name
                    print(f"    - {filename}")
    
    if failed:
        print(f"\n❌ FAILED URLS:")
        for result in failed:
            print(f"  - {result['url']}: {result['error']}")
    
    total_tweets = sum(r.get('total_change_tweets', 0) for r in successful)
    print(f"\n🎉 GRAND TOTAL: {total_tweets} tweets generated!")
    print(f"📂 Check the 'users/' directory for all generated files")

async def test_single_url():
    """Test with a single URL (for compatibility)."""
    if WORKFLOWY_URLS:
        url_config = WORKFLOWY_URLS[0]
        
        async with WorkflowyTester() as tester:
            await tester.process_single_url(
                url_config,
                exclude_node_names=["SpikyPOVs", "Private Notes"]
            )
    else:
        print("❌ No URLs configured in WORKFLOWY_URLS")

if __name__ == "__main__":
    print("Workflowy Scraper Test")
    print("=====================")
    
    # Choose which test to run:
    
    # Process all configured URLs
    asyncio.run(test_multiple_workflowy_urls())
    
    # Or process just the first URL
    # asyncio.run(test_single_url())