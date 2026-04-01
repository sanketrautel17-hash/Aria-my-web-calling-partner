"""
Aria — Web Search Tool using Tavily API.

Shared between web calls and phone calls (Loan Assistant persona).
"""

import os
from core.config import settings
from commons.logger import logger

log = logger(__name__)


class WebSearch:
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY or ""
        if not self.api_key:
            log.warning("TAVILY_API_KEY not found. Web search will be unavailable.")
            self.client = None
        else:
            from tavily import TavilyClient
            self.client = TavilyClient(api_key=self.api_key)
            log.info("✅ Tavily web search initialized")

    def search(self, query: str, max_results: int = 3) -> str:
        """
        Perform a web search using Tavily API.
        Returns a formatted string of results.
        """
        try:
            if not self.client:
                return (
                    "Web search is currently unavailable. "
                    "Please use the internal knowledge base tool (get_loan_information) instead."
                )

            log.info(f"Searching web (Tavily): {query}")
            response = self.client.search(
                query, search_depth="advanced", max_results=max_results
            )
            results = response.get("results", [])

            if not results:
                return "No relevant information found online."

            formatted = []
            for r in results:
                formatted.append(
                    f"Title: {r.get('title', 'No Title')}\n"
                    f"Summary: {r.get('content', '')}\n"
                    f"Source: {r.get('url', '')}"
                )

            return "\n\n".join(formatted)
        except Exception as e:
            log.error(f"Web search failed: {e}")
            return f"Error performing web search: {str(e)}"


# Singleton
web_search = WebSearch()
