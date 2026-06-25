"""Browser Research Agent for AppSuite."""
from __future__ import annotations

import re
import urllib.parse
import requests
from typing import Any, Dict, List
from .base_agent import BaseAgent, AgentTask

class BrowserAgent(BaseAgent):
    """
    Browser Research Agent capable of documentation lookup, asset discovery,
    and error investigation using real web searches.
    """
    
    def receive_task(self, task: AgentTask):
        print(f"[{self.name}] Researching objective: {task.objective}")
        if self.message_bus:
            self.message_bus.send("browser_status", f"Researching: {task.objective}")

    def plan(self, task: AgentTask) -> Any:
        # Determine research type based on the task description
        obj = task.objective.lower()
        if "error" in obj or "fail" in obj or "crash" in obj or "debug" in obj:
            return {"type": "error_investigation", "query": task.objective}
        elif "asset" in obj or "model" in obj or "texture" in obj:
            return {"type": "asset_discovery", "query": task.objective}
        elif "docs" in obj or "documentation" in obj or "how to" in obj or "syntax" in obj:
            return {"type": "documentation_lookup", "query": task.objective}
        else:
            return {"type": "technical_research", "query": task.objective}

    def execute_tools(self, plan: Any) -> Any:
        research_type = plan["type"]
        query = plan["query"]
        
        if self.message_bus:
            self.message_bus.send("browser_status", f"Executing search for: {query}")
            
        results = self.search_web(query)
        
        output = {
            "query": query,
            "research_type": research_type,
            "raw_results": results
        }
        
        # Structure the findings based on research type
        if research_type == "error_investigation":
            output["analysis"] = self._analyze_errors(query, results)
        elif research_type == "asset_discovery":
            output["analysis"] = self._discover_asset_sources(query, results)
        elif research_type == "documentation_lookup":
            output["analysis"] = self._lookup_documentation(query, results)
        else:
            output["analysis"] = self._perform_general_research(query, results)
            
        return output

    def search_web(self, query: str) -> List[Dict[str, str]]:
        """
        Perform a real web search via DuckDuckGo HTML interface.
        Bypasses API key requirements and returns list of dicts.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                html = r.text
                links = re.findall(r'<a class="result__url" href="([^"]+)"', html)
                snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                
                results = []
                for link, snippet in zip(links, snippets):
                    # Clean snippet from HTML tags
                    snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
                    # Resolve redirected url if necessary
                    decoded_link = urllib.parse.unquote(link)
                    if "uddg=" in decoded_link:
                        decoded_link = decoded_link.split("uddg=")[1].split("&")[0]
                        decoded_link = urllib.parse.unquote(decoded_link)
                    results.append({
                        "url": decoded_link,
                        "snippet": snippet_clean
                    })
                return results[:5]  # Limit to top 5 results
        except Exception as e:
            print(f"[BrowserAgent] Web search failed: {e}")
            
        # Fallback if request fails
        return [
            {
                "url": "https://docs.godotengine.org/en/stable/",
                "snippet": "Fallback: Godot 4.x official documentation and class index."
            }
        ]

    def _analyze_errors(self, query: str, results: List[Dict[str, str]]) -> Dict[str, Any]:
        # Formulate general debug suggestions from search snippets
        suggestions = []
        for r in results:
            snippet = r["snippet"]
            if "error" in snippet.lower() or "fix" in snippet.lower() or "solution" in snippet.lower():
                suggestions.append(snippet)
        
        return {
            "summary": f"Analyzed error: {query}",
            "solutions": suggestions if suggestions else ["Ensure syntax is correct for Godot 4.x.", "Check node references and variable initialization."],
            "recommended_fixes": ["Verify script class inherits from the correct Node type (e.g. CharacterBody3D for player)."]
        }

    def _discover_asset_sources(self, query: str, results: List[Dict[str, str]]) -> Dict[str, Any]:
        sources = []
        for r in results:
            if "kenney" in r["url"].lower() or "poly" in r["url"].lower() or "github" in r["url"].lower() or "sketchfab" in r["url"].lower():
                sources.append(r["url"])
        return {
            "summary": f"Discovered asset sources for: {query}",
            "matching_urls": sources if sources else [r["url"] for r in results[:3]],
            "recommended_source": sources[0] if sources else "https://kenney.nl/assets"
        }

    def _lookup_documentation(self, query: str, results: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "summary": f"Documentation lookup for: {query}",
            "links": [r["url"] for r in results],
            "key_notes": results[0]["snippet"] if results else "No specific snippets found."
        }

    def _perform_general_research(self, query: str, results: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "summary": f"Research query: {query}",
            "findings": [r["snippet"] for r in results]
        }
