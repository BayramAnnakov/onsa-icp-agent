"""Firecrawl SDK integration for web crawling and content extraction."""

import os
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import structlog

try:
    from firecrawl import FirecrawlApp, ScrapeOptions
except ImportError:
    raise ImportError("firecrawl-py is required. Install with: pip install firecrawl-py")

from utils.cache import CacheManager


class FirecrawlClient:
    """
    Firecrawl SDK client for web crawling, content extraction, and website analysis.
    
    Uses the official Firecrawl Python SDK for comprehensive web scraping capabilities.
    """
    
    def __init__(self, api_key: Optional[str] = None, cache_manager: Optional[CacheManager] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.cache_manager = cache_manager
        
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable is required")
        
        self.logger = structlog.get_logger().bind(service="firecrawl")
        
        # Initialize Firecrawl SDK
        self.app = FirecrawlApp(api_key=self.api_key)
        
        self.logger.info("Firecrawl SDK client initialized")
    
    async def scrape_url(
        self,
        url: str,
        include_links: bool = True,
        include_metadata: bool = True,
        format_type: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Scrape a single URL and extract content.
        
        Args:
            url: URL to scrape
            include_links: Whether to extract links
            include_metadata: Whether to extract metadata
            format_type: Output format (markdown, html, text)
            
        Returns:
            Scraped content and metadata
        """
        
        # Check cache first
        cache_params = {
            "url": url,
            "links": include_links,
            "metadata": include_metadata,
            "format": format_type
        }
        
        if self.cache_manager:
            cached_content = self.cache_manager.get_cached_api_response(
                "firecrawl", "scrape", cache_params
            )
            if cached_content:
                self.logger.info("Using cached scraped content", url=url)
                return cached_content
        
        # Prepare scrape options according to v1 API
        formats = [format_type]
        
        # Add links format if requested
        if include_links:
            formats.append('links')
        
        try:
            # Use Firecrawl SDK to scrape
            # Correct usage: app.scrape_url(url, formats=['markdown'])
            result = await asyncio.to_thread(
                self.app.scrape_url,
                url,
                formats=formats
            )
            
            # Process the scraped content
            processed_content = self._process_scraped_content(result, url)
            
            # Cache the results
            if self.cache_manager:
                self.cache_manager.cache_api_response(
                    "firecrawl", "scrape", cache_params, processed_content
                )
            
            self.logger.info("URL scraped successfully", url=url)
            return processed_content
            
        except Exception as e:
            self.logger.error("Error during URL scraping", url=url, error=str(e))
            raise
    
    async def crawl_website(
        self,
        start_url: str,
        max_pages: int = 10,
        max_depth: int = 2,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Crawl an entire website starting from a URL.
        
        Args:
            start_url: Starting URL for the crawl
            max_pages: Maximum number of pages to crawl
            max_depth: Maximum crawl depth
            include_patterns: URL patterns to include
            exclude_patterns: URL patterns to exclude
            
        Returns:
            Crawl results with all pages
        """
        
        # Check cache first
        cache_params = {
            "start_url": start_url,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "include": include_patterns or [],
            "exclude": exclude_patterns or []
        }
        
        if self.cache_manager:
            cached_crawl = self.cache_manager.get_cached_api_response(
                "firecrawl", "crawl", cache_params
            )
            if cached_crawl:
                self.logger.info("Using cached crawl results", start_url=start_url)
                return cached_crawl
        
        try:
            # Use Firecrawl SDK to crawl
            # Based on example: app.crawl_url('https://firecrawl.dev', limit=100, scrape_options=ScrapeOptions(formats=['markdown', 'html']))
            scrape_options = ScrapeOptions(formats=['markdown'])
            
            result = await asyncio.to_thread(
                self.app.crawl_url,
                start_url,
                limit=max_pages,
                scrape_options=scrape_options,
                poll_interval=5
            )
            
            # Process the crawl results
            processed_results = self._process_crawl_results(result, start_url)
            
            # Cache the results
            if self.cache_manager:
                self.cache_manager.cache_api_response(
                    "firecrawl", "crawl", cache_params, processed_results
                )
            
            self.logger.info("Website crawl completed", start_url=start_url, pages=len(processed_results.get("pages", [])))
            return processed_results
            
        except Exception as e:
            self.logger.error("Error during website crawling", start_url=start_url, error=str(e))
            raise
    
    async def map_website(
        self,
        url: str,
        search: Optional[str] = None,
        ignore_sitemap: bool = False,
        include_subdomains: bool = False,
        limit: int = 5000
    ) -> Dict[str, Any]:
        """
        Map a website to get all URLs.
        
        Args:
            url: Website URL to map
            search: Search term to filter URLs
            ignore_sitemap: Whether to ignore sitemap
            include_subdomains: Whether to include subdomains
            limit: Maximum number of URLs
            
        Returns:
            Website map with all URLs
        """
        
        # Check cache first
        cache_params = {
            "url": url,
            "search": search,
            "ignore_sitemap": ignore_sitemap,
            "include_subdomains": include_subdomains,
            "limit": limit
        }
        
        if self.cache_manager:
            cached_map = self.cache_manager.get_cached_api_response(
                "firecrawl", "map", cache_params
            )
            if cached_map:
                self.logger.info("Using cached website map", url=url)
                return cached_map
        
        try:
            # Use Firecrawl SDK to map
            # Simple call - map_url might not accept many parameters
            result = await asyncio.to_thread(
                self.app.map_url,
                url
            )
            
            # Process the map results
            processed_map = {
                "url": url,
                "links": result.get("links", []),
                "total_links": len(result.get("links", [])),
                "mapped_at": datetime.now().isoformat(),
                "search_term": search,
                "parameters": params
            }
            
            # Cache the results
            if self.cache_manager:
                self.cache_manager.cache_api_response(
                    "firecrawl", "map", cache_params, processed_map
                )
            
            self.logger.info("Website mapped successfully", url=url, total_links=processed_map["total_links"])
            return processed_map
            
        except Exception as e:
            self.logger.error("Error during website mapping", url=url, error=str(e))
            raise
    
    async def extract_structured_data(
        self,
        url: str,
        schema: Dict[str, Any],
        extraction_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from a webpage using a schema.
        
        Args:
            url: URL to extract data from
            schema: JSON schema defining the data structure to extract
            extraction_prompt: Optional prompt to guide extraction
            
        Returns:
            Extracted structured data
        """
        
        # Check cache first
        cache_params = {"url": url, "schema": schema, "prompt": extraction_prompt}
        
        if self.cache_manager:
            cached_extraction = self.cache_manager.get_cached_api_response(
                "firecrawl", "extract", cache_params
            )
            if cached_extraction:
                self.logger.info("Using cached extraction results", url=url)
                return cached_extraction
        
        # Prepare extract options
        extract_config = {
            'schema': schema
        }
        
        if extraction_prompt:
            extract_config['prompt'] = extraction_prompt
        
        try:
            # Use Firecrawl SDK to extract
            result = await asyncio.to_thread(
                self.app.scrape_url,
                url,
                formats=['extract'],
                extract=extract_config
            )
            
            # Process extraction results
            processed_data = {
                "url": url,
                "extracted_data": result.get("extract", {}),
                "extraction_timestamp": datetime.now().isoformat(),
                "schema": schema
            }
            
            # Cache the results
            if self.cache_manager:
                self.cache_manager.cache_api_response(
                    "firecrawl", "extract", cache_params, processed_data
                )
            
            self.logger.info("Structured data extracted", url=url)
            return processed_data
            
        except Exception as e:
            self.logger.error("Error during data extraction", url=url, error=str(e))
            raise
    
    async def analyze_competitor_websites(
        self,
        competitor_urls: List[str],
        analysis_focus: str = "general"
    ) -> Dict[str, Any]:
        """
        Analyze multiple competitor websites for insights.
        
        Args:
            competitor_urls: List of competitor website URLs
            analysis_focus: Focus of analysis (pricing, features, messaging, etc.)
            
        Returns:
            Competitive analysis results
        """
        
        analysis_results = {}
        
        for url in competitor_urls:
            try:
                # Scrape competitor website
                scraped_data = await self.scrape_url(url, include_metadata=True)
                
                # Analyze specific aspects based on focus
                analysis = await self._analyze_competitor_content(scraped_data, analysis_focus)
                
                analysis_results[url] = {
                    "scraped_data": scraped_data,
                    "analysis": analysis,
                    "analyzed_at": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error("Error analyzing competitor", url=url, error=str(e))
                analysis_results[url] = {"error": str(e)}
        
        # Generate comparative insights
        comparative_insights = self._generate_comparative_insights(analysis_results, analysis_focus)
        
        return {
            "competitor_analyses": analysis_results,
            "comparative_insights": comparative_insights,
            "analysis_focus": analysis_focus,
            "analyzed_count": len([r for r in analysis_results.values() if "error" not in r])
        }
    
    def _process_scraped_content(self, raw_data, url: str) -> Dict[str, Any]:
        """Process raw scraped content into structured format."""
        
        # Handle Firecrawl SDK response object
        if hasattr(raw_data, 'markdown'):
            content = getattr(raw_data, 'markdown', '')
            metadata = getattr(raw_data, 'metadata', {})
            links = getattr(raw_data, 'links', [])
        elif isinstance(raw_data, dict):
            content = raw_data.get("markdown", "") or raw_data.get("html", "") or raw_data.get("content", "")
            metadata = raw_data.get("metadata", {})
            links = raw_data.get("links", [])
        else:
            content = str(raw_data)
            metadata = {}
            links = []
        
        return {
            "url": url,
            "title": metadata.get("title", "") if isinstance(metadata, dict) else "",
            "description": metadata.get("description", "") if isinstance(metadata, dict) else "",
            "content": content,
            "links": links if isinstance(links, list) else [],
            "metadata": metadata if isinstance(metadata, dict) else {},
            "scraped_at": datetime.now().isoformat(),
            "word_count": len(content.split()) if content else 0,
            "success": True
        }
    
    def _process_crawl_results(self, raw_results: Dict[str, Any], start_url: str) -> Dict[str, Any]:
        """Process raw crawl results into structured format."""
        
        pages = []
        
        # Handle both crawl response formats
        data = raw_results.get("data", [])
        if isinstance(data, dict):
            data = [data]
        
        for page_data in data:
            processed_page = self._process_scraped_content(page_data, page_data.get("metadata", {}).get("sourceURL", ""))
            pages.append(processed_page)
        
        return {
            "start_url": start_url,
            "pages": pages,
            "total_pages": len(pages),
            "crawl_completed_at": datetime.now().isoformat(),
            "success": raw_results.get("success", True),
            "crawl_metadata": {
                "total_words": sum(page.get("word_count", 0) for page in pages),
                "unique_domains": len(set(page.get("url", "").split("/")[2] for page in pages if page.get("url") and "/" in page.get("url", "")))
            }
        }
    
    async def _analyze_competitor_content(self, scraped_data: Dict[str, Any], focus: str) -> Dict[str, Any]:
        """Analyze competitor content based on focus area."""
        
        content = scraped_data.get("content", "")
        metadata = scraped_data.get("metadata", {})
        
        analysis = {
            "focus": focus,
            "content_length": len(content),
            "title": metadata.get("title", ""),
            "description": metadata.get("description", "")
        }
        
        # Focus-specific analysis
        if focus == "pricing":
            analysis["pricing_signals"] = self._extract_pricing_signals(content)
        elif focus == "features":
            analysis["feature_mentions"] = self._extract_feature_mentions(content)
        elif focus == "messaging":
            analysis["key_messages"] = self._extract_key_messages(content)
        elif focus == "contact":
            analysis["contact_info"] = self._extract_contact_info(content)
        else:
            analysis["general_insights"] = self._extract_general_insights(content)
        
        return analysis
    
    def _extract_pricing_signals(self, content: str) -> List[str]:
        """Extract pricing-related information from content."""
        
        pricing_keywords = ["$", "price", "cost", "pricing", "subscription", "plan", "free", "trial"]
        pricing_signals = []
        
        content_lower = content.lower()
        
        for keyword in pricing_keywords:
            if keyword in content_lower:
                # Extract sentences containing pricing keywords
                sentences = content.split(".")
                for sentence in sentences:
                    if keyword in sentence.lower():
                        pricing_signals.append(sentence.strip())
                        if len(pricing_signals) >= 5:  # Limit to first 5 signals
                            break
        
        return pricing_signals
    
    def _extract_feature_mentions(self, content: str) -> List[str]:
        """Extract feature mentions from content."""
        
        feature_keywords = [
            "feature", "capability", "functionality", "tool", "integration",
            "dashboard", "analytics", "reporting", "automation", "AI", "API"
        ]
        
        feature_mentions = []
        content_lower = content.lower()
        
        for keyword in feature_keywords:
            if keyword in content_lower:
                # Extract surrounding context
                sentences = content.split(".")
                for sentence in sentences:
                    if keyword in sentence.lower():
                        feature_mentions.append(sentence.strip())
                        if len(feature_mentions) >= 10:
                            break
        
        return feature_mentions
    
    def _extract_key_messages(self, content: str) -> List[str]:
        """Extract key marketing messages from content."""
        
        # Look for headings and emphasized text
        lines = content.split("\n")
        key_messages = []
        
        for line in lines:
            line = line.strip()
            # Look for headings (markdown format)
            if line.startswith("#") or len(line.split()) <= 10:
                if len(line) > 5:  # Avoid very short lines
                    key_messages.append(line)
                    if len(key_messages) >= 5:
                        break
        
        return key_messages
    
    def _extract_contact_info(self, content: str) -> Dict[str, List[str]]:
        """Extract contact information from content."""
        
        import re
        
        contact_info = {
            "emails": [],
            "phones": [],
            "addresses": []
        }
        
        # Email regex
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        contact_info["emails"] = re.findall(email_pattern, content)
        
        # Phone regex (basic)
        phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        contact_info["phones"] = re.findall(phone_pattern, content)
        
        # Look for address indicators
        address_keywords = ["address", "location", "office", "headquarters"]
        for keyword in address_keywords:
            if keyword.lower() in content.lower():
                # Extract sentences containing address keywords
                sentences = content.split(".")
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        contact_info["addresses"].append(sentence.strip())
                        if len(contact_info["addresses"]) >= 3:
                            break
        
        return contact_info
    
    def _extract_general_insights(self, content: str) -> Dict[str, Any]:
        """Extract general insights from content."""
        
        word_count = len(content.split())
        
        # Simple keyword analysis
        business_keywords = [
            "solution", "platform", "service", "customer", "business",
            "enterprise", "scale", "growth", "innovation", "technology"
        ]
        
        keyword_counts = {}
        content_lower = content.lower()
        
        for keyword in business_keywords:
            keyword_counts[keyword] = content_lower.count(keyword)
        
        return {
            "word_count": word_count,
            "keyword_analysis": keyword_counts,
            "top_keywords": sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def _generate_comparative_insights(
        self,
        analysis_results: Dict[str, Any],
        focus: str
    ) -> Dict[str, Any]:
        """Generate comparative insights across competitors."""
        
        successful_analyses = {url: data for url, data in analysis_results.items() if "error" not in data}
        
        if not successful_analyses:
            return {"error": "No successful competitor analyses to compare"}
        
        insights = {
            "total_competitors_analyzed": len(successful_analyses),
            "focus": focus,
            "common_patterns": [],
            "unique_features": [],
            "recommendations": []
        }
        
        # Analyze patterns based on focus
        if focus == "pricing":
            insights["pricing_comparison"] = self._compare_pricing_signals(successful_analyses)
        elif focus == "features":
            insights["feature_comparison"] = self._compare_features(successful_analyses)
        elif focus == "messaging":
            insights["messaging_comparison"] = self._compare_messaging(successful_analyses)
        
        return insights
    
    def _compare_pricing_signals(self, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Compare pricing signals across competitors."""
        
        all_signals = []
        
        for url, data in analyses.items():
            signals = data.get("analysis", {}).get("pricing_signals", [])
            all_signals.extend(signals)
        
        return {
            "total_pricing_signals": len(all_signals),
            "common_pricing_terms": ["subscription", "free trial", "enterprise"],  # Simplified
            "pricing_strategies_identified": len(set(all_signals))
        }
    
    def _compare_features(self, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Compare features across competitors."""
        
        all_features = []
        
        for url, data in analyses.items():
            features = data.get("analysis", {}).get("feature_mentions", [])
            all_features.extend(features)
        
        return {
            "total_feature_mentions": len(all_features),
            "common_features": ["dashboard", "analytics", "integration"],  # Simplified
            "unique_features_count": len(set(all_features))
        }
    
    def _compare_messaging(self, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Compare messaging across competitors."""
        
        all_messages = []
        
        for url, data in analyses.items():
            messages = data.get("analysis", {}).get("key_messages", [])
            all_messages.extend(messages)
        
        return {
            "total_messages": len(all_messages),
            "common_themes": ["innovation", "efficiency", "growth"],  # Simplified
            "messaging_diversity": len(set(all_messages))
        }
    
    async def test_connection(self) -> bool:
        """Test API connection and authentication."""
        
        try:
            # Simple scrape to test connection
            test_url = "https://example.com"
            
            result = await asyncio.to_thread(
                self.app.scrape_url,
                test_url,
                formats=['markdown']
            )
            
            # Firecrawl SDK returns a response object
            if hasattr(result, 'markdown') or hasattr(result, 'success'):
                return True
            elif isinstance(result, dict):
                return result.get("success", True)
            else:
                return True  # If we got a response, consider it success
            
        except Exception as e:
            self.logger.error("Connection test failed", error=str(e))
            return False