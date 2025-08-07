"""
Content processing utilities for Workflowy data
"""

import re
import html
from typing import Optional

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
    def get_node_by_id(target_id: str) -> Optional[dict]:
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
