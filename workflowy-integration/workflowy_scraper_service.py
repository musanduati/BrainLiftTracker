import base64
import hashlib
import html
import json
import logging
import re
import time
from typing import Any, Optional

import aiohttp
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# from app.models.pydantic_models import InitializationData, WorkflowyNode
# from app.utils.brain_lift_utils import get_regex_matching_pattern

logger = logging.getLogger("ephor.services.workflowy_scraper")

class AuxiliaryProject(BaseModel):
    shareId: str


class ProjectTreeData(BaseModel):
    auxiliaryProjectTreeInfos: list[AuxiliaryProject]


class InitializationData(BaseModel):
    projectTreeData: ProjectTreeData

    def transform(self) -> list[str]:
        return [info.shareId for info in self.projectTreeData.auxiliaryProjectTreeInfos]

class WorkflowyNode(BaseModel):
    node_id: str
    node_name: str
    content: str
    timestamp: float | None = None

def get_regex_matching_pattern(node_names: list[str] | str) -> re.Pattern:
    if isinstance(node_names, str):
        node_names = [node_names]
    node_names = [name.strip().lower() for name in node_names]
    pattern = r"^\s*[\-:;,.]*\s*(" + "|".join(re.escape(name) for name in node_names) + r")\s*[\-:;,.]*\s*$"
    return re.compile(pattern, re.IGNORECASE)


class WorkflowyScraperService:
    WORKFLOWY_URL = "https://workflowy.com"
    LOGIN_URL = f"{WORKFLOWY_URL}/ajax_login"

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._default_timeout = aiohttp.ClientTimeout(
            total=10,
            connect=10,
            sock_connect=10,
            sock_read=10,
        )  # Default 10s timeout

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._default_timeout)
        return self._session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def make_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        Makes an async HTTP request with retry logic using tenacity.

        Args:
            method: HTTP method to use (GET, POST, etc)
            url: The URL to make the request to
            **kwargs: Additional arguments to pass to aiohttp.ClientSession.request
                     If timeout is provided as int/float, it will be converted to ClientTimeout

        Returns:
            aiohttp.ClientResponse: The HTTP response object for lazy processing

        Raises:
            aiohttp.ClientError: If all retry attempts fail
        """
        # Handle timeout if provided in kwargs
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
        response = await self.make_request("GET", url)
        html_text = await response.text()
        # Get sessionid from cookies
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
        exclude_ids = set()

        # Fix: Pass exclude_names directly instead of individual names
        exclude_patterns = [get_regex_matching_pattern([name]) for name in exclude_names]

        # Or better yet, create one pattern for all names:
        # exclude_pattern = get_regex_matching_pattern(exclude_names)

        def collect_children(parent_id):
            for node in nodes:
                if node["prnt"] == parent_id:
                    exclude_ids.add(node["id"])
                    collect_children(node["id"])

        for node in nodes:
            # Add safety check for missing keys
            node_name = node.get("nm", "").strip()
            # Check if the node name matches any of the exclude patterns
            if node_name and any(pattern.match(node_name) for pattern in exclude_patterns):
                exclude_ids.add(node["id"])
                collect_children(node["id"])

        # Filter out the nodes with the specified names
        filtered_nodes = [node for node in nodes if node["id"] not in exclude_ids]
        return filtered_nodes

    def filter_include_only_nodes(self, nodes, include_only_names):
        """Recursively filter to include only nodes with the specified names and their children."""
        if not include_only_names:
            return nodes

        include_ids = set()
        include_patterns = [get_regex_matching_pattern([name]) for name in include_only_names]

        def collect_children(parent_id):
            """Recursively collect all children of a given parent node."""
            for node in nodes:
                if node.get("prnt") == parent_id:
                    include_ids.add(node["id"])
                    collect_children(node["id"])

        def collect_parent_chain(node_id):
            """Collect all parents up to the root to maintain hierarchy."""
            for node in nodes:
                if node["id"] == node_id:
                    parent_id = node.get("prnt")
                    if parent_id:
                        include_ids.add(parent_id)
                        collect_parent_chain(parent_id)

        # Find nodes matching the include patterns
        for node in nodes:
            node_name = node.get("nm", "").strip()
            if node_name and any(pattern.match(node_name) for pattern in include_patterns):
                include_ids.add(node["id"])
                # Include all children of this node
                collect_children(node["id"])
                # Include parent chain to maintain hierarchy
                collect_parent_chain(node["id"])

        # Filter to include only the matched nodes and their related nodes
        filtered_nodes = [node for node in nodes if node["id"] in include_ids]
        return filtered_nodes

    async def get_tree_data(self, session_id: str, share_id: str | None = None,
                       exclude_node_names: list[str] | None = None,
                       include_only_node_names: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Fetches the entire tree data from Workflowy for a given session ID and optional share ID.

        Args:
            session_id (str): The session ID for authentication.
            share_id (Optional[str], optional): The share ID to fetch specific shared data. Defaults to None.
            exclude_node_names (Optional[list[str]], optional): List of node names to exclude. Defaults to None.
            include_only_node_names (Optional[list[str]], optional): List of node names to include only. Defaults to None.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the tree data items.
        """
        if not session_id:
            raise ValueError("No sessionId provided.")

        url = f"{self.WORKFLOWY_URL}/get_tree_data/"
        if share_id:
            url += f"?share_id={share_id}"
            logger.info("SHARE_ID appended: %s", url)

        response = await self.make_request("GET", url, headers={"Cookie": f"sessionid={session_id}"}, timeout=10)
        data = await response.json()
        items = data.get("items", [])

        # Apply include-only filter first (if specified)
        if include_only_node_names:
            items = self.filter_include_only_nodes(items, include_only_node_names)

        # Then apply exclude filter (if specified)
        if exclude_node_names:
            items = self.filter_nodes(items, exclude_node_names)

        return items

    async def login_to_workflowy(self, username: str, password: str) -> str:
        if not username or not password:
            raise ValueError("Username and password are required.")
        print(f"Logging in to Workflowy with username: {username} and password: {password}")
        body = {"username": username, "password": password}
        response = await self.make_request("POST", self.LOGIN_URL, data=body, timeout=10)
        print(f"Login response: {response}")
        data = await response.json()
        print(f"Login data: {data}")
        if data.get("success"):
            cookie = response.cookies.get("sessionid")
            if cookie:
                return str(cookie.value)
            raise Exception("Session ID not found in response cookies.")
        else:
            raise Exception("Login to Workflowy failed.")

    async def get_initial_data(self, session_id: str, share_id: str) -> list[str]:
        INITIALIZATION_URL = f"{self.WORKFLOWY_URL}/get_initialization_data?share_id={share_id}&client_version=21&client_version_v2=28&no_root_children=1&include_main_tree=1"
        logger.info("GET_INITIAL_DATA: fetching response.")
        response = await self.make_request("GET", INITIALIZATION_URL, headers={"Cookie": f"sessionid={session_id}"}, timeout=10)
        data = await response.json()
        logger.info("GET_INITIAL_DATA: response: %s", response)
        return InitializationData(**data).transform()

    def remove_unnecessary_html_tags(self, content: str) -> str:
        # First remove mention tags completely since they don't contain relevant content
        content = re.sub(r"<mention[^>]*>[^<]*</mention>", "", content)

        # Convert hyperlinks to markdown format: replace <a href="url">text</a> with [text](url)
        def replace_link(match):
            href = re.search(r'href=["\'](.*?)["\']', match.group(0))
            text = re.sub(r"<[^>]+>", "", match.group(0))  # Get text without tags
            if href:
                return f"[{text.strip()}]({href.group(1)})"
            return text.strip()

        content = re.sub(r"<a[^>]+>.*?</a>", replace_link, content)

        # Then remove all other HTML tags while preserving their content
        content = re.sub(r"<[^>]+>", "", content)
        return content.strip()

    def generate_full_tree_markdown(self, tree: dict[str, dict[str, Any]], is_breadcrumb_format: bool = True):
        top_parent_name = ""
        top_parent_node_id = ""

        def generate_plain_markdown(item: dict[str, Any], level: int = 0) -> str:
            nonlocal top_parent_name, top_parent_node_id  # Ensure these are accessible
            indent = "  " * level
            markdown = f"{indent}- {item['nm']}\n"
            if level == 0:
                top_parent_name = item["nm"]
                top_parent_node_id = item["id"]  # Assign the node ID
            if "children" in item:
                for child in sorted(item["children"], key=lambda x: x["pr"]):
                    markdown += generate_plain_markdown(child, level + 1)
            return markdown

        def process_tree(item: dict[str, Any]) -> str:
            nonlocal top_parent_name, top_parent_node_id
            if not top_parent_name:  # Only set these for the first item
                top_parent_name = item["nm"]
                top_parent_node_id = item["id"]
            return self.node_to_markdown(item)

        # Generate markdown for all root nodes in the tree
        markdown_content = ""
        for _root_id, root_item in tree.items():
            if is_breadcrumb_format:
                markdown_content += process_tree(root_item)
            else:
                markdown_content += generate_plain_markdown(root_item)

        workflowy_node = WorkflowyNode(node_id=top_parent_node_id, node_name=top_parent_name, content=markdown_content)
        return workflowy_node

    def url_to_markdown(self, data: list[dict[str, Any]], is_breadcrumb_format: bool = True) -> WorkflowyNode:
        # Step 1: Create a dictionary to organize the items by their ID
        items_by_id: dict[str, dict[str, Any]] = {item["id"]: item for item in data}
        tree: dict[str, dict[str, Any]] = {}
        code = None  # This will store the extracted code from the URL

        # Step 3: Build the tree and look for the matching node
        for item in data:
            parent_id = item.get("prnt")
            if parent_id:
                parent = items_by_id.get(parent_id)
                if parent:
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(item)
            else:
                tree[item["id"]] = item  # Add top-level items to the tree

        # Step 4: If no matching node is found, return the full tree
        logger.info("No matching node found for code: %s. Returning the full tree.", code)
        workflowy_node = self.generate_full_tree_markdown(tree, is_breadcrumb_format)
        return workflowy_node

    def node_to_markdown(self, node: dict[str, Any], breadcrumb: str = "", level: int = 0, save_to_file: bool = False) -> str:
        markdown = ""
        bullet = "#" * (level + 1) if level < 3 else "-"

        # Create current breadcrumb
        current_name = node["nm"].strip()
        current_breadcrumb = f"{breadcrumb} -> {current_name}" if breadcrumb else current_name

        # Add the node's name with breadcrumb
        if current_name:
            markdown += f"{bullet} {current_breadcrumb}\n"
            if node.get("no"):  # Use get() to safely handle missing "no" key
                markdown += f"{node['no']}\n"
            markdown += "\n"

        # Process children recursively with updated breadcrumb, but limit to 6 levels
        if level < 6:
            for child in node.get("children", []):
                markdown += self.node_to_markdown(child, breadcrumb=current_breadcrumb, level=level + 1)
        else:
            # Append all deeper nodes' content to the 6th level node
            for child in node.get("children", []):
                markdown += f"- {child['nm'].strip()}\n"
                if child.get("no"):
                    markdown += f"{child['no']}\n"
                markdown += "\n"

        if save_to_file:
            with open("output.md", "w") as f:
                f.write(markdown)

        return markdown

    async def scrape_workflowy(self, url: str, exclude_node_names: list[str] | None = None,
                          include_only_node_names: list[str] | None = None):
        try:
            session_id, share_id = await self.extract_share_id(url)
            root_node_ids = await self.get_initial_data(session_id, share_id)

            item_data_list = await self.get_tree_data(
                session_id,
                share_id=root_node_ids[0],
                exclude_node_names=exclude_node_names,
                include_only_node_names=include_only_node_names
            )
            logger.info("Successfully grabbed item_data_list")

            workflowy_node = self.url_to_markdown(item_data_list, is_breadcrumb_format=False)
            logger.info(f"Workflowy Node: {workflowy_node}")

            workflowy_node.content = self.remove_unnecessary_html_tags(workflowy_node.content)
            workflowy_node.timestamp = time.time()
            logger.info("Markdown: %s", workflowy_node.content)
            return workflowy_node
        except Exception as e:
            logger.error("SCRAPER_SERVICE: Error scraping workflowy at node %s. Exception: %s", url, e)

    async def refresh_workflowy_node(self, node_id) -> WorkflowyNode | None:
        try:
            if node_id.startswith("workflowy__"):
                segment = node_id.split("__")[1]
                logger.info("Segment: %s", segment)
                url_from_b64 = base64.b64decode(segment).decode()
                url = f"https://workflowy.com/s/{url_from_b64}"
                logger.info("URL: %s", url)
                # Refresh the node
                workflowy_node = await self.scrape_workflowy(url)
                return workflowy_node
            else:
                return None
        except Exception as e:
            logger.error("SCRAPER_SERVICE: Error refreshing workflowy at node %s. Exception: %s", node_id, e)
            return None

    def validate_workflowy_url(self, url: str) -> tuple[str, str]:
        """Validates Workflowy URL and extracts url_path"""
        match = re.search(r"https://workflowy.com/s/(.*)", url)
        if not match:
            raise ValueError("Invalid Workflowy URL format")
        url_path = match.group(1)
        b64_url_path = base64.b64encode(url_path.encode()).decode()
        return url_path, b64_url_path

    def generate_node_name(self, full_node_name: str, prefix: str = "WF - ", max_length: int = 50) -> str:
        """Generates a truncated node name with prefix and sanitized content

        Args:
            full_node_name: Raw node name that may contain HTML tags
            prefix: String to prepend to the node name
            max_length: Maximum length of the resulting node name

        Returns:
            Sanitized and truncated node name with prefix
        """
        node_name = re.sub(r"<mention[^>]*>.*?</mention>", "", full_node_name)
        node_name = re.sub(r"<[^>]+>", "", node_name)
        node_name = html.unescape(node_name)
        node_name = node_name[:max_length].strip()
        if len(node_name) == max_length:
            index_space = node_name.rfind(" ")
            if index_space != -1:
                node_name = node_name[:index_space].strip()

        return prefix + node_name

    def create_manifest_item(self, node_id: str, node_name: str, content: str, url: str) -> dict:
        """Creates a manifest item for the Workflowy node"""
        content_hash = hashlib.md5(content.encode("utf-8"), usedforsecurity=False).hexdigest()
        return {"id": node_id, "name": f"{node_name}.md", "mimeType": "text/markdown", "ingestion_status": "Added", "content_hash": content_hash, "webViewLink": url}

    async def prepare_workflowy_ingest(self, url: str, exclude_node_names: list[str] | None = None,
                                  include_only_node_names: list[str] | None = None) -> tuple[WorkflowyNode, str, str, list]:
        """
        Prepares all necessary data for Workflowy ingestion
        Returns: (workflowy_node, node_id, node_name, manifest)
        """
        url_path, b64_url_path = self.validate_workflowy_url(url)

        workflowy_node = await self.scrape_workflowy(
            url,
            exclude_node_names=exclude_node_names,
            include_only_node_names=include_only_node_names
        )
        if not workflowy_node or not workflowy_node.content:
            raise ValueError("Failed to scrape Workflowy content.")

        node_name = self.generate_node_name(workflowy_node.node_name)
        node_id = f"workflowy__{b64_url_path}"

        manifest = [self.create_manifest_item(node_id, node_name, workflowy_node.content, url)]

        return workflowy_node, node_id, node_name, manifest

    async def __aenter__(self):
        """Async context manager entry."""
        await self.get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None
