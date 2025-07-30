"""
LLM Service Module

This module contains all LLM-related functionality including:
- OpenAI API integration
- Node identification using LLM
- Fallback pattern matching
- Request/response models
"""

import ast
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Dict

import aiohttp

# Setup logger
logger = logging.getLogger("workflowy_llm")
logger.setLevel(logging.DEBUG)


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
            logger.debug("Exact match found: %s -> %s", node_name, node['id'])
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
                        logger.debug("Pattern match found: %s (%s) -> %s", node_name, variation, node['id'])
                        return node['id']
        
        # Direct substring matching as final fallback
        if node_name_lower in clean_node_name or clean_node_name in node_name_lower:
            logger.debug("Substring match found: %s -> %s", node_name, node['id'])
            return node['id']
    
    logger.warning("Could not find node ID for: %s in nodes: %s", node_name, [clean_name(n['name']) for n in nodes])
    return None


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
            logger.warning("OPENAI_API_KEY not found in environment. Will fall back to pattern matching.")

    async def generate_simple_text_using_slm(self, request: GenerateSimpleTextRequest) -> str:
        """
        Generate simple text using OpenAI REST API.
        """
        lm_type = getattr(request, 'lm_type', self.default_model)
        logger.info("Generating text using OpenAI model: %s", lm_type)

        # If no API key, fall back immediately
        if not self.openai_api_key:
            logger.warning("No OpenAI API key, falling back to pattern matching")
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
                logger.info("OpenAI LLM response: %s", result)
                return result.strip()
            else:
                logger.warning("Empty response from OpenAI, falling back to pattern matching")
                return self._fallback_to_pattern_matching(request.query)

        except Exception as e:
            logger.error("OpenAI API call failed: %s, falling back to pattern matching", e)
            return self._fallback_to_pattern_matching(request.query)

    async def _call_openai_rest(self, messages: list[dict], lm_type: str) -> str:
        """Call OpenAI API using REST/HTTP requests"""
        
        # Map lm_type to actual OpenAI model names
        model_map = {
            'openai-4om': 'gpt-4o-mini',
            'openai-4o': 'gpt-4o',
            'gpt-4o-mini': 'gpt-4o-mini',
            'gpt-4o': 'gpt-4o',
        }
        model = model_map.get(lm_type, self.default_model)
        
        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 100,
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
                    logger.error(f"OpenAI API error {response.status}: {error_text}")
                    raise Exception(f"OpenAI API returned {response.status}: {error_text}")

    def _fallback_to_pattern_matching(self, query: str) -> str:
        """Fallback to pattern matching when LLM fails"""
        try:
            # Extract node name and nodes from query
            query_lines = query.split('\n')
            if len(query_lines) >= 2:
                node_to_find = query_lines[0].replace("Node to find: ", "").strip()
                nodes_str = query_lines[1].replace("List of nodes: ", "").strip()
                
                nodes = ast.literal_eval(nodes_str)
                
                # Use the existing fallback logic
                result = _fallback_node_matching(node_to_find, nodes)
                logger.info("Fallback pattern matching returned: %s", result)
                return result or ""
        except Exception as e:
            logger.error("Fallback pattern matching also failed: %s", e)
        
        return ""

    async def _perform_single_inference(self, messages: list[dict], lm_type: str) -> str:
        """Single inference method for compatibility"""
        request = GenerateSimpleTextRequest(
            query=messages[-1]["content"] if messages else "",
            lm_type=lm_type,
            custom_instructions=messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        )
        return await self.generate_simple_text_using_slm(request)


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
        query = f"Node to find: {node_name} \n List of nodes: {nodes}"
        print(f"Query: {query}")
        
        # Use actual LLM service integration 
        request = GenerateSimpleTextRequest(
            query=query, 
            lm_type="gpt-4o-mini", 
            custom_instructions=EXTRACT_BRAINLIFT_NODE_ID_PROMPT
        )
        response = await lm_service_instance.generate_simple_text_using_slm(request)
        
        # If LLM returns a valid response, use it; otherwise fall back
        if response and response.strip():
            logger.debug("LLM found node ID: %s for node: %s", response, node_name)
            return response.strip()
        else:
            logger.debug("LLM returned empty response, using fallback for node: %s", node_name)
            return _fallback_node_matching(node_name, nodes)
        
    except Exception as e:
        logger.error("Error parsing brainlift content using LLM: %s", e)
        return _fallback_node_matching(node_name, nodes)


# Global LLM service instance
_lm_service_instance = None


def get_lm_service() -> LMService:
    """Get or create the global LMService instance."""
    global _lm_service_instance
    if _lm_service_instance is None:
        _lm_service_instance = LMService()
    return _lm_service_instance


# For backward compatibility
lm_service = get_lm_service()
