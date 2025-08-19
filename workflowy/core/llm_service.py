"""
LLM Service Module

This module contains all LLM-related functionality including:
- OpenAI API integration
- Node identification using LLM
- Fallback pattern matching
- Request/response models
"""

import ast
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Dict
import aiohttp
from workflowy.config.logger import structured_logger

def _fallback_node_matching(node_name: str, nodes: list[dict[str, str]]) -> str | None:
    """
    Improved fallback fuzzy matching logic for node identification.
    Now handles HTML tags and better pattern matching.
    """
    node_name_lower = node_name.lower().strip()
    
    # Direct mapping for common variations (improved)
    node_mappings = {
        'dok4': ['spiky pov', 'spov', 'dok4', 'dok 4', 'spiky point of views', 'spiky points of view', 'spikey pov', 'spikey povs'],
        'spikypovs': ['spiky pov', 'spov', 'dok4', 'dok 4', 'spiky point of views', 'spiky points of view', 'spikey pov', 'spikey povs'],
        'experts': ['expert', 'experts', 'thought leader'],
        'dok3': ['dok3', 'dok 3', 'insight', 'insights'],
        'insights': ['dok3', 'dok 3', 'insight', 'insights'],
        'purpose': ['purpose'],
        'owner': ['owner'],
        'dok2': ['dok2', 'dok 2', 'knowledge tree', 'categories', 'category'],
        'knowledge tree': ['dok2', 'dok 2', 'knowledge tree', 'categories', 'category'],
        'categories': ['dok2', 'dok 2', 'knowledge tree', 'categories', 'category']
    }
    
    # Helper function to clean node names (remove HTML tags)
    def clean_name(name: str) -> str:
        # Remove HTML tags like <b>, </b>, etc.
        clean = re.sub(r'<[^>]+>', '', name)
        # Remove extra whitespace and convert to lowercase
        return clean.strip().lower()
    
    # First try exact matching on cleaned names
    for node in nodes:
        clean_node_name = clean_name(node['name'])
        if clean_node_name == node_name_lower:
            structured_logger.debug_operation("_fallback_node_matching", f"Exact match found: {node_name} -> {node['id']}")
            return node['id']
    
    # Then try fuzzy matching using mappings
    for node in nodes:
        clean_node_name = clean_name(node['name'])
        
        # Check if the node_name matches any known pattern
        for canonical_name, variations in node_mappings.items():
            if node_name_lower in variations or canonical_name == node_name_lower:
                # Check if current node matches any variation of this canonical name
                for variation in variations:
                    if variation in clean_node_name:
                        structured_logger.debug_operation("_fallback_node_matching", f"Pattern match found: {node_name} ({variation}) -> {node['id']}")
                        return node['id']
        
        # Direct substring matching as final fallback
        if node_name_lower in clean_node_name or clean_node_name in node_name_lower:
            structured_logger.debug_operation("_fallback_node_matching", f"Substring match found: {node_name} -> {node['id']}")
            return node['id']
    
    structured_logger.warning_operation("_fallback_node_matching", f"Could not find node ID for: {node_name} in nodes: {[clean_name(n['name']) for n in nodes]}")
    return None

def _fallback_find_all_matching_nodes(node_name: str, nodes: list[dict[str, str]]) -> list[str]:
    """
    Fallback fuzzy matching logic for finding ALL nodes that match the requested type.
    Returns list of all matching node IDs.
    """
    try:
        structured_logger.debug_operation("_fallback_find_all_matching_nodes", f"Starting fallback matching for: {repr(node_name)}")
        structured_logger.debug_operation("_fallback_find_all_matching_nodes", f"Nodes input type: {type(nodes)}, length: {len(nodes)}")
        
        # Validate input parameters
        if not isinstance(node_name, str):
            structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Invalid node_name type: {type(node_name)}, value: {repr(node_name)}")
            return []
            
        if not isinstance(nodes, list):
            structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Invalid nodes type: {type(nodes)}, value: {repr(nodes)}")
            return []
        
        node_name_lower = node_name.lower().strip()
        matching_node_ids = []
        
        # Direct mapping for common variations (same as existing)
        node_mappings = {
            'dok4': ['spiky pov', 'spov', 'dok4', 'dok 4', 'spiky point of views', 'spiky points of view', 'spikey pov', 'spikey povs'],
            'spikypovs': ['spiky pov', 'spov', 'dok4', 'dok 4', 'spiky point of views', 'spiky points of view', 'spikey pov', 'spikey povs'],
            'experts': ['expert', 'experts', 'thought leader'],
            'dok3': ['dok3', 'dok 3', 'insight', 'insights'],
            'insights': ['dok3', 'dok 3', 'insight', 'insights'],
            'purpose': ['purpose'],
            'owner': ['owner'],
            'dok2': ['dok2', 'dok 2', 'knowledge tree', 'categories', 'category'],
            'knowledge tree': ['dok2', 'dok 2', 'knowledge tree', 'categories', 'category'],
            'categories': ['dok2', 'dok 2', 'knowledge tree', 'categories', 'category']
        }
        
        # Helper function to clean node names (same as existing)
        def clean_name(name: str) -> str:
            try:
                clean = re.sub(r'<[^>]+>', '', name)
                return clean.strip().lower()
            except Exception as e:
                structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Error cleaning name {repr(name)}: {e}")
                return str(name).lower()  # Fallback
        
        # First pass: exact matching
        for i, node in enumerate(nodes):
            try:
                if not isinstance(node, dict):
                    structured_logger.warning_operation("_fallback_find_all_matching_nodes", f"Node {i} is not a dict: {type(node)}, value: {repr(node)}")
                    continue
                    
                if 'name' not in node or 'id' not in node:
                    structured_logger.warning_operation("_fallback_find_all_matching_nodes", f"Node {i} missing required keys: {node.keys()}")
                    continue
                
                node_name_raw = node.get('name', '')
                node_id = node.get('id', '')
                
                structured_logger.debug_operation("_fallback_find_all_matching_nodes", f"Processing node {i}: name={repr(node_name_raw)}, id={repr(node_id)}")
                
                clean_node_name = clean_name(node_name_raw)
                if clean_node_name == node_name_lower:
                    structured_logger.debug_operation("_fallback_find_all_matching_nodes", f"Exact match found: {node_name} -> {node_id}")
                    matching_node_ids.append(node_id)
                    
            except Exception as e:
                structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Error processing node {i}: {type(e).__name__}: {e}")
                structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Problem node: {repr(node)}")
                continue
        
        # Second pass: fuzzy matching using mappings (only if no exact matches)
        if not matching_node_ids:
            for i, node in enumerate(nodes):
                try:
                    if not isinstance(node, dict) or 'name' not in node or 'id' not in node:
                        continue
                        
                    node_name_raw = node.get('name', '')
                    node_id = node.get('id', '')
                    clean_node_name = clean_name(node_name_raw)
                    
                    # Check if the node_name matches any known pattern
                    for canonical_name, variations in node_mappings.items():
                        if node_name_lower in variations or canonical_name == node_name_lower:
                            # Check if current node matches any variation of this canonical name
                            for variation in variations:
                                if variation in clean_node_name:
                                    structured_logger.debug_operation("_fallback_find_all_matching_nodes", f"Pattern match found: {node_name} ({variation}) -> {node_id}")
                                    matching_node_ids.append(node_id)
                                    break  # Avoid duplicate matches for same node
                            break  # Move to next node
                                
                except Exception as e:
                    structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Error in fuzzy matching for node {i}: {e}")
                    continue

        # Third pass: substring matching as final fallback (only if no matches yet)
        if not matching_node_ids:
            for i, node in enumerate(nodes):
                try:
                    if not isinstance(node, dict) or 'name' not in node or 'id' not in node:
                        continue
                        
                    node_name_raw = node.get('name', '')
                    node_id = node.get('id', '')
                    clean_node_name = clean_name(node_name_raw)
                    
                    if node_name_lower in clean_node_name or clean_node_name in node_name_lower:
                        structured_logger.debug_operation("_fallback_find_all_matching_nodes", f"Substring match found: {node_name} -> {node_id}")
                        matching_node_ids.append(node_id)
                        
                except Exception as e:
                    structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Error in substring matching for node {i}: {e}")
                    continue
        
        # Remove duplicates while preserving order
        unique_node_ids = []
        for node_id in matching_node_ids:
            if node_id not in unique_node_ids:
                unique_node_ids.append(node_id)
        
        if unique_node_ids:
            structured_logger.info_operation("_fallback_find_all_matching_nodes", f"Found {len(unique_node_ids)} matching nodes for {node_name}: {unique_node_ids}")
        else:
            structured_logger.warning_operation("_fallback_find_all_matching_nodes", f"Could not find any nodes for: {node_name} in {len(nodes)} available nodes")
        
        return unique_node_ids
        
    except Exception as e:
        structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Critical error in _fallback_find_all_matching_nodes: {type(e).__name__}: {e}")
        structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Node name: {repr(node_name)}")
        structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Nodes: {repr(nodes)[:500]}...")  # Truncated for safety
        import traceback
        structured_logger.error_operation("_fallback_find_all_matching_nodes", f"Full traceback: {traceback.format_exc()}")
        return []  # Safe fallback

@dataclass
class GenerateSimpleTextRequest:
    """Request model for LLM text generation."""
    query: str
    top_k: int = 1
    lm_type: str = "anthropic-haiku3"
    custom_instructions: str = ""
    training_data: Optional[List[Dict]] = None


class LMService:
    """Real LLM Service using OpenAI REST API"""
    
    def __init__(self):
        # Load API key from environment
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # dotenv is optional - continue without it
            pass
        
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.default_model = os.getenv('DEFAULT_LLM_MODEL', 'gpt-4o-mini')
        self.api_base_url = "https://api.openai.com/v1"
        
        if not self.openai_api_key:
            structured_logger.warning_operation("LMService-init", "OPENAI_API_KEY not found in environment. Will fall back to pattern matching.")

    async def generate_simple_text_using_slm(self, request: GenerateSimpleTextRequest) -> str:
        """
        Generate simple text using OpenAI REST API.
        """
        lm_type = getattr(request, 'lm_type', self.default_model)
        structured_logger.info_operation("generate_simple_text_using_slm", f"Generating text using OpenAI model: {lm_type}")

        # If no API key, fall back immediately
        if not self.openai_api_key:
            structured_logger.warning_operation("generate_simple_text_using_slm", "No OpenAI API key, falling back to pattern matching")
            return self._fallback_to_pattern_matching(request.query)

        try:
            # Prepare messages for OpenAI
            if request.custom_instructions:
                messages = [
                    {"role": "system", "content": request.custom_instructions},
                    {"role": "user", "content": request.query}
                ]
            else:
                # Use training data if available, otherwise just the query
                messages = request.training_data or []
                messages.append({"role": "user", "content": request.query})

            # Make REST API call to OpenAI
            result = await self._call_openai_rest(messages, lm_type)
            
            if result:
                structured_logger.info_operation("generate_simple_text_using_slm", f"OpenAI LLM response: {result}")
                return result.strip()
            else:
                structured_logger.warning_operation("generate_simple_text_using_slm", "Empty response from OpenAI, falling back to pattern matching")
                return self._fallback_to_pattern_matching(request.query)

        except Exception as e:
            structured_logger.error_operation("generate_simple_text_using_slm", f"OpenAI API call failed: {e}, falling back to pattern matching")
            return self._fallback_to_pattern_matching(request.query)

    async def _call_openai_rest(self, messages: list[dict], lm_type: str) -> str:
        """Call OpenAI API using REST/HTTP requests"""
        
        # Map lm_type to actual OpenAI model names
        model_map = {
            'gpt-4o-mini': 'gpt-4o-mini',
            'gpt-4o': 'gpt-4o',
        }
        model = model_map.get(lm_type, self.default_model)
        
        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 8192,
            "temperature": 0,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        # Use aiohttp for async HTTP request
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.api_base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    return content
                else:
                    error_text = await response.text()
                    structured_logger.error_operation("_call_openai_rest", f"OpenAI API error {response.status}: {error_text}")
                    raise Exception(f"OpenAI API returned {response.status}: {error_text}")

    def _fallback_to_pattern_matching(self, query: str) -> str:
        """Fallback to pattern matching when LLM fails"""
        try:
            # Extract node name and nodes from query - handle both old and new formats
            query_lines = query.split('\n')
            if len(query_lines) >= 2:
                # Handle both "Node to find:" and "Node type to find:" formats
                first_line = query_lines[0]
                if "Node to find:" in first_line:
                    node_to_find = first_line.replace("Node to find:", "").strip()
                elif "Node type to find:" in first_line:
                    node_to_find = first_line.replace("Node type to find:", "").strip()
                else:
                    structured_logger.warning_operation("_fallback_to_pattern_matching", f"Unknown query format: {first_line}")
                    return ""
                
                # Handle both "List of nodes:" and "list of nodes:" formats  
                second_line = query_lines[1]
                if "List of nodes:" in second_line:
                    nodes_str = second_line.replace("List of nodes:", "").strip()
                elif "list of nodes:" in second_line:
                    nodes_str = second_line.replace("list of nodes:", "").strip()
                else:
                    structured_logger.warning_operation("_fallback_to_pattern_matching", f"Unknown nodes format: {second_line}")
                    return ""
                
                # Parse the nodes safely
                try:
                    nodes = ast.literal_eval(nodes_str)
                except (ValueError, SyntaxError) as e:
                    structured_logger.error_operation("_fallback_to_pattern_matching", f"Failed to parse nodes string: {repr(nodes_str)}, error: {e}")
                    return ""
                
                # Use the existing fallback logic (single node)
                result = _fallback_node_matching(node_to_find, nodes)
                structured_logger.info_operation("_fallback_to_pattern_matching", f"Fallback pattern matching returned: {result}")
                return result or ""
                
        except Exception as e:
            structured_logger.error_operation("_fallback_to_pattern_matching", f"Fallback pattern matching failed: {e}")
        
        return ""


# LLM prompt template for node identification
EXTRACT_BRAINLIFT_NODE_ID_PROMPT = """
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a formatting assistant. Your task is to extract the node id of the node name provided in the input.

Top-level Nodes can be same or different variations with extra information:
   - Owner
   - Purpose
   - DOK4 - SPOV / new knowledge (Potentially labeled differently: "Spiky POV," "SPOV," "Spiky point of views," etc. Always map these variations to the spov field in JSON.)
   - DOK3 - Insights (Potentially labeled differently: "Insights," "DOK3," etc. Map to the insights field in JSON.)
   - Experts
   - DOK2 - Knowledge Tree / Categories (Potentially labeled differently: "Knowledge Tree," "Categories," etc. Map to the knowledge_tree field in JSON.)

Your job is to find the relevant id for the given node name from the list of nodes provided in the input.

<example>
Input:
node to find: experts

list of nodes:
{
  "nodes": [
    {"name": "Owner", "id": "123"},
    {"name": "Purpose", "id": "456"},
    {"name": "DOK4 - SPOV / new knowledge", "id": "789"},
    {"name": "DOK3 - Insights", "id": "101"},
    {"name": "Experts", "id": "102"},
    {"name": "DOK2 - Knowledge Tree / Categories", "id": "103"},
  ]
}

Output:
102
</example>

<example>
Input:
node to find: spiky point of views

list of nodes:
{
  "nodes": [
    {"name": "Owner", "id": "123"},
    {"name": "Purpose", "id": "456"},
    {"name": "DOK4 - SPOV / new knowledge", "id": "789"},
    {"name": "DOK3 - Insights", "id": "101"},
    {"name": "Experts", "id": "102"},
  ]
}

Output:
789
</example>

Provide the output as a one piece of text.
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

# LLM prompt template for finding ALL matching nodes
EXTRACT_ALL_BRAINLIFT_NODE_IDS_PROMPT = """
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a formatting assistant. Your task is to find ALL node IDs that match the requested node type.

Top-level Nodes can have same or different variations with extra information:
   - Owner
   - Purpose
   - DOK4 - SPOV / new knowledge (Potentially labeled differently: "Spiky POV," "SPOV," "Spiky point of views," "SpikyPOVs," etc.)
   - DOK3 - Insights (Potentially labeled differently: "Insights," "DOK3," etc.)
   - Experts
   - DOK2 - Knowledge Tree / Categories (Potentially labeled differently: "Knowledge Tree," "Categories," etc.)

Your job is to find ALL node IDs that match the requested node type. Return them as a comma-separated list.

<example>
Input:
Node type to find: DOK4

list of nodes:
[
  {"name": "Owner", "id": "123"},
  {"name": "Purpose", "id": "456"},
  {"name": "DI SpikyPOVs", "id": "789"},
  {"name": "DOK3 - Insights", "id": "101"},
  {"name": "Experts", "id": "102"},
  {"name": "Spiky POV for Texas Prep", "id": "103"},
]

Output:
789,103
</example>

<example>
Input:
Node type to find: DOK3

list of nodes:
[
  {"name": "Owner", "id": "123"},
  {"name": "Purpose", "id": "456"},
  {"name": "DOK4 - SPOV", "id": "789"},
  {"name": "Insights", "id": "101"},
  {"name": "DOK3 - Analysis", "id": "102"},
]

Output:
101,102
</example>

Return ONLY the comma-separated node IDs. If no matches found, return empty string.
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""


async def extract_node_id_using_llm(
    node_name: str, 
    nodes: list[dict[str, str]], 
    lm_service_instance: Optional['LMService'] = None
) -> Optional[str]:
    """
    Extract node ID using LLM-based fuzzy matching.
    
    Args:
        node_name: Name of the node to find (e.g., "SpikyPOVs", "Experts")
        nodes: List of node dictionaries with 'name' and 'id' keys
        lm_service_instance: Optional LMService instance to use
        
    Returns:
        str: Node ID if found, None otherwise
    """
    # Use provided instance or create a new one
    if lm_service_instance is None:
        lm_service_instance = get_lm_service()
    
    try:
        structured_logger.info_operation("extract_node_id_using_llm", f"Extracting node ID for: {node_name}")
        structured_logger.info_operation("extract_node_id_using_llm", f"Nodes: {nodes}")
        query = f"Node to find: {node_name} \n List of nodes: {nodes}"

        # Use actual LLM service integration 
        request = GenerateSimpleTextRequest(
            query=query, 
            lm_type="gpt-4o", 
            custom_instructions=EXTRACT_BRAINLIFT_NODE_ID_PROMPT
        )
        response = await lm_service_instance.generate_simple_text_using_slm(request)
        
        # If LLM returns a valid response, use it; otherwise fall back
        if response and response.strip():
            structured_logger.debug_operation("extract_node_id_using_llm", f"LLM found node ID: {response} for node: {node_name}")
            return response.strip()
        else:
            structured_logger.debug_operation("extract_node_id_using_llm", f"LLM returned empty response, using fallback for node: {node_name}")
            return _fallback_node_matching(node_name, nodes)
        
    except Exception as e:
        structured_logger.error_operation("extract_node_id_using_llm", f"Error parsing brainlift content using LLM: {e}")
        return _fallback_node_matching(node_name, nodes)

async def extract_all_dok_node_ids_using_llm(
    node_name: str, 
    nodes: list[dict[str, str]], 
    lm_service_instance: Optional['LMService'] = None
) -> list[str]:
    """
    Extract ALL node IDs that match the DOK type using LLM-based fuzzy matching.
    
    Args:
        node_name: Name of the node type to find (e.g., "DOK4", "DOK3")
        nodes: List of node dictionaries with 'name' and 'id' keys
        lm_service_instance: Optional LMService instance to use
        
    Returns:
        list[str]: List of all matching node IDs
    """
    try:
        structured_logger.info_operation("extract_all_dok_node_ids_using_llm", f"Extracting ALL node IDs for: {repr(node_name)}")
        structured_logger.info_operation("extract_all_dok_node_ids_using_llm", f"Available nodes: {len(nodes)} nodes")
        
        # Use provided instance or create a new one
        if lm_service_instance is None:
            lm_service_instance = get_lm_service()
        
        # If still None after initialization attempt, use fallback immediately
        if lm_service_instance is None:
            structured_logger.warning_operation("extract_all_dok_node_ids_using_llm", "No LMService available, using fallback pattern matching")
            return _fallback_find_all_matching_nodes(node_name, nodes)
        
        query = f"Node type to find: {node_name} \n list of nodes: {nodes}"

        # Use LLM service integration 
        request = GenerateSimpleTextRequest(
            query=query, 
            lm_type="gpt-4o", 
            custom_instructions=EXTRACT_ALL_BRAINLIFT_NODE_IDS_PROMPT
        )
        response = await lm_service_instance.generate_simple_text_using_slm(request)
        
        # Parse LLM response with comprehensive error handling
        if response and response.strip():
            try:
                raw_response = response.strip()
                structured_logger.debug_operation("extract_all_dok_node_ids_using_llm", f"Raw LLM response for {node_name}: {repr(raw_response)}")
                
                # Check if response looks like it might contain code/eval
                if any(suspicious in raw_response.lower() for suspicious in ['eval', 'exec', 'import', '__', 'lambda']):
                    structured_logger.error_operation("extract_all_dok_node_ids_using_llm", f"Suspicious LLM response detected: {repr(raw_response)}")
                    return _fallback_find_all_matching_nodes(node_name, nodes)
                
                # Handle comma-separated node IDs
                node_ids = []
                for id_part in raw_response.split(','):
                    cleaned_id = id_part.strip()
                    # Basic validation - node IDs should look like UUIDs
                    if cleaned_id and (len(cleaned_id) > 10) and ('-' in cleaned_id or len(cleaned_id) == 32):
                        node_ids.append(cleaned_id)
                    elif cleaned_id:
                        structured_logger.warning_operation("extract_all_dok_node_ids_using_llm", f"Unexpected node ID format from LLM: {repr(cleaned_id)}")
                
                if not node_ids:
                    structured_logger.warning_operation("extract_all_dok_node_ids_using_llm", f"No valid node IDs found in LLM response: {repr(raw_response)}")
                    return _fallback_find_all_matching_nodes(node_name, nodes)
                
                structured_logger.debug_operation("extract_all_dok_node_ids_using_llm", f"Parsed valid node IDs: {node_ids}")
                
                # Validate that returned IDs actually exist in the node list
                valid_node_ids = []
                available_ids = {node['id'] for node in nodes}
                
                for node_id in node_ids:
                    if node_id in available_ids:
                        valid_node_ids.append(node_id)
                    else:
                        structured_logger.warning_operation("extract_all_dok_node_ids_using_llm", f"LLM returned invalid node ID: {node_id}")
                
                if valid_node_ids:
                    structured_logger.info_operation("extract_all_dok_node_ids_using_llm", f"LLM found {len(valid_node_ids)} valid nodes for {node_name}: {valid_node_ids}")
                    return valid_node_ids
                else:
                    structured_logger.debug_operation("extract_all_dok_node_ids_using_llm", f"LLM returned no valid node IDs, using fallback for: {node_name}")
                    return _fallback_find_all_matching_nodes(node_name, nodes)
                
            except Exception as e:
                structured_logger.error_operation("extract_all_dok_node_ids_using_llm", f"Exception parsing LLM response: {type(e).__name__}: {e}")
                structured_logger.error_operation("extract_all_dok_node_ids_using_llm", f"Raw response was: {repr(response)}")
                import traceback
                structured_logger.error_operation("extract_all_dok_node_ids_using_llm", f"Traceback: {traceback.format_exc()}")
                return _fallback_find_all_matching_nodes(node_name, nodes)
        else:
            structured_logger.debug_operation("extract_all_dok_node_ids_using_llm", f"LLM returned empty response, using fallback for: {node_name}")
            return _fallback_find_all_matching_nodes(node_name, nodes)
        
    except Exception as e:
        structured_logger.error_operation("extract_all_dok_node_ids_using_llm", f"TOP-LEVEL ERROR in extract_all_dok_node_ids_using_llm: {type(e).__name__}: {e}")
        structured_logger.warning_operation("extract_all_dok_node_ids_using_llm", "Falling back to pattern matching")
        import traceback
        structured_logger.error_operation("extract_all_dok_node_ids_using_llm", f"Full traceback: {traceback.format_exc()}")
        return _fallback_find_all_matching_nodes(node_name, nodes)

# Global LLM service instance
_lm_service_instance = None


def get_lm_service() -> Optional[LMService]:  # Change return type to Optional
    """Get or create the global LMService instance."""
    global _lm_service_instance
    if _lm_service_instance is None:
        try:
            structured_logger.debug_operation("get_lm_service", "Initializing LMService...")
            _lm_service_instance = LMService()
            structured_logger.debug_operation("get_lm_service", "✅ LMService initialized successfully")
        except Exception as e:
            structured_logger.error_operation("get_lm_service", f"❌ Failed to initialize LMService: {type(e).__name__}: {e}")
            structured_logger.warning_operation("get_lm_service", "Will use fallback pattern matching only")
            import traceback
            structured_logger.error_operation("get_lm_service", f"LMService initialization traceback: {traceback.format_exc()}")
            return None  # Return None on initialization failure
    return _lm_service_instance


# For backward compatibility
lm_service = get_lm_service()
