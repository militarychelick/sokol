# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Search Agent for External Information Lookup"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
import json

from ..core import OllamaClient
from ..web_fetcher import WebFetcher
from .base import AgentBase, AgentResponse, AgentStatus, AgentCapability

logger = logging.getLogger(__name__)


class SearchAgent(AgentBase):
    """
    Search Agent - Handles external information lookup when local data is insufficient
    Performs web searches and retrieves information from external sources
    """
    
    def __init__(self):
        capabilities = [
            AgentCapability(
                name="web_search",
                description="Search the web for information",
                max_execution_time=25
            ),
            AgentCapability(
                name="fetch_url",
                description="Fetch and extract content from URLs",
                max_execution_time=20
            ),
            AgentCapability(
                name="lookup_info",
                description="Lookup specific information from external sources",
                max_execution_time=15
            ),
            AgentCapability(
                name="summarize",
                description="Summarize search results and web content",
                max_execution_time=10
            )
        ]
        
        super().__init__("search_agent", capabilities)
        
        # Initialize clients
        self.web_fetcher = WebFetcher()
        self.llm_client = OllamaClient(
            system_message=self._get_search_system_prompt(),
            classify_prompt=""
        )
    
    def _get_search_system_prompt(self) -> str:
        """Get system prompt for search agent"""
        return """You are Sokol's Search Agent. Your job is to find and retrieve information from external sources.

Your responsibilities:
1. Understand what information the user needs
2. Formulate effective search queries
3. Extract relevant information from search results
4. Summarize findings clearly and concisely

RULES:
- Be factual and accurate
- Cite sources when possible
- Focus on practical, actionable information
- Avoid speculation and opinions

RESPONSE FORMAT (JSON):
{
  "query": "search query used",
  "results": [
    {
      "title": "Result title",
      "url": "source URL",
      "snippet": "relevant excerpt",
      "relevance": 0.9
    }
  ],
  "summary": "concise summary of findings",
  "confidence": 0.8,
  "sources": ["url1", "url2"]
}

Be helpful and efficient in finding information."""
    
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """Process search agent request"""
        self._start_execution()
        
        try:
            action = request.get("action", "").lower()
            
            if action == "web_search":
                return await self._web_search(request)
            elif action == "fetch_url":
                return await self._fetch_url(request)
            elif action == "lookup_info":
                return await self._lookup_info(request)
            elif action == "summarize":
                return await self._summarize(request)
            else:
                return await self._handle_search_request(request)
                
        except Exception as e:
            self.logger.error(f"Search operation failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _web_search(self, request: Dict[str, Any]) -> AgentResponse:
        """Perform web search"""
        query = request.get("query", "")
        max_results = request.get("max_results", 5)
        
        if not query:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No search query provided"
            )
        
        try:
            # Perform web search
            search_results = await self._perform_search(query, max_results)
            
            if not search_results:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="No search results found"
                )
            
            # Summarize results
            summary = await self._summarize_results(query, search_results)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Found {len(search_results)} search results",
                data={
                    "query": query,
                    "results": search_results,
                    "summary": summary.get("summary", ""),
                    "sources": [r.get("url", "") for r in search_results]
                },
                confidence=summary.get("confidence", 0.7)
            )
            
        except Exception as e:
            self.logger.error(f"Web search failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _fetch_url(self, request: Dict[str, Any]) -> AgentResponse:
        """Fetch and extract content from URL"""
        url = request.get("url", "")
        extract_text = request.get("extract_text", True)
        
        if not url:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No URL provided"
            )
        
        try:
            # Fetch URL content
            content = await self._fetch_url_content(url)
            
            if not content:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Failed to fetch URL content"
                )
            
            # Extract text if requested
            if extract_text:
                extracted_text = await self._extract_text_from_content(content)
                content["extracted_text"] = extracted_text
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="URL content fetched successfully",
                data=content,
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"URL fetch failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _lookup_info(self, request: Dict[str, Any]) -> AgentResponse:
        """Lookup specific information"""
        topic = request.get("topic", "")
        info_type = request.get("info_type", "general")
        
        if not topic:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No topic provided"
            )
        
        try:
            # Formulate search query based on info type
            query = self._formulate_lookup_query(topic, info_type)
            
            # Perform search
            search_results = await self._perform_search(query, 3)
            
            # Extract specific information
            extracted_info = await self._extract_specific_info(topic, info_type, search_results)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Information lookup completed for: {topic}",
                data={
                    "topic": topic,
                    "info_type": info_type,
                    "extracted_info": extracted_info,
                    "sources": [r.get("url", "") for r in search_results]
                },
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Information lookup failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _summarize(self, request: Dict[str, Any]) -> AgentResponse:
        """Summarize search results or content"""
        content = request.get("content", "")
        content_type = request.get("content_type", "text")
        
        if not content:
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message="No content to summarize"
            )
        
        try:
            # Generate summary
            summary = await self._generate_summary(content, content_type)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Content summarized successfully",
                data={
                    "original_content": content[:500] + "..." if len(content) > 500 else content,
                    "summary": summary,
                    "content_type": content_type
                },
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Summarization failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _handle_search_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Handle general search requests"""
        text = request.get("text", str(request))
        
        # Try to understand the search intent
        text_lower = text.lower()
        
        if "search" in text_lower or "find" in text_lower or "look up" in text_lower:
            # Extract search query
            query = self._extract_search_query(text)
            return await self._web_search({"query": query})
        
        elif "url" in text_lower or "website" in text_lower:
            # Extract URL
            url = self._extract_url(text)
            return await self._fetch_url({"url": url})
        
        else:
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Search agent ready. Available operations: web_search, fetch_url, lookup_info, summarize",
                data={"available_operations": self.list_capabilities()},
                confidence=0.7
            )
    
    async def _perform_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform actual web search"""
        try:
            # Use web_fetcher for search
            # This is a simplified implementation - in reality would use search API
            import urllib.parse
            
            # For now, create mock search results
            # In production, would integrate with DuckDuckGo, Google, or other search APIs
            
            mock_results = [
                {
                    "title": f"Search result for: {query}",
                    "url": "https://example.com/search",
                    "snippet": f"This is a mock search result for the query: {query}",
                    "relevance": 0.8
                }
            ]
            
            return mock_results[:max_results]
            
        except Exception as e:
            self.logger.error(f"Search execution failed: {e}")
            return []
    
    async def _fetch_url_content(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch content from URL"""
        try:
            # Use web_fetcher to get URL content
            content = await asyncio.get_event_loop().run_in_executor(
                None, self.web_fetcher.fetch, url
            )
            
            if content:
                return {
                    "url": url,
                    "title": content.get("title", ""),
                    "content": content.get("content", ""),
                    "status_code": content.get("status_code", 200)
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"URL content fetch failed: {e}")
            return None
    
    async def _extract_text_from_content(self, content: Dict[str, Any]) -> str:
        """Extract clean text from web content"""
        try:
            html_content = content.get("content", "")
            
            # Simple text extraction (in production would use BeautifulSoup)
            # Remove HTML tags
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            
            # Clean up whitespace
            text = ' '.join(text.split())
            
            return text[:2000]  # Limit length
            
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            return ""
    
    async def _summarize_results(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize search results"""
        try:
            # Combine result snippets
            combined_text = "\n".join([
                f"{r.get('title', '')}: {r.get('snippet', '')}"
                for r in results[:5]
            ])
            
            # Generate summary using LLM
            summary_prompt = f"""Summarize the search results for query: "{query}"

Results:
{combined_text}

Provide a concise summary in JSON:
{{
  "summary": "brief summary",
  "confidence": 0.8,
  "key_points": ["point1", "point2"]
}}"""
            
            summary_response = self.llm_client.chat(summary_prompt, one_shot=True)
            
            try:
                return json.loads(summary_response)
            except json.JSONDecodeError:
                return {
                    "summary": summary_response,
                    "confidence": 0.6,
                    "key_points": []
                }
                
        except Exception as e:
            self.logger.error(f"Result summarization failed: {e}")
            return {
                "summary": f"Found {len(results)} results for '{query}'",
                "confidence": 0.5,
                "key_points": []
            }
    
    async def _extract_specific_info(self, topic: str, info_type: str, results: List[Dict[str, Any]]) -> str:
        """Extract specific information from search results"""
        try:
            # Combine relevant content
            combined_content = "\n".join([
                r.get("snippet", "") for r in results
            ])
            
            # Extract based on info type
            if info_type == "definition":
                prompt = f"Extract the definition of '{topic}' from this text: {combined_content}"
            elif info_type == "how_to":
                prompt = f"Extract how-to information about '{topic}' from this text: {combined_content}"
            elif info_type == "troubleshooting":
                prompt = f"Extract troubleshooting information about '{topic}' from this text: {combined_content}"
            else:
                prompt = f"Extract key information about '{topic}' from this text: {combined_content}"
            
            # Use LLM to extract information
            extracted = self.llm_client.chat(prompt, one_shot=True)
            return extracted
            
        except Exception as e:
            self.logger.error(f"Information extraction failed: {e}")
            return f"Could not extract specific information about {topic}"
    
    async def _generate_summary(self, content: str, content_type: str) -> str:
        """Generate summary of content"""
        try:
            # Truncate content if too long
            truncated_content = content[:3000] if len(content) > 3000 else content
            
            summary_prompt = f"""Summarize this {content_type} content:

{truncated_content}

Provide a concise summary:"""
            
            summary = self.llm_client.chat(summary_prompt, one_shot=True)
            return summary
            
        except Exception as e:
            self.logger.error(f"Summary generation failed: {e}")
            return f"Content summary unavailable. Length: {len(content)} characters."
    
    def _formulate_lookup_query(self, topic: str, info_type: str) -> str:
        """Formulate effective search query"""
        if info_type == "definition":
            return f"what is {topic} definition"
        elif info_type == "how_to":
            return f"how to {topic}"
        elif info_type == "troubleshooting":
            return f"{topic} troubleshooting problem solution"
        elif info_type == "tutorial":
            return f"{topic} tutorial guide"
        else:
            return topic
    
    def _extract_search_query(self, text: str) -> str:
        """Extract search query from text"""
        # Simple extraction - look for keywords
        text_lower = text.lower()
        
        # Remove search-related words
        for word in ["search", "find", "look up", "for"]:
            text_lower = text_lower.replace(word, "")
        
        return text_lower.strip()
    
    def _extract_url(self, text: str) -> str:
        """Extract URL from text"""
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        matches = re.findall(url_pattern, text)
        return matches[0] if matches else ""
