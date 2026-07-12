"""
Browser Supervisor
==================
Orchestrates generic browser automation. Acts as the interface between the core AppSuite 
and web targets. Coordinates DOM interpretation, website adapters, and website memory.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional

from ...logging_setup import get_logger
from .adapters import AdapterRegistry
from .dom_interpreter import DOMInterpreter
from .memory import WebsiteMemory

log = get_logger("browser_agent")

class BrowserSupervisor:
    def __init__(self, db: Any):
        self.db = db
        self.memory = WebsiteMemory(db)
        self.adapters = AdapterRegistry()
        self.interpreter = DOMInterpreter()
        
    def search(self, query: str, domain: Optional[str] = None) -> List[Dict[str, str]]:
        """Performs a search on the specified domain, or generically if none provided."""
        adapter = self.adapters.get_adapter(f"https://{domain}" if domain else "generic")
        url = adapter.get_search_url(query)
        
        if self.memory.is_rate_limited(adapter.domain):
            log.warning("BrowserAgent: Domain %s is rate limited. Skipping search.", adapter.domain)
            return []
            
        log.info("BrowserAgent: Searching %s for '%s'", adapter.domain, query)
        
        # In a real implementation, we would HTTP GET the url here
        # html = requests.get(url).text
        html = "<html>mock dom</html>"
        
        dom = self.interpreter.parse_html(html)
        results = adapter.extract_search_results(dom)
        
        self.memory.record_visit(url, "search", "success", {"results_count": len(results)})
        return results

    def extract_information(self, url: str) -> str:
        """Visits a URL and extracts summarized content."""
        adapter = self.adapters.get_adapter(url)
        log.info("BrowserAgent: Extracting info from %s", url)
        
        # html = requests.get(url).text
        html = "<html>mock dom</html>"
        
        dom = self.interpreter.parse_html(html)
        summary = self.interpreter.summarize_content(dom)
        
        self.memory.record_visit(url, "extract", "success", {"summary_length": len(summary)})
        return summary

    def download_asset(self, page_url: str) -> Optional[str]:
        """Resolves a page URL to a direct download URL via the adapter, then fetches it."""
        adapter = self.adapters.get_adapter(page_url)
        log.info("BrowserAgent: Resolving download for %s", page_url)
        
        # html = requests.get(page_url).text
        html = "<html>mock dom</html>"
        
        dom = self.interpreter.parse_html(html)
        download_url = adapter.get_download_url(page_url, dom)
        
        if not download_url:
            log.warning("BrowserAgent: Failed to find download link on %s", page_url)
            self.memory.record_visit(page_url, "download_resolve", "failure")
            return None
            
        log.info("BrowserAgent: Found direct download URL -> %s", download_url)
        self.memory.record_visit(page_url, "download_resolve", "success", {"download_url": download_url})
        return download_url
