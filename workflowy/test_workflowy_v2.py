"""
WorkflowyTester V2 - Project-based Content Processing
Updated to use project-based identification instead of URL-derived parameters.
Eliminates dependency on username parsing from URLs.
"""

import json
import asyncio
import aiohttp
import hashlib
import re
import html
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from aws_storage_v2 import AWSStorageV2
from project_id_utils import is_valid_project_id, normalize_project_id
from logger_config import logger
from llm_service import extract_node_id_using_llm, get_lm_service
from test_workflowy import (
    # Import existing utility functions that don't depend on user_name
    extract_single_dok_section_llm,
    parse_dok_points,
    get_timestamp,
    create_dok_state_from_points,
    advanced_compare_dok_states,
    generate_advanced_change_tweets,
    WorkflowyNode,
    InitializationData,
    extract_top_level_nodes
)


class WorkflowyTesterV2:
    """
    Updated WorkflowyTester using project-based identification.
    Eliminates dependency on URL-derived parameters for user identification.
    """
    
    WORKFLOWY_URL = "https://workflowy.com"
    LOGIN_URL = f"{WORKFLOWY_URL}/ajax_login"
    
    def __init__(self, environment: str = 'test'):
        self.session = None
        self.environment = environment
        self.storage = AWSStorageV2(environment)
        
        # LLM service for content processing
        self.lm_service = get_lm_service()
        
        logger.info(f"🔄 WorkflowyTester V2 initialized (Environment: {environment})")
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WorkflowyTester/2.0)"}
            )
        return self.session
    
    async def extract_share_id(self, url: str) -> tuple[str, str]:
        """Extract session ID and share ID from Workflowy URL."""
        try:
            # Make HTTP request to get session and real share_id (same as original)
            response = await self.make_request("GET", url)
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
    
    async def scrape_workflowy_raw_data(self, url: str, exclude_node_names: list[str] | None = None) -> list[dict[str, str]]:
        """Scrape raw data from Workflowy URL."""
        try:
            # Extract REAL session and share IDs (same as original)
            session_id, share_id = await self.extract_share_id(url)
            
            # Get tree data using REAL session_id
            tree_data = await self.get_tree_data(session_id, share_id, exclude_node_names)
            
            if not tree_data:
                logger.warning(f"No tree data found for URL: {url}")
                return []
            
            logger.info(f"✅ Successfully scraped {len(tree_data)} nodes from Workflowy")
            return tree_data
            
        except Exception as e:
            logger.error(f"Error scraping Workflowy raw data from {url}: {e}")
            raise
    
    async def process_single_project(self, project_id: str, exclude_node_names: list[str] | None = None):
        """
        Process a single project using project_id instead of URL parsing.
        
        Args:
            project_id: Project identifier
            exclude_node_names: Node names to exclude from processing
            
        Returns:
            dict: Processing results
        """
        project_id = normalize_project_id(project_id)
        if not project_id:
            error_msg = f"Invalid project_id format: {project_id}"
            logger.error(f"❌ {error_msg}")
            return {
                'project_id': project_id,
                'status': 'error',
                'error': error_msg
            }
        
        # Get project configuration
        project = self.storage.get_project_by_id(project_id)
        if not project:
            error_msg = f"Project not found: {project_id}"
            logger.error(f"❌ {error_msg}")
            return {
                'project_id': project_id,
                'status': 'error',
                'error': error_msg
            }
        
        url = project['url']
        project_name = project['name']
        account_id = project['account_id']
        
        # Check if this is first run using project_id
        first_run = self.storage.is_first_run(project_id)
        timestamp = get_timestamp()
        
        logger.info(f"{'='*60}")
        logger.info(f"PROCESSING PROJECT: {project_id}")
        logger.info(f"NAME: {project_name}")
        logger.info(f"URL: {url}")
        logger.info(f"ACCOUNT: {account_id}")
        logger.info(f"FIRST RUN: {first_run}")
        logger.info(f"TIMESTAMP: {timestamp}")
        logger.info(f"{'='*60}")
        
        try:
            # Load previous state from DynamoDB using project_id
            if first_run:
                logger.info("🆕 First run - no previous state to load")
                previous_state = {"dok4": [], "dok3": []}
            else:
                logger.info("🔄 Loading previous state from DynamoDB...")
                previous_state = self.storage.load_previous_state(project_id)
                logger.info(f"📊 Previous state loaded: {len(previous_state.get('dok4', []))} DOK4, {len(previous_state.get('dok3', []))} DOK3 items")
            
            # Scrape current content
            logger.info("🕷️ Scraping current Workflowy content...")
            raw_data = await self.scrape_workflowy_raw_data(url, exclude_node_names)
            
            if not raw_data:
                error_msg = "No content scraped from URL"
                logger.error(f"❌ {error_msg}")
                return {
                    'project_id': project_id,
                    'status': 'error',
                    'error': error_msg,
                    'url': url
                }
            
            # Convert raw data to markdown (same as original)
            workflowy_node = self.url_to_markdown(raw_data, is_breadcrumb_format=False)
            # Clean HTML tags
            markdown_content = self.remove_unnecessary_html_tags(workflowy_node.content)
            # Save markdown content (not raw JSON)
            content_url = self.storage.save_scraped_content(project_id, markdown_content, timestamp)
            logger.info(f"📄 Raw content saved to: {content_url}")
            
            # Extract DOK4 and DOK3 sections
            logger.info("🔍 Extracting DOK sections...")
            dok4_content = await extract_single_dok_section_llm(raw_data, "dok4")
            dok3_content = await extract_single_dok_section_llm(raw_data, "dok3")
            
            # Parse current content into structured format
            current_dok4_points = parse_dok_points(dok4_content, "DOK4") if dok4_content else []
            current_dok3_points = parse_dok_points(dok3_content, "DOK3") if dok3_content else []
            
            logger.info(f"📊 Current content: {len(current_dok4_points)} DOK4, {len(current_dok3_points)} DOK3 points")
            
            # Create current state
            current_state = {
                "dok4": create_dok_state_from_points(current_dok4_points),
                "dok3": create_dok_state_from_points(current_dok3_points)
            }
            
            # Compare with previous state to detect changes
            all_change_tweets = []
            total_change_tweets = 0
            
            if first_run:
                # First run: just establish baseline, no tweets (same as original)
                logger.info(f"DOK4 Baseline: {len(current_state['dok4'])} points established (no tweets generated)")
                logger.info(f"DOK3 Baseline: {len(current_state['dok3'])} points established (no tweets generated)")
                total_change_tweets = 0
                
            else:
                logger.info("🔍 Comparing with previous state to detect changes...")
                
                # Detect changes for DOK4 (same as original)
                dok4_changes = advanced_compare_dok_states(
                    previous_state.get("dok4", []), 
                    current_state["dok4"]
                )
                logger.info(f"DOK4 Changes: {dok4_changes}")
                dok4_tweets = generate_advanced_change_tweets(dok4_changes, "DOK4", first_run)
                logger.info(f"DOK4 Tweets: {dok4_tweets}")
                all_change_tweets.extend(dok4_tweets)
                
                dok4_stats = dok4_changes.get("stats", {})
                logger.info(f"DOK4 Changes: +{dok4_stats.get('added', 0)} ~{dok4_stats.get('updated', 0)} -{dok4_stats.get('deleted', 0)} ={dok4_stats.get('unchanged', 0)}")
                
                # Detect changes for DOK3 (same as original)
                dok3_changes = advanced_compare_dok_states(
                    previous_state.get("dok3", []), 
                    current_state["dok3"]
                )
                logger.info(f"DOK3 Changes: {dok3_changes}")
                dok3_tweets = generate_advanced_change_tweets(dok3_changes, "DOK3", first_run)
                logger.info(f"DOK3 Tweets: {dok3_tweets}")
                all_change_tweets.extend(dok3_tweets)
                
                dok3_stats = dok3_changes.get("stats", {})
                logger.info(f"DOK3 Changes: +{dok3_stats.get('added', 0)} ~{dok3_stats.get('updated', 0)} -{dok3_stats.get('deleted', 0)} ={dok3_stats.get('unchanged', 0)}")
                
                total_change_tweets = len(all_change_tweets)
                
                if total_change_tweets == 0:
                    logger.info("ℹ️ No changes detected")
                else:
                    logger.info(f"📝 Total changes detected: {total_change_tweets} tweets generated")
            
            # Save change tweets to S3 using project_id
            if all_change_tweets:
                tweets_url = self.storage.save_change_tweets(project_id, all_change_tweets, timestamp)
                logger.info(f"🐦 Change tweets saved to: {tweets_url}")
            
            # Save current state to DynamoDB using project_id
            self.storage.save_current_state(project_id, current_state)
            logger.info("💾 Current state saved to DynamoDB")
            
            return {
                'project_id': project_id,
                'project_name': project_name,
                'account_id': account_id,
                'status': 'success',
                'url': url,
                'timestamp': timestamp,
                'first_run': first_run,
                'total_change_tweets': total_change_tweets,
                'dok4_points': len(current_dok4_points),
                'dok3_points': len(current_dok3_points),
                'content_url': content_url,
                'tweets_url': tweets_url if all_change_tweets else None
            }
            
        except Exception as e:
            error_msg = f"Error processing project {project_id}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'project_id': project_id,
                'status': 'error',
                'error': error_msg,
                'url': url
            }
    
    async def process_all_projects(self, exclude_node_names: list[str] | None = None):
        """
        Process all active projects.
        
        Args:
            exclude_node_names: Node names to exclude from processing
            
        Returns:
            list: Processing results for all projects
        """
        logger.info("📋 Loading all active projects...")
        projects = self.storage.get_all_projects()
        
        if not projects:
            logger.warning("⚠️ No active projects found")
            return []
        
        logger.info(f"📊 Found {len(projects)} active projects to process")
        
        results = []
        for i, project in enumerate(projects, 1):
            project_id = project['project_id']
            project_name = project['name']
            
            logger.info(f"🔄 PROCESSING PROJECT {i}/{len(projects)}: {project_name} ({project_id})")
            
            result = await self.process_single_project(project_id, exclude_node_names)
            results.append(result)
            
            # Add delay between projects to be respectful
            if i < len(projects):
                logger.info(f"⏱️ Waiting 2 seconds before next project...")
                await asyncio.sleep(2)
        
        return results
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

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
        
        logger.info(f"Getting tree data from {url}")

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

    def create_workflowy_node_from_raw_data(self, raw_data: list[dict[str, str]]) -> WorkflowyNode:
        """
        Create a WorkflowyNode from raw data without making HTTP requests.
        This replaces the scrape_workflowy function for efficiency.
        """
        # Convert to markdown (same logic as in scrape_workflowy)
        workflowy_node = self.url_to_markdown(raw_data, is_breadcrumb_format=False)
        
        # Clean HTML tags
        workflowy_node.content = self.remove_unnecessary_html_tags(workflowy_node.content)
        workflowy_node.timestamp = time.time()
        
        return workflowy_node

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


if __name__ == "__main__":
    # Test the new project-based WorkflowyTester
    async def test_project_processing():
        logger.info("Testing WorkflowyTester V2 (Project-based)")
        
        async with WorkflowyTesterV2(environment='test') as tester:
            # Test processing all projects
            results = await tester.process_all_projects()
            
            logger.info(f"📊 Processing results:")
            for result in results:
                status = result['status']
                project_id = result['project_id']
                if status == 'success':
                    tweets = result.get('total_change_tweets', 0)
                    logger.info(f"  ✅ {project_id}: {tweets} change tweets")
                else:
                    error = result.get('error', 'Unknown error')
                    logger.info(f"  ❌ {project_id}: {error}")
    
    asyncio.run(test_project_processing())
