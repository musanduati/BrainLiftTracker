"""
Main WorkflowyTesterV2 class - orchestrates all scraping operations
"""

import json
import re
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime

from workflowy.config.logger import logger
from workflowy.storage.aws_storage import AWSStorageV2
from workflowy.storage.project_utils import normalize_project_id
from workflowy.core.llm_service import extract_node_id_using_llm, get_lm_service

# Import from scraper submodules
from .models import WorkflowyNode
from .content_processing import _clean_html_content, _extract_node_content
from .dok_parser import (
    parse_dok_points, 
    get_timestamp,
    create_dok_state_from_points,
    advanced_compare_dok_states
)
from .tweet_generation import generate_advanced_change_tweets
from .api_utils import (
    WORKFLOWY_URL,
    extract_share_id,
    make_request,
    get_tree_data,
    get_initial_data,
    extract_top_level_nodes,
    filter_nodes_llm
)


async def extract_single_dok_section_llm(item_data_list: list[dict[str, str]], section_prefix: str) -> str:
    """
    Extract a single DOK section using LLM-based identification.
    """
    logger.info(f"🔍 Extracting {section_prefix} section...")
    
    # Get top-level nodes first
    top_nodes = await extract_top_level_nodes(item_data_list)
    
    # If there's only one top-level node (root), get its children instead
    nodes_for_llm = []
    if len(top_nodes) == 1:
        root_id = top_nodes[0]['id']
        logger.info(f"Found single root node: {top_nodes[0]['name']}, looking for children...")
        
        # Get children of the root node
        for item in item_data_list:
            if item.get('prnt') == root_id:
                node_name = _clean_html_content(item.get('nm', '').strip())
                if node_name:
                    nodes_for_llm.append({
                        'name': node_name,
                        'id': item['id']
                    })
                    logger.debug(f"Found child node: {node_name} (ID: {item['id']})")
    else:
        # Multiple top-level nodes, use them directly
        nodes_for_llm = top_nodes
    
    logger.info(f"Found main nodes: {nodes_for_llm}")
    
    # Use LLM to find the correct node ID
    node_id = await extract_node_id_using_llm(section_prefix, nodes_for_llm)
    
    if not node_id:
        logger.warning(f"⚠️ Could not find {section_prefix} section")
        return ""
    
    logger.info(f"✅ Found {section_prefix} with node_id: {node_id}")
    
    # Extract content for this node
    return _extract_node_content(item_data_list, node_id, section_prefix)


class WorkflowyTesterV2:
    """
    Updated WorkflowyTester using project-based identification.
    Eliminates dependency on URL-derived parameters for user identification.
    """
    
    WORKFLOWY_URL = WORKFLOWY_URL
    
    def __init__(self, environment: str = 'test'):
        self.storage = AWSStorageV2(environment)
        self.environment = environment
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookie_jar = aiohttp.CookieJar()
        self.auth_headers = None
        self.lm_service = get_lm_service()
        logger.info(f"🚀 Initialized WorkflowyTesterV2 for {environment}")
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with cookie jar."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                cookie_jar=self.cookie_jar,
                headers=self.auth_headers or {}
            )
        return self.session
    
    async def extract_share_id(self, url: str) -> tuple[str, str]:
        """Extract session ID and share ID from Workflowy URL."""
        session = await self.get_session()
        return await extract_share_id(session, url)
    
    async def scrape_workflowy_raw_data(self, url: str, exclude_node_names: list[str] | None = None) -> list[dict[str, str]]:
        """Scrape raw data from Workflowy URL."""
        try:
            session_id, share_id = await self.extract_share_id(url)
            
            session = await self.get_session()
            items = await get_tree_data(session, session_id, share_id, exclude_node_names)
            
            logger.info(f"Retrieved {len(items)} items from Workflowy")
            return items
            
        except Exception as e:
            logger.error(f"Error scraping Workflowy: {e}")
            raise
    
    async def process_single_project(self, project_id: str, exclude_node_names: list[str] | None = None):
        """
        Process a single project using project_id for identification.
        """
        logger.info(f"🔄 Processing project: {project_id}")
        
        # Get project configuration
        project_config = self.storage.get_project_by_id(project_id)
        if not project_config:
            logger.error(f"❌ Project not found: {project_id}")
            return None
        
        if not project_config.get('active', True):
            logger.info(f"⏸️ Project {project_id} is inactive, skipping")
            return None
        
        url = project_config.get('url')
        if not url:
            logger.error(f"❌ No URL found for project: {project_id}")
            return None
        
        project_name = project_config.get('name', project_id)
        logger.info(f"📋 Project: {project_name} ({project_id})")
        logger.info(f"🔗 URL: {url}")
        
        # Check if this is the first run for this project
        is_first_run = self.storage.is_first_run(project_id)
        logger.info(f"🏁 First run: {is_first_run}")
        
        # Load previous state if exists
        previous_state = None if is_first_run else self.storage.load_previous_state(project_id)
        
        try:
            # Scrape raw data from Workflowy
            raw_data = await self.scrape_workflowy_raw_data(url, exclude_node_names)
            
            # Extract DOK sections with LLM-based identification
            dok4_content = await extract_single_dok_section_llm(raw_data, "DOK4")
            dok3_content = await extract_single_dok_section_llm(raw_data, "DOK3")
            
            # Process DOK sections
            all_tweets = []
            # Always initialize current_state with both keys (lowercase)
            current_state = {
                'dok4': [],  # Always include, even if empty
                'dok3': []   # Always include, even if empty
            }
            
            # Process DOK4 section
            if dok4_content:
                logger.info("📝 Processing DOK4 section...")
                dok4_points = parse_dok_points(dok4_content, "DOK4")
                current_state['dok4'] = create_dok_state_from_points(dok4_points)  # Use lowercase key
                
                # Only generate tweets if NOT first run
                if not is_first_run:
                    # Compare with previous state
                    prev_dok4_state = previous_state.get('dok4', []) if previous_state else []
                    changes = advanced_compare_dok_states(prev_dok4_state, current_state['dok4'])
                    dok4_tweets = generate_advanced_change_tweets(changes, "DOK4", is_first_run=False)
                    all_tweets.extend(dok4_tweets)
                    logger.info(f"✅ Generated {len(dok4_tweets)} tweets for DOK4")
                else:
                    logger.info("🏁 First run - establishing DOK4 baseline, no tweets generated")
            else:
                logger.info("⚠️ No DOK4 content found")
            
            # Process DOK3 section
            if dok3_content:
                logger.info("📝 Processing DOK3 section...")
                dok3_points = parse_dok_points(dok3_content, "DOK3")
                current_state['dok3'] = create_dok_state_from_points(dok3_points)  # Use lowercase key
                
                # Only generate tweets if NOT first run
                if not is_first_run:
                    # Compare with previous state
                    prev_dok3_state = previous_state.get('dok3', []) if previous_state else []
                    changes = advanced_compare_dok_states(prev_dok3_state, current_state['dok3'])
                    dok3_tweets = generate_advanced_change_tweets(changes, "DOK3", is_first_run=False)
                    all_tweets.extend(dok3_tweets)
                    logger.info(f"✅ Generated {len(dok3_tweets)} tweets for DOK3")
                else:
                    logger.info("🏁 First run - establishing DOK3 baseline, no tweets generated")
            else:
                logger.info("⚠️ No DOK3 content found")
            
            # Save results
            timestamp = get_timestamp()
            
            # Save scraped content
            combined_content = f"# {project_name}\n\n{dok4_content}\n\n{dok3_content}"
            s3_scraped_path = self.storage.save_scraped_content(project_id, combined_content, timestamp)
            logger.info(f"💾 Saved scraped content to: {s3_scraped_path}")
            
            # Save tweets if any
            s3_tweets_path = None  # Initialize variable
            if all_tweets:
                s3_tweets_path = self.storage.save_change_tweets(project_id, all_tweets, timestamp)
                logger.info(f"💾 Saved {len(all_tweets)} tweets to: {s3_tweets_path}")
            
            # Save current state for next comparison
            self.storage.save_current_state(project_id, current_state)
            logger.info(f"💾 Updated state for project: {project_id}")
            
            # Cleanup old content
            self.storage.cleanup_old_scraped_content(project_id)
            
            # Return with the expected fields for lambda_handler
            return {
                'project_id': project_id,
                'project_name': project_name,
                'status': 'success',  # Add status field
                'total_change_tweets': len(all_tweets),  # Use expected field name
                'tweets_generated': len(all_tweets),  # Keep for backward compatibility
                'is_first_run': is_first_run,
                'scraped_path': s3_scraped_path,
                'tweets_path': s3_tweets_path,
                'timestamp': timestamp
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing project {project_id}: {e}")
            return {
                'project_id': project_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def process_all_projects(self, exclude_node_names: list[str] | None = None):
        """
        Process all active projects in the system.
        """
        logger.info("🚀 Starting processing of all active projects...")
        
        # Get all active projects
        projects = self.storage.get_all_projects()
        active_projects = [p for p in projects if p.get('active', False)]
        
        logger.info(f"📊 Found {len(active_projects)} active projects to process")
        
        results = []
        for project in active_projects:
            project_id = project['project_id']
            try:
                result = await self.process_single_project(project_id, exclude_node_names)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"❌ Failed to process project {project_id}: {e}")
                results.append({
                    'project_id': project_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        logger.info(f"✅ Processed {len(results)} projects")
        return results
    
    async def __aenter__(self):
        self.session = await self.get_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None
    
    async def make_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Makes an async HTTP request with retry logic."""
        session = await self.get_session()
        return await make_request(session, method, url, **kwargs)
    
    async def filter_nodes_llm(self, nodes, exclude_names):
        """Recursively filter out nodes using LLM-based identification."""
        return await filter_nodes_llm(nodes, exclude_names)
    
    async def get_tree_data(self, session_id: str, share_id: str | None = None, exclude_node_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Fetch tree data from Workflowy."""
        session = await self.get_session()
        return await get_tree_data(session, session_id, share_id, exclude_node_names)
    
    async def get_initial_data(self, session_id: str, share_id: str) -> list[str]:
        """Get initialization data from Workflowy."""
        session = await self.get_session()
        return await get_initial_data(session, session_id, share_id)
    
    def remove_unnecessary_html_tags(self, content: str) -> str:
        """Remove HTML tags and convert to markdown (legacy method name for compatibility)."""
        return _clean_html_content(content)
    
    def node_to_markdown(self, node: dict[str, Any], breadcrumb: str = "", level: int = 0) -> str:
        """Convert node to markdown format (legacy method for compatibility)."""
        markdown = "  " * level
        node_name = self.remove_unnecessary_html_tags(node.get("nm", ""))
        
        if level == 0:
            if breadcrumb:
                markdown += f"# {breadcrumb} > {node_name}\n"
            else:
                markdown += f"# {node_name}\n"
        else:
            markdown += f"- {node_name}\n"
        
        # Add note if present
        if node.get("no"):
            note = self.remove_unnecessary_html_tags(node["no"])
            markdown += "  " * level + f"  {note}\n"
        
        # Process children
        if node.get("ch"):
            for child in node["ch"]:
                child_breadcrumb = f"{breadcrumb} > {node_name}" if breadcrumb else node_name
                markdown += self.node_to_markdown(child, child_breadcrumb, level + 1)
        
        return markdown
    
    def url_to_markdown(self, data: list[dict[str, Any]], is_breadcrumb_format: bool = True) -> WorkflowyNode:
        """Convert URL data to markdown format (legacy method for compatibility)."""
        content = ""
        
        # Find root node(s)
        root_nodes = [item for item in data if not item.get("prnt")]
        
        for root in root_nodes:
            if is_breadcrumb_format:
                content += self.node_to_markdown(root)
            else:
                content += self.generate_plain_markdown(root)
        
        # Create WorkflowyNode
        node_id = root_nodes[0]["id"] if root_nodes else "unknown"
        node_name = self.remove_unnecessary_html_tags(root_nodes[0].get("nm", "")) if root_nodes else "Workflowy Content"
        
        return WorkflowyNode(
            node_id=node_id,
            node_name=node_name,
            content=content.strip()
        )
    
    def generate_plain_markdown(self, item: dict[str, Any], level: int = 0) -> str:
        """Generate plain markdown without breadcrumbs (legacy method for compatibility)."""
        markdown = "  " * level + "- " + self.remove_unnecessary_html_tags(item.get("nm", "")) + "\n"
        
        if item.get("no"):
            markdown += "  " * level + "  " + self.remove_unnecessary_html_tags(item["no"]) + "\n"
        
        if item.get("ch"):
            for child in item["ch"]:
                markdown += self.generate_plain_markdown(child, level + 1)
        
        return markdown
    
    def create_workflowy_node_from_raw_data(self, raw_data: list[dict[str, str]]) -> WorkflowyNode:
        """Create WorkflowyNode from raw data (legacy method for compatibility)."""
        return self.url_to_markdown(raw_data, is_breadcrumb_format=False)
    
    async def scrape_workflowy(self, url: str, exclude_node_names: list[str] | None = None) -> WorkflowyNode:
        """
        Main entry point to scrape a Workflowy URL (legacy method for compatibility).
        """
        raw_data = await self.scrape_workflowy_raw_data(url, exclude_node_names)
        return self.create_workflowy_node_from_raw_data(raw_data)


# For testing
async def test_project_processing():
    """Test processing a single project."""
    logger.info("Testing project processing...")
    
    async with WorkflowyTesterV2(environment='test') as tester:
        # Test with a specific project ID
        result = await tester.process_single_project('wfx-test-1234')
        if result:
            logger.info(f"✅ Test successful: {result}")
        else:
            logger.error("❌ Test failed")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_project_processing())
