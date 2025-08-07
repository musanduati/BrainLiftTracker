"""
API and network utilities for Workflowy interactions
"""

import re
import json
import aiohttp
from typing import Optional, Dict, Any, List, Tuple
from workflowy.config.logger import logger
from workflowy.core.scraper.models import InitializationData
from workflowy.core.llm_service import extract_node_id_using_llm

WORKFLOWY_URL = "https://workflowy.com"
LOGIN_URL = f"{WORKFLOWY_URL}/ajax_login"


async def extract_share_id(session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
    """
    Extract session ID and share ID from Workflowy URL.
    
    Args:
        session: aiohttp session to use for request
        url: Workflowy URL to extract from
        
    Returns:
        Tuple of (session_id, share_id)
    """
    try:
        # Make HTTP request to get session and real share_id
        response = await session.get(url)
        response.raise_for_status()
        html_text = await response.text()
        
        cookie = response.cookies.get("sessionid")
        if not cookie:
            raise Exception("No cookie found in response headers.")

        match = re.search(r"PROJECT_TREE_DATA_URL_PARAMS = (\{.*?\});", html_text)
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            session_id = str(cookie.value)
            share_id = data.get("share_id")
            logger.debug(f"Extracted session_id: {session_id[:20]}..., share_id: {share_id} from URL: {url}")
            return session_id, share_id
        else:
            raise Exception("No match found for PROJECT_TREE_DATA_URL_PARAMS.")
            
    except Exception as e:
        logger.error(f"Error extracting session and share_id from URL {url}: {e}")
        raise


async def make_request(session: aiohttp.ClientSession, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
    """
    Makes an async HTTP request with retry logic.
    
    Args:
        session: aiohttp session to use
        method: HTTP method
        url: URL to request
        **kwargs: Additional request parameters
        
    Returns:
        aiohttp.ClientResponse
    """
    timeout = kwargs.pop("timeout", None)
    if isinstance(timeout, int | float):
        timeout = aiohttp.ClientTimeout(total=timeout)
    if timeout is not None:
        kwargs["timeout"] = timeout

    response = await session.request(method, url, **kwargs)
    response.raise_for_status()
    return response


async def get_tree_data(
    session: aiohttp.ClientSession,
    session_id: str, 
    share_id: Optional[str] = None, 
    exclude_node_names: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch tree data from Workflowy.
    
    Args:
        session: aiohttp session to use
        session_id: Workflowy session ID
        share_id: Optional share ID
        exclude_node_names: Optional list of node names to exclude
        
    Returns:
        List of tree data items
    """
    if not session_id:
        raise ValueError("No sessionId provided.")

    url = f"{WORKFLOWY_URL}/get_tree_data/"
    if share_id:
        url += f"?share_id={share_id}"
    
    logger.info(f"Getting tree data from {url}")

    response = await make_request(
        session, "GET", url, 
        headers={"Cookie": f"sessionid={session_id}"}, 
        timeout=10
    )
    data = await response.json()
    items = data.get("items", [])

    if exclude_node_names:
        filtered_items = await filter_nodes_llm(items, exclude_node_names)
    else:
        filtered_items = items

    return filtered_items


async def get_initial_data(
    session: aiohttp.ClientSession,
    session_id: str, 
    share_id: str
) -> List[str]:
    """
    Get initialization data from Workflowy.
    
    Args:
        session: aiohttp session to use
        session_id: Workflowy session ID
        share_id: Share ID
        
    Returns:
        List of auxiliary project share IDs
    """
    url = f"{WORKFLOWY_URL}/get_initialization_data?share_id={share_id}&client_version=21&client_version_v2=28&no_root_children=1&include_main_tree=1"
    
    response = await make_request(
        session, "GET", url, 
        headers={"Cookie": f"sessionid={session_id}"}, 
        timeout=10
    )
    data = await response.json()
    return InitializationData(**data).transform()


async def extract_top_level_nodes(item_data_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Extract top-level nodes from item data for LLM identification.
    
    Args:
        item_data_list: List of items from Workflowy
        
    Returns:
        List of top-level nodes with name and ID
    """
    # Import here to avoid circular dependency
    from workflowy.core.scraper.content_processing import _clean_html_content
    
    logger.info("Extracting top-level nodes for LLM identification...")
    top_nodes = []
    
    # Find root or nodes without parent
    for item in item_data_list:
        # Top-level nodes are those without 'prnt' field or with prnt as None/empty
        if not item.get('prnt'):
            node_name = _clean_html_content(item.get('nm', '').strip())
            if node_name:  # Only add if there's a name
                node_info = {
                    'name': node_name,
                    'id': item['id']
                }
                top_nodes.append(node_info)
                logger.debug(f"Found top-level node: {node_name} (ID: {item['id']})")
    
    logger.info(f"Found {len(top_nodes)} top-level nodes")
    return top_nodes


async def filter_nodes_llm(nodes: List[Dict], exclude_names: List[str]) -> List[Dict]:
    """
    Recursively filter out nodes using LLM-based identification.
    
    Args:
        nodes: List of nodes to filter
        exclude_names: List of node names to exclude
        
    Returns:
        Filtered list of nodes
    """
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
