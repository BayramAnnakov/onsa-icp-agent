#!/usr/bin/env python3
"""
Exa Websets API integration using official exa-py SDK
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any
import json
import hashlib
from datetime import datetime
from exa_py import Exa
from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ExaWebsetsAPI:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Exa Websets API client using official exa-py SDK
        
        Args:
            api_key: Exa API key (defaults to EXA_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('EXA_API_KEY')
        if not self.api_key:
            raise ValueError("EXA_API_KEY environment variable or api_key parameter required")
        
        # Initialize Exa client
        self.exa = Exa(api_key=self.api_key)
        logger.info("Exa Websets API client initialized")
        
    def create_webset(self, search_query: str, count: int = 10, enrichments: List[Dict] = None) -> Dict:
        """
        Create a new webset with search and enrichment parameters
        
        Args:
            search_query: Search query to find relevant websites
            count: Number of results to return
            enrichments: List of enrichment parameters
            
        Returns:
            Webset creation response with webset ID
        """
        enrichments = enrichments or []
        
        # Convert enrichments to CreateEnrichmentParameters
        enrichment_params = []
        for enrich in enrichments:
            enrichment_params.append(
                CreateEnrichmentParameters(
                    description=enrich.get("description", ""),
                    format=enrich.get("format", "text")
                )
            )
        
        try:
            # Create webset using exa-py SDK
            webset = self.exa.websets.create(
                params=CreateWebsetParameters(
                    search={
                        "query": search_query,
                        "count": count
                    },
                    enrichments=enrichment_params
                )
            )
            
            logger.info(f"Webset created with ID: {webset.id}")
            return {"id": webset.id, "status": "created"}
            
        except Exception as e:
            logger.error(f"Error creating webset: {e}")
            return {}
    
    def get_webset(self, webset_id: str) -> Dict:
        """
        Get webset details by ID
        
        Args:
            webset_id: ID of the webset
            
        Returns:
            Webset details including status
        """
        try:
            # Get webset status using exa-py SDK
            webset = self.exa.websets.get(webset_id)
            
            return {
                "id": webset.id,
                "status": webset.status,
                "created_at": getattr(webset, 'created_at', None),
                "updated_at": getattr(webset, 'updated_at', None)
            }
            
        except Exception as e:
            logger.error(f"Error getting webset {webset_id}: {e}")
            return {}
    
    def list_webset_items(self, webset_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        List items in a webset
        
        Args:
            webset_id: ID of the webset
            limit: Maximum number of items to return
            offset: Offset for pagination
            
        Returns:
            List of webset items
        """
        try:
            # Get webset items using exa-py SDK
            items = self.exa.websets.items.list(webset_id=webset_id)
            
            # Convert items to dictionaries
            item_list = []
            for item in items.data[offset:offset+limit]:
                item_dict = json.loads(item.model_dump_json())
                item_list.append(item_dict)
            
            return item_list
            
        except Exception as e:
            logger.error(f"Error listing webset items for {webset_id}: {e}")
            return []
    
    def wait_for_completion(self, webset_id: str, max_wait_time: int = 300, check_interval: int = 10) -> bool:
        """
        Wait for webset to complete processing
        
        Args:
            webset_id: ID of the webset
            max_wait_time: Maximum time to wait in seconds (default: 300 seconds = 5 minutes)
            check_interval: How often to check status in seconds (not used with SDK wait)
            
        Returns:
            True if completed successfully, False if timed out or failed
        """
        try:
            logger.info(f"Waiting for webset {webset_id} to complete (timeout: {max_wait_time}s)...")
            
            # Use exa-py SDK's built-in wait function
            webset = self.exa.websets.wait_until_idle(webset_id, timeout=max_wait_time)
            
            logger.info(f"Webset {webset_id} completed with status: {webset.status}")
            return webset.status in ["completed", "idle"]
            
        except Exception as e:
            logger.error(f"Error waiting for webset completion: {e}")
            return False
    
    def wait_for_items(self, webset_id: str, wait_time: int = 30, min_items: int = 5) -> bool:
        """
        Wait for a specific time and check if items are available
        
        Args:
            webset_id: ID of the webset
            wait_time: How long to wait in seconds (default: 30)
            min_items: Minimum number of items to consider ready (default: 5)
            
        Returns:
            True if items are available, False otherwise
        """
        try:
            logger.info(f"Waiting {wait_time} seconds for webset {webset_id} to process items...")
            time.sleep(wait_time)
            
            # Check if items are available
            items = self.list_webset_items(webset_id, limit=min_items)
            item_count = len(items)
            
            if item_count >= min_items:
                logger.info(f"Found {item_count} items in webset {webset_id} (required: {min_items})")
                return True
            else:
                logger.info(f"Only {item_count} items available (required: {min_items}), waiting longer...")
                # Wait a bit more and check again
                time.sleep(wait_time)
                items = self.list_webset_items(webset_id, limit=min_items)
                item_count = len(items)
                logger.info(f"After additional wait: {item_count} items available")
                return item_count > 0
            
        except Exception as e:
            logger.error(f"Error waiting for webset items: {e}")
            return False


class ExaExtractor:
    def __init__(self, api_key: Optional[str] = None, cache_manager: Optional[Any] = None):
        """
        Initialize general-purpose Exa extractor using Exa Websets
        
        Args:
            api_key: Exa API key
            cache_manager: Optional cache manager for webset ID caching
        """
        self.exa_api = ExaWebsetsAPI(api_key)
        self.cache_manager = cache_manager
        self._webset_cache = {}  # In-memory cache for webset IDs
    
    def _generate_webset_cache_key(self, search_query: str, enrichments: List[Dict], count: int) -> str:
        """Generate a unique cache key for a webset configuration."""
        # Sort enrichments to ensure consistent key generation
        sorted_enrichments = sorted(enrichments, key=lambda x: x.get("description", ""))
        
        cache_data = {
            "search_query": search_query,
            "enrichments": sorted_enrichments,
            "count": count
        }
        
        # Create a hash of the configuration
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_cached_webset_id(self, cache_key: str) -> Optional[str]:
        """Get cached webset ID if available."""
        # Check in-memory cache first
        if cache_key in self._webset_cache:
            webset_id = self._webset_cache[cache_key]
            logger.info(f"Found webset ID in memory cache: {webset_id}")
            return webset_id
        
        # Check persistent cache if available
        if self.cache_manager:
            cached_data = self.cache_manager.get(cache_key, namespace="exa_websets")
            if cached_data and isinstance(cached_data, dict):
                webset_id = cached_data.get("webset_id")
                if webset_id:
                    # Verify the webset still exists and is valid
                    webset_info = self.exa_api.get_webset(webset_id)
                    if webset_info and webset_info.get("status") in ["completed", "idle"]:
                        # Update memory cache
                        self._webset_cache[cache_key] = webset_id
                        logger.info(f"Found valid webset ID in persistent cache: {webset_id}")
                        return webset_id
                    else:
                        logger.warning(f"Cached webset {webset_id} is no longer valid, will create new one")
        
        return None
    
    def _cache_webset_id(self, cache_key: str, webset_id: str) -> None:
        """Cache webset ID for future use."""
        # Update in-memory cache
        self._webset_cache[cache_key] = webset_id
        
        # Update persistent cache if available
        if self.cache_manager:
            cache_data = {
                "webset_id": webset_id,
                "created_at": datetime.now().isoformat()
            }
            # Cache for 7 days (604800 seconds)
            self.cache_manager.set(cache_key, cache_data, ttl=604800, namespace="exa_websets")
            logger.info(f"Cached webset ID {webset_id} with key {cache_key}")
    
    def extract_companies(self, search_query: str, enrichments: List[Dict] = None, count: int = 50) -> List[Dict]:
        """
        Extract companies using a custom search query and enrichments
        
        Args:
            search_query: Search query to find companies
            enrichments: List of enrichment dictionaries
            count: Number of results to return
            
        Returns:
            List of company dictionaries
        """
        logger.info(f"Extracting companies using Exa Websets with query: {search_query}")
        
        # Default enrichments if none provided
        if not enrichments:
            enrichments = [
                {
                    "description": "Company name",
                    "format": "text"
                },
                {
                    "description": "Company description",
                    "format": "text"
                },
                {
                    "description": "Company location",
                    "format": "text"
                },
                {
                    "description": "Company website URL",
                    "format": "text"
                },
                {
                    "description": "Industry or business sector",
                    "format": "text"
                },
                {
                    "description": "Company size (number of employees)",
                    "format": "text"
                },
                {
                    "description": "Technologies used",
                    "format": "text"
                },
                {
                    "description": "Recent news or announcements",
                    "format": "text"
                }
            ]
        
        # Generate cache key for this configuration
        cache_key = self._generate_webset_cache_key(search_query, enrichments, count)
        
        # Check if we have a cached webset ID
        webset_id = self._get_cached_webset_id(cache_key)
        
        if not webset_id:
            # No cached webset, create a new one
            logger.info("No cached webset found, creating new one")
            webset = self.exa_api.create_webset(
                search_query=search_query,
                count=count,
                enrichments=enrichments
            )
            
            webset_id = webset.get("id")
            if not webset_id:
                logger.error("Failed to create webset")
                return []
            
            logger.info(f"Created webset {webset_id}, waiting for initial results...")
            
            # Wait for items to be available (30 seconds should be enough for initial results)
            if not self.exa_api.wait_for_items(webset_id, wait_time=30, min_items=5):
                logger.warning("Initial results not ready after 30 seconds, checking available items...")
            
            # Cache the webset ID for future use
            self._cache_webset_id(cache_key, webset_id)
        else:
            logger.info(f"Using cached webset {webset_id}")
        
        # Get the results
        items = self.exa_api.list_webset_items(webset_id)
        logger.info(f"Retrieved {len(items)} items from webset")
        
        # Parse companies from results
        companies = []
        for item in items:
            try:
                company = self._parse_company_item(item)
                if company:
                    companies.append(company)
            except Exception as e:
                logger.debug(f"Error parsing company item: {e}")
                continue
        
        logger.info(f"Extracted {len(companies)} companies")
        return companies
    
    def extract_people(self, search_query: str, enrichments: List[Dict] = None, count: int = 50) -> List[Dict]:
        """
        Extract people/contacts using a custom search query and enrichments
        
        Args:
            search_query: Search query to find people
            enrichments: List of enrichment dictionaries
            count: Number of results to return
            
        Returns:
            List of people dictionaries
        """
        logger.info(f"Extracting people using Exa Websets with query: {search_query}")
        
        # Default enrichments if none provided
        if not enrichments:
            enrichments = [
                {
                    "description": "Person full name",
                    "format": "text"
                },
                {
                    "description": "Job title or role",
                    "format": "text"
                },
                {
                    "description": "Company name",
                    "format": "text"
                },
                {
                    "description": "LinkedIn profile URL",
                    "format": "text"
                },
                {
                    "description": "Professional background or bio",
                    "format": "text"
                }
            ]
        
        # Generate cache key for this configuration
        cache_key = self._generate_webset_cache_key(search_query, enrichments, count)
        
        # Check if we have a cached webset ID
        webset_id = self._get_cached_webset_id(cache_key)
        
        if not webset_id:
            # No cached webset, create a new one
            logger.info("No cached webset found, creating new one")
            webset = self.exa_api.create_webset(
                search_query=search_query,
                count=count,
                enrichments=enrichments
            )
            
            webset_id = webset.get("id")
            if not webset_id:
                logger.error("Failed to create webset")
                return []
            
            logger.info(f"Created webset {webset_id}, waiting for initial results...")
            
            # Wait for items to be available (30 seconds should be enough for initial results)
            if not self.exa_api.wait_for_items(webset_id, wait_time=30, min_items=5):
                logger.warning("Initial results not ready after 30 seconds, checking available items...")
            
            # Cache the webset ID for future use
            self._cache_webset_id(cache_key, webset_id)
        else:
            logger.info(f"Using cached webset {webset_id}")
        
        # Get the results
        items = self.exa_api.list_webset_items(webset_id)
        logger.info(f"Retrieved {len(items)} items from webset")
        
        # Parse people from results
        people = []
        for i, item in enumerate(items):
            try:
                # Log first few items in detail for debugging
                if i < 3:
                    logger.info(f"Parsing item {i} - keys: {list(item.keys()) if isinstance(item, dict) else 'not a dict'}")
                    if isinstance(item, dict) and "enrichments" in item:
                        enrichments = item["enrichments"]
                        if isinstance(enrichments, dict):
                            logger.info(f"Item {i} enrichments keys: {list(enrichments.keys())[:5]}")
                        elif isinstance(enrichments, list):
                            logger.info(f"Item {i} enrichments is a list with {len(enrichments)} items")
                
                person_data = self._parse_person_item(item)
                if person_data:
                    people.extend(person_data if isinstance(person_data, list) else [person_data])
                    logger.info(f"Extracted {len(person_data) if isinstance(person_data, list) else 1} people from item {i}")
                else:
                    logger.debug(f"No people extracted from item {i}")
            except Exception as e:
                logger.error(f"Error parsing person item {i}: {e}", exc_info=True)
                continue
        
        # Remove duplicates
        unique_people = []
        seen_names = set()
        for person in people:
            name = person.get('name', '').strip().lower()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_people.append(person)
        
        logger.info(f"Extracted {len(unique_people)} unique people")
        return unique_people
    
    def _parse_company_item(self, item: Dict) -> Optional[Dict]:
        """
        Parse a webset item to extract company information
        
        Args:
            item: Webset item data
            
        Returns:
            Company dictionary or None
        """
        enrichments = item.get("enrichments", {})
        url = item.get("url", "")
        
        # Extract company data from enrichments
        name = enrichments.get("Company name", "").strip()
        description = enrichments.get("Company description", "").strip()
        location = enrichments.get("Company location", "").strip()
        website = enrichments.get("Company website URL", "").strip()
        industry = enrichments.get("Industry or business sector", "").strip()
        
        # Basic validation
        if not name:
            return None
        
        return {
            'name': name,
            'description': description,
            'location': location,
            'website': website,
            'industry': industry,
            'source_url': url,
            'extracted_at': datetime.now().isoformat()
        }
    
    def _parse_person_item(self, item: Dict) -> List[Dict]:
        """
        Parse a webset item to extract person information
        
        Args:
            item: Webset item data
            
        Returns:
            List of person dictionaries
        """
        # Log the item structure for debugging
        logger.debug(f"Parsing person item with keys: {list(item.keys())}")
        
        # Check if item has properties.person (structured data)
        properties = item.get("properties", {})
        if properties.get("type") == "person" and "person" in properties:
            person_info = properties["person"]
            
            # Extract structured person data
            name = (person_info.get("name") or "").strip()
            role = (person_info.get("position") or "").strip()
            company = person_info.get("company", {}).get("name", "") if isinstance(person_info.get("company"), dict) else ""
            linkedin_url = (properties.get("url") or "").strip()
            
            # Basic validation
            if not name:
                return []
            
            return [{
                'name': name,
                'title': role,
                'company': company,
                'linkedin_url': linkedin_url,
                'email': "",  # Not available in structured data
                'location': person_info.get("location", ""),
                'description': properties.get("description", ""),
                'source_url': properties.get("url", ""),
                'extracted_at': datetime.now().isoformat()
            }]
        
        # Try to parse enrichments - handle both dict and list formats
        enrichments = item.get("enrichments", {})
        
        # Log enrichments structure
        if enrichments:
            logger.debug(f"Enrichments type: {type(enrichments)}, keys/length: {list(enrichments.keys()) if isinstance(enrichments, dict) else len(enrichments) if isinstance(enrichments, list) else 'empty'}")
        
        # Initialize default values
        name = ""
        role = ""
        company = ""
        linkedin_url = ""
        email = ""
        bio = ""
        
        # Handle enrichments as dictionary (most common case from Exa)
        if isinstance(enrichments, dict):
            # Try different possible keys for person data
            name = enrichments.get("Person full name", "") or enrichments.get("name", "") or enrichments.get("Name", "")
            role = enrichments.get("Current job title or role", "") or enrichments.get("Job title or role", "") or enrichments.get("title", "") or enrichments.get("role", "")
            company = enrichments.get("Current company name", "") or enrichments.get("Company name", "") or enrichments.get("company", "")
            linkedin_url = enrichments.get("LinkedIn profile URL", "") or enrichments.get("linkedin_url", "") or enrichments.get("linkedin", "")
            email = enrichments.get("Email address if available", "") or enrichments.get("email", "")
            bio = enrichments.get("Professional background and expertise", "") or enrichments.get("Professional background or bio", "") or enrichments.get("bio", "")
            
            # Clean up the values
            name = str(name).strip() if name else ""
            role = str(role).strip() if role else ""
            company = str(company).strip() if company else ""
            linkedin_url = str(linkedin_url).strip() if linkedin_url else ""
            email = str(email).strip() if email else ""
            bio = str(bio).strip() if bio else ""
            
            logger.debug(f"Parsed from dict - name: {name}, role: {role}, company: {company}")
            
        # Handle enrichments as list (legacy format)
        elif isinstance(enrichments, list):
            # Flatten nested lists if needed
            if enrichments and isinstance(enrichments[0], list):
                enrichments = enrichments[0]
            
            # Extract based on position in array
            if len(enrichments) > 0:
                if isinstance(enrichments[0], dict):
                    name = enrichments[0].get("result", "").strip()
                elif isinstance(enrichments[0], str):
                    name = enrichments[0].strip()
                    
            if len(enrichments) > 1:
                if isinstance(enrichments[1], dict):
                    role = enrichments[1].get("result", "").strip()
                elif isinstance(enrichments[1], str):
                    role = enrichments[1].strip()
                    
            if len(enrichments) > 2:
                if isinstance(enrichments[2], dict):
                    company = enrichments[2].get("result", "").strip()
                elif isinstance(enrichments[2], str):
                    company = enrichments[2].strip()
                    
            if len(enrichments) > 3:
                if isinstance(enrichments[3], dict):
                    linkedin_url = enrichments[3].get("result", "").strip()
                elif isinstance(enrichments[3], str):
                    linkedin_url = enrichments[3].strip()
                    
            if len(enrichments) > 4:
                if isinstance(enrichments[4], dict):
                    email = enrichments[4].get("result", "").strip()
                elif isinstance(enrichments[4], str):
                    email = enrichments[4].strip()
                    
            if len(enrichments) > 5:
                if isinstance(enrichments[5], dict):
                    bio = enrichments[5].get("result", "").strip()
                elif isinstance(enrichments[5], str):
                    bio = enrichments[5].strip()
            
            logger.debug(f"Parsed from list - name: {name}, role: {role}, company: {company}")
        
        # Basic validation - require at least a name
        if not name:
            logger.debug("No name found in item, skipping")
            return []
        
        # Handle multiple people in single response
        people = []
        
        # If the name contains multiple names (comma or "and" separated), split them
        if "," in name or " and " in name:
            names = []
            if "," in name:
                names = [n.strip() for n in name.split(",")]
            elif " and " in name:
                names = [n.strip() for n in name.split(" and ")]
            
            for individual_name in names:
                if individual_name:
                    people.append({
                        'name': individual_name,
                        'title': role,
                        'role': role,  # Include both for compatibility
                        'company': company,
                        'linkedin_url': linkedin_url if len(names) == 1 else "",  # Only assign if single person
                        'email': email if len(names) == 1 else "",
                        'bio': bio,
                        'source_url': item.get("url", ""),
                        'extracted_at': datetime.now().isoformat()
                    })
        else:
            # Single person
            people.append({
                'name': name,
                'title': role,
                'role': role,  # Include both for compatibility
                'company': company,
                'linkedin_url': linkedin_url,
                'email': email,
                'bio': bio,
                'source_url': item.get("url", ""),
                'extracted_at': datetime.now().isoformat()
            })
        
        logger.debug(f"Extracted {len(people)} people from item")
        return people
    
    def build_enhanced_search_query(self, base_query: str, icp_criteria: Dict[str, Any], search_type: str = "people") -> str:
        """
        Build an enhanced search query incorporating ICP criteria like buying signals and pain points.
        
        Args:
            base_query: Base search query
            icp_criteria: ICP criteria dictionary
            search_type: Type of search ("people" or "companies")
            
        Returns:
            Enhanced search query string
        """
        search_parts = [base_query]
        
        # Add pain points as search context
        pain_points = icp_criteria.get("pain_points", [])
        if pain_points:
            pain_point_keywords = []
            for pain_point in pain_points[:2]:  # Limit to top 2
                if "efficiency" in pain_point.lower():
                    pain_point_keywords.extend(["improving efficiency", "productivity challenges"])
                elif "growth" in pain_point.lower():
                    pain_point_keywords.extend(["scaling", "growth challenges", "expansion"])
                elif "sales" in pain_point.lower():
                    pain_point_keywords.extend(["sales performance", "revenue growth", "pipeline management"])
                elif "automation" in pain_point.lower():
                    pain_point_keywords.extend(["process automation", "workflow optimization"])
            
            if pain_point_keywords:
                if search_type == "companies":
                    search_parts.append(f"companies dealing with {' OR '.join(pain_point_keywords[:2])}")
                else:
                    search_parts.append(f"professionals addressing {' OR '.join(pain_point_keywords[:2])}")
        
        # Add buying signals
        buying_signals = icp_criteria.get("buying_signals", [])
        if buying_signals:
            signal_keywords = []
            for signal in buying_signals[:2]:  # Limit to top 2
                if "budget" in signal.lower():
                    signal_keywords.extend(["budget allocated", "funding secured", "investment round"])
                elif "looking" in signal.lower() or "evaluating" in signal.lower():
                    signal_keywords.extend(["evaluating solutions", "vendor selection", "RFP"])
                elif "hiring" in signal.lower():
                    signal_keywords.extend(["hiring", "team expansion", "growing team", "job openings"])
                elif "implementing" in signal.lower():
                    signal_keywords.extend(["implementing new", "digital transformation", "modernization"])
            
            if signal_keywords:
                search_parts.append(f"showing signs of {' OR '.join(signal_keywords[:2])}")
        
        # Add tech stack for companies
        if search_type == "companies":
            tech_stack = icp_criteria.get("tech_stack", [])
            if tech_stack:
                search_parts.append(f"using {' OR '.join(tech_stack[:2])}")
        
        # Add goals
        goals = icp_criteria.get("goals", [])
        if goals:
            search_parts.append(f"focused on {' OR '.join(goals[:2])}")
        
        # Combine all parts
        enhanced_query = " ".join(search_parts)
        
        # Limit query length for API compatibility
        if len(enhanced_query) > 500:
            return base_query  # Fallback to base query if too long
        
        logger.info(f"Built enhanced {search_type} search query: {enhanced_query}")
        return enhanced_query
    
    def clear_webset_cache(self) -> None:
        """Clear all cached webset IDs."""
        self._webset_cache.clear()
        if self.cache_manager:
            count = self.cache_manager.clear_namespace("exa_websets")
            logger.info(f"Cleared {count} cached webset IDs from persistent cache")
        else:
            logger.info("Cleared in-memory webset cache")


def test_exa_integration():
    """Test function for Exa Websets integration"""
    try:
        extractor = ExaExtractor()
        
        # Test company extraction
        logger.info("Testing company extraction...")
        companies = extractor.extract_companies(
            search_query="technology startup companies San Francisco",
            count=5
        )
        
        if companies:
            logger.info(f"Found {len(companies)} companies")
            for i, company in enumerate(companies[:5]):
                logger.info(f"{i+1}. {company['name']} - {company.get('description', 'No description')}")
        else:
            logger.warning("No companies found")
            
        # Test people extraction
        logger.info("Testing people extraction...")
        people = extractor.extract_people(
            search_query="CEO technology companies LinkedIn",
            count=5
        )
        
        if people:
            logger.info(f"Found {len(people)} people")
            for i, person in enumerate(people[:5]):
                logger.info(f"{i+1}. {person['name']} - {person.get('role', 'Unknown role')} at {person.get('company', 'Unknown company')}")
        else:
            logger.warning("No people found")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == "__main__":
    test_exa_integration()