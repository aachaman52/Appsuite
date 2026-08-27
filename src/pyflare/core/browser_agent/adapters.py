"""
Website Adapters Registry
=========================
Maintains domain-specific adapters. This isolates website-specific logic (e.g. 
search URL formatting, specific class names for scraping) away from the generic core.
"""
from __future__ import annotations

import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class WebsiteAdapter(ABC):
    domain: str
    
    @abstractmethod
    def get_search_url(self, query: str) -> str:
        pass
        
    @abstractmethod
    def extract_search_results(self, dom: Any) -> List[Dict[str, str]]:
        pass
        
    @abstractmethod
    def get_download_url(self, page_url: str, dom: Any) -> Optional[str]:
        pass

class GenericAdapter(WebsiteAdapter):
    domain = "*"
    def get_search_url(self, query: str) -> str:
        return f"https://google.com/search?q={urllib.parse.quote(query)}"
        
    def extract_search_results(self, dom: Any) -> List[Dict[str, str]]:
        return []
        
    def get_download_url(self, page_url: str, dom: Any) -> Optional[str]:
        return None

class GitHubAdapter(WebsiteAdapter):
    domain = "github.com"
    def get_search_url(self, query: str) -> str:
        return f"https://github.com/search?q={urllib.parse.quote(query)}"
        
    def extract_search_results(self, dom: Any) -> List[Dict[str, str]]:
        return []
        
    def get_download_url(self, page_url: str, dom: Any) -> Optional[str]:
        # Synthesize zip download url from repo page
        return f"{page_url}/archive/refs/heads/main.zip"

class AdapterRegistry:
    def __init__(self):
        self._adapters: Dict[str, WebsiteAdapter] = {}
        self.register(GenericAdapter())
        self.register(GitHubAdapter())
        # Other adapters: Sketchfab, Mixamo, PolyPizza, Kenney, Fab, Docs
        
    def register(self, adapter: WebsiteAdapter):
        self._adapters[adapter.domain] = adapter
        
    def get_adapter(self, url: str) -> WebsiteAdapter:
        try:
            domain = urllib.parse.urlparse(url).netloc
            for registered_domain, adapter in self._adapters.items():
                if registered_domain in domain:
                    return adapter
        except Exception:
            pass
        return self._adapters["*"]
