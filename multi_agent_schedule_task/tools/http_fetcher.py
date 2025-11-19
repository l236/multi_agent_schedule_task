"""
HTTP fetcher tool.

Fetches URL content and returns a standardized dict with text content,
title and basic metadata.
"""
import logging
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup

from ..registry import BaseTool, tool_registry

logger = logging.getLogger(__name__)


class HttpFetcherTool(BaseTool):
    @property
    def name(self) -> str:
        return "http_fetcher"

    @property
    def description(self) -> str:
        return "Fetch HTML or text content from a URL and return normalized text"

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        url = None
        if isinstance(input_data, dict):
            url = input_data.get("url")
            timeout = input_data.get("timeout", 10)
            headers = input_data.get("headers")
        else:
            url = str(input_data)
            timeout = 10
            headers = None

        if not url:
            raise ValueError("http_fetcher requires a 'url' parameter")

        logger.info(f"Fetching URL: {url}")
        resp = requests.get(url, timeout=timeout, headers=headers)

        result: Dict[str, Any] = {
            "url": url,
            "status_code": resp.status_code,
            "content_type": resp.headers.get("content-type"),
            "content": None,
            "title": None,
            "metadata": {},
        }

        # If HTML, extract readable text
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type.lower():
            soup = BeautifulSoup(resp.text, "lxml")
            # Remove scripts/styles
            for s in soup(["script", "style", "noscript"]):
                s.decompose()
            text = soup.get_text(separator="\n")
            title_tag = soup.title.string.strip() if soup.title and soup.title.string else None
            # meta description
            desc = None
            md = soup.find("meta", attrs={"name": "description"})
            if md and md.get("content"):
                desc = md.get("content")

            result.update({"content": text.strip(), "title": title_tag, "metadata": {"description": desc}})
        else:
            # Non-html: treat as text/binary
            try:
                result["content"] = resp.text
            except Exception:
                result["content"] = None

        return result


# Register tool into the global registry
try:
    tool_registry.register_tool("http_fetcher", HttpFetcherTool)
except Exception:
    # registration may be called multiple times in some environments
    logger.debug("http_fetcher registration skipped or already registered")
