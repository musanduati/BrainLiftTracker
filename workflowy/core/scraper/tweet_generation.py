"""
Tweet generation utilities for DOK content changes
"""

import re
from datetime import datetime
from typing import List, Dict
from workflowy.config.logger import logger


def create_combined_content(main_content: str, sub_points: List[str]) -> str:
    """
    Combine main point with sub-points into one text block.
    
    Args:
        main_content: Main content text
        sub_points: List of sub-points
        
    Returns:
        Combined content string
    """
    combined = main_content
    
    if sub_points:
        for sub_point in sub_points:
            combined += f" {sub_point}"
    
    return combined.strip()


def split_content_for_twitter(content: str, max_chars: int = 230) -> List[str]:
    """
    Split content into Twitter-sized chunks at sentence boundaries.
    Leaves room for thread indicators and formatting.
    
    Args:
        content: Content to split
        max_chars: Maximum characters per chunk
        
    Returns:
        List of content chunks
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


def generate_advanced_change_tweets(changes: Dict, section: str, is_first_run: bool = False) -> List[Dict]:
    """
    Generate tweets with advanced change detection information.
    
    Args:
        changes: Dictionary containing added/updated/deleted changes
        section: Section name (e.g., "DOK4", "DOK3")
        is_first_run: Whether this is the first run for the project
        
    Returns:
        List of tweet dictionaries with formatted content
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
