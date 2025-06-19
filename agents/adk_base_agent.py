"""Base agent class using Google ADK (Agent Development Kit)."""

import os
import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime

# Google ADK imports
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.tools import FunctionTool
from google.adk.sessions import InMemorySessionService
from google.genai import types

import structlog
from pydantic import BaseModel, Field

from models import Conversation, ConversationMessage, MessageRole
from utils.config import Config
from utils.cache import CacheManager


class AgentMessage(BaseModel):
    """Message structure for agent communication."""
    
    id: str = Field(..., description="Unique message identifier")
    sender: str = Field(..., description="Sending agent identifier")
    recipient: str = Field(..., description="Recipient agent identifier") 
    message_type: str = Field(..., description="Type of message")
    content: Dict[str, Any] = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")


class AgentResponse(BaseModel):
    """Response structure for agent communication."""
    
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if any")


class ADKAgent(ABC):
    """
    Base agent class implementing Google ADK with external tools.
    
    This class extends Google ADK's BaseAgent to provide:
    - Integration with external APIs as tools
    - Structured conversation management
    - Caching capabilities
    - Configuration management
    """
    
    def __init__(
        self,
        agent_name: str,
        agent_description: str,
        config: Config,
        cache_manager: Optional[CacheManager] = None,
        tools: Optional[List[Any]] = None
    ):
        # Store configuration
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.agent_id = str(uuid.uuid4())
        self.config = config
        self.cache_manager = cache_manager or CacheManager(config.cache)
        
        # Set up logging
        self.logger = structlog.get_logger().bind(agent=agent_name)
        
        # Agent state
        self.active_conversations = {}
        
        # External API clients (to be initialized by subclasses)
        self.external_clients = {}
        
        # Tool list for Google ADK
        self.tools = tools or []
        
        # Session service for Google ADK
        self.session_service = InMemorySessionService()
        
        # Initialize the Google ADK Agent
        self.adk_agent = None
        self.runner = None
        
        self.logger.info("ADK Agent initialized", model=config.gemini.model)
    
    def add_external_tool(
        self,
        name: str,
        description: str,
        func: Callable,
        client: Optional[Any] = None
    ) -> None:
        """Add an external API as a tool."""
        
        if client:
            self.external_clients[name] = client
        
        # Create a tool from the function (FunctionTool only accepts func parameter)
        tool = FunctionTool(func=func)
        
        # Store tool metadata separately
        if not hasattr(self, 'tool_metadata'):
            self.tool_metadata = {}
        self.tool_metadata[func.__name__] = {
            'name': name,
            'description': description
        }
        
        # Add to tools list
        self.tools.append(tool)
        
        # Recreate the ADK agent with updated tools
        self._create_adk_agent()
        
        self.logger.info("Added external tool", tool_name=name)
    
    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process a message using Google ADK."""
        
        # Ensure ADK agent is created
        if not self.adk_agent:
            self._create_adk_agent()
        
        # Get or create conversation
        if conversation_id:
            conversation = self.get_conversation(conversation_id)
            if not conversation:
                conversation = Conversation(
                    id=conversation_id,
                    user_id="default"
                )
                self.active_conversations[conversation_id] = conversation
        else:
            conversation_id = f"conv_{int(datetime.now().timestamp())}"
            conversation = Conversation(
                id=conversation_id,
                user_id="default"
            )
            self.active_conversations[conversation_id] = conversation
        
        # Add user message to conversation
        conversation.add_message(MessageRole.USER, message)
        
        # Create or get session
        user_id = conversation.user_id
        session = await self.session_service.create_session(
            app_name="icp_agent_system",
            user_id=user_id,
            session_id=conversation_id
        )
        
        try:
            # Create content for Google ADK
            content = types.Content(
                role='user',
                parts=[types.Part(text=message)]
            )
            
            # Run the agent
            response_text = ""
            events_async = self.runner.run_async(
                session_id=session.id,
                user_id=user_id,
                new_message=content
            )
            
            async for event in events_async:
                if event.content and event.content.parts:
                    if text := ''.join(part.text or '' for part in event.content.parts):
                        response_text += text
            
            # Add assistant response to conversation
            conversation.add_message(
                MessageRole.ASSISTANT,
                response_text,
                agent_name=self.agent_name
            )
            
            return response_text
            
        except Exception as e:
            self.logger.error("Error processing message", error=str(e))
            raise
    
    def _format_conversation_history(self, conversation: Conversation) -> str:
        """Format conversation history for the model."""
        history_lines = []
        for msg in conversation.messages[-10:]:  # Last 10 messages
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            history_lines.append(f"{role}: {msg.content}")
        
        return "\n".join(history_lines) if history_lines else ""
    
    async def search_companies_hdw(
        self,
        query: str,
        limit: int = 10,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for companies using HorizonDataWave API.
        
        Use this tool when you need to find companies based on search criteria.
        
        Args:
            query: Search query for companies
            limit: Maximum number of companies to return
            location: Optional location filter
            
        Returns:
            Dictionary with company search results
        """
        try:
            hdw_client = self.external_clients.get("horizondatawave")
            if not hdw_client:
                return {"status": "error", "error_message": "HorizonDataWave client not available"}
            
            # Use caching for API calls
            cache_key = f"hdw_companies_{query}_{limit}_{location}"
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return {"status": "success", "companies": cached_result, "cached": True}
            
            # Call the actual API (sync method) - limit to 1 for now
            companies = hdw_client.search_companies(
                keywords=query,
                count=min(limit, 1),  # Limit to 1 for now
                timeout=300
            )
            
            # Cache the result
            self.cache_manager.set(cache_key, companies)
            
            self.logger.info("Companies found via HDW", count=len(companies))
            return {"status": "success", "companies": companies}
            
        except Exception as e:
            self.logger.error("Error searching companies with HDW", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def search_people_hdw(
        self,
        query: str,
        limit: int = 10,
        current_companies: Optional[List[str]] = None,
        current_titles: Optional[List[str]] = None,
        locations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Search for people using HorizonDataWave LinkedIn API.
        
        NOTE: This uses the less expensive search_linkedin_users endpoint.
        For more advanced searches, use search_people_nav_hdw which uses search_nav_search_users.
        
        Args:
            query: Search query for people
            limit: Maximum number of people to return
            current_companies: Filter by current companies
            current_titles: Filter by current job titles
            locations: Filter by locations
            
        Returns:
            Dictionary with people search results
        """
        try:
            hdw_client = self.external_clients.get("horizondatawave")
            if not hdw_client:
                return {"status": "error", "error_message": "HorizonDataWave client not available"}
            
            # Use caching for API calls
            cache_key = f"hdw_people_{query}_{limit}_{current_companies}_{current_titles}"
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return {"status": "success", "people": cached_result, "cached": True}
            
            # Call HDW search_linkedin_users - limit to 1 for now
            users = hdw_client.search_linkedin_users(
                keywords=query,
                current_companies=current_companies,
                current_titles=current_titles,
                locations=locations,
                count=min(limit, 1),  # Limit to 1 for now
                timeout=300
            )
            
            # Convert to standard format
            people = []
            for user in users:
                people.append({
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "name": f"{user.first_name} {user.last_name}",
                    "title": user.current_position_title,
                    "company": user.current_company_name,
                    "linkedin_url": user.url,
                    "location": user.location,
                    "source": "hdw"
                })
            
            # Cache the result
            self.cache_manager.set(cache_key, people)
            
            self.logger.info("People found via HDW", count=len(people))
            return {"status": "success", "people": people}
            
        except Exception as e:
            self.logger.error("Error searching people with HDW", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def search_people_exa(
        self,
        query: str,
        limit: int = 10,
        role_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for people using Exa Websets API.
        
        Use this tool when you need to find people/contacts based on search criteria.
        
        Args:
            query: Search query for people
            limit: Maximum number of people to return
            role_filter: Optional job role filter
            
        Returns:
            Dictionary with people search results
        """
        try:
            # Use caching for API calls
            cache_key = f"exa_people_{query}_{limit}_{role_filter}"
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return {"status": "success", "people": cached_result, "cached": True}
            
            # Use ExaExtractor for people extraction
            from integrations.exa_websets import ExaExtractor
            try:
                extractor = ExaExtractor()
                people = extractor.extract_people(
                    search_query=query,
                    count=limit
                )
            except ValueError as e:
                # Exa API key not configured
                self.logger.warning("Exa API not configured", error=str(e))
                return {"status": "error", "error_message": "Exa API key not configured"}
            
            # Cache the result
            self.cache_manager.set(cache_key, people)
            
            self.logger.info("People found via Exa", count=len(people))
            return {"status": "success", "people": people}
            
        except Exception as e:
            self.logger.error("Error searching people with Exa", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def scrape_website_firecrawl(
        self,
        url: str,
        include_links: bool = False,
        max_depth: int = 1
    ) -> Dict[str, Any]:
        """Scrape website content using Firecrawl API.
        
        Use this tool when you need to extract content from websites.
        
        Args:
            url: Website URL to scrape
            include_links: Whether to include links in the content
            max_depth: Maximum crawl depth
            
        Returns:
            Dictionary with scraped website content
        """
        try:
            firecrawl_client = self.external_clients.get("firecrawl")
            if not firecrawl_client:
                return {"status": "error", "error_message": "Firecrawl client not available"}
            
            # Use caching for API calls
            cache_key = f"firecrawl_{url}_{include_links}_{max_depth}"
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                return {"status": "success", "content": cached_result, "cached": True}
            
            # Call the actual API (async method)
            content = await firecrawl_client.scrape_url(
                url=url,
                include_links=include_links,
                include_metadata=True,
                format_type="markdown"
            )
            
            # Cache the result
            self.cache_manager.set(cache_key, content)
            
            self.logger.info("Website scraped via Firecrawl", url=url)
            return {"status": "success", "content": content}
            
        except Exception as e:
            self.logger.error("Error scraping website with Firecrawl", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def search_industries_hdw(
        self,
        name: str,
        count: int = 5
    ) -> Dict[str, Any]:
        """Search for industries and get their URNs using HorizonDataWave API.
        
        Args:
            name: Industry name to search for
            count: Maximum number of results to return
            
        Returns:
            Dictionary with industry search results including URNs
        """
        try:
            hdw_client = self.external_clients.get("horizondatawave")
            if not hdw_client:
                return {"status": "error", "error_message": "HorizonDataWave client not available"}
            
            # Search for industries
            industries = hdw_client.search_industries(
                name=name,
                count=count,
                timeout=300
            )
            
            # Format results with URNs
            results = []
            for industry in industries:
                results.append({
                    "name": industry.name,
                    "urn": f"urn:li:industry:{industry.urn.value}",
                    "type": industry.type
                })
            
            self.logger.info(f"Found {len(results)} industries for '{name}'")
            return {"status": "success", "industries": results}
            
        except Exception as e:
            self.logger.error("Error searching industries with HDW", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def search_people_nav_hdw(
        self,
        keywords: Optional[str] = None,
        current_titles: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        levels: Optional[List[str]] = None,
        company_sizes: Optional[List[str]] = None,
        count: int = 10
    ) -> Dict[str, Any]:
        """Search for people using HorizonDataWave's expensive search_nav_search_users endpoint.
        
        WARNING: This is an expensive endpoint. Use caching and limit results carefully.
        
        Args:
            keywords: Search keywords
            current_titles: List of job titles to filter by
            locations: List of location URNs (use search_locations_hdw to get URNs)
            industries: List of industry URNs (use search_industries_hdw to get URNs)
            levels: List of seniority levels (VP, Director, C-Level, etc.)
            company_sizes: List of company size enums (51-200, 201-500, etc.)
            count: Maximum number of results (default: 10, use sparingly)
            
        Returns:
            Dictionary with people search results
        """
        try:
            hdw_client = self.external_clients.get("horizondatawave")
            if not hdw_client:
                return {"status": "error", "error_message": "HorizonDataWave client not available"}
            
            # Create cache key with all parameters
            cache_key = f"hdw_nav_{keywords}_{current_titles}_{locations}_{industries}_{levels}_{company_sizes}_{count}"
            cached_result = self.cache_manager.get(cache_key)
            if cached_result:
                self.logger.info("Returning cached HDW nav search results")
                return {"status": "success", "people": cached_result, "cached": True}
            
            self.logger.warning(f"Using expensive HDW search_nav_search_users endpoint for {count} results")
            
            # Call the expensive endpoint
            users = hdw_client.search_nav_search_users(
                keywords=keywords,
                current_titles=current_titles,
                locations=locations,
                industry=industries,  # Note: HDW uses 'industry' not 'industries'
                levels=levels,
                company_sizes=company_sizes,
                count=count,
                timeout=300
            )
            
            # Convert to standard format
            people = []
            for user in users:
                person_data = {
                    "name": user.name,
                    "first_name": user.name.split()[0] if user.name else "Unknown",
                    "last_name": " ".join(user.name.split()[1:]) if user.name and len(user.name.split()) > 1 else "",
                    "headline": user.headline,
                    "location": user.location,
                    "linkedin_url": user.url,
                    "is_premium": user.is_premium
                }
                
                # Add current company info
                if user.current_companies:
                    current_company = user.current_companies[0]
                    person_data["title"] = current_company.position
                    person_data["company"] = current_company.company.name if current_company.company else "Unknown"
                    person_data["company_joined"] = current_company.joined
                else:
                    person_data["title"] = "Unknown"
                    person_data["company"] = "Unknown"
                
                people.append(person_data)
            
            # Cache the result for a long time (1 year)
            self.cache_manager.set(cache_key, people, ttl=31536000)
            
            self.logger.info(f"Found {len(people)} people via HDW nav search")
            return {"status": "success", "people": people}
            
        except Exception as e:
            self.logger.error("Error with HDW nav search", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def search_locations_hdw(
        self,
        name: str,
        count: int = 5
    ) -> Dict[str, Any]:
        """Search for locations and get their URNs using HorizonDataWave API.
        
        Args:
            name: Location name to search for
            count: Maximum number of results to return
            
        Returns:
            Dictionary with location search results including URNs
        """
        try:
            hdw_client = self.external_clients.get("horizondatawave")
            if not hdw_client:
                return {"status": "error", "error_message": "HorizonDataWave client not available"}
            
            # Search for locations
            locations = hdw_client.search_locations(
                name=name,
                count=count,
                timeout=300
            )
            
            # Format results with URNs
            results = []
            for location in locations:
                results.append({
                    "name": location.name,
                    "urn": f"urn:li:geo:{location.urn.value}",
                    "type": location.type
                })
            
            self.logger.info(f"Found {len(results)} locations for '{name}'")
            return {"status": "success", "locations": results}
            
        except Exception as e:
            self.logger.error("Error searching locations with HDW", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    def setup_external_tools(self) -> None:
        """Setup external API tools. Override in subclasses to add specific tools."""
        # Base implementation does not add any tools
        # Subclasses should call specific tool setup methods as needed
        pass
    
    def setup_company_search_tools(self) -> None:
        """Setup company search tools (HorizonDataWave)."""
        self.add_external_tool(
            name="search_companies_hdw",
            description="Search for companies using HorizonDataWave API. Use when looking for company information, LinkedIn profiles, or business data.",
            func=self.search_companies_hdw
        )
        
        self.add_external_tool(
            name="search_industries_hdw",
            description="Search for industry URNs using HorizonDataWave. Use to get industry URNs for company searches.",
            func=self.search_industries_hdw
        )
        
        self.add_external_tool(
            name="search_locations_hdw",
            description="Search for location URNs using HorizonDataWave. Use to get location URNs for company/people searches.",
            func=self.search_locations_hdw
        )
    
    def setup_people_search_tools(self) -> None:
        """Setup people search tools (HorizonDataWave and Exa)."""
        self.add_external_tool(
            name="search_people_hdw",
            description="Search for people using HorizonDataWave LinkedIn API. Use when looking for LinkedIn user profiles with specific titles or companies.",
            func=self.search_people_hdw
        )
        
        self.add_external_tool(
            name="search_people_exa",
            description="Search for people using Exa Websets API. Use when looking for contact information, people profiles, or decision makers.",
            func=self.search_people_exa
        )
        
        self.add_external_tool(
            name="search_people_nav_hdw",
            description="Search for people using HDW's expensive search_nav_search_users endpoint. WARNING: Expensive endpoint, use sparingly with caching.",
            func=self.search_people_nav_hdw
        )
    
    def setup_web_scraping_tools(self) -> None:
        """Setup web scraping tools (Firecrawl)."""
        self.add_external_tool(
            name="scrape_website_firecrawl",
            description="Scrape website content using Firecrawl API. Use when analyzing company websites, extracting business information, or understanding company offerings.",
            func=self.scrape_website_firecrawl
        )
    
    def _create_adk_agent(self) -> None:
        """Create or recreate the Google ADK Agent with current tools."""
        # Extract just the function objects from FunctionTool wrappers
        tool_functions = []
        for tool in self.tools:
            if hasattr(tool, 'func'):
                tool_functions.append(tool.func)
        
        # Create agent with simplified configuration
        try:
            self.adk_agent = Agent(
                model=self.config.gemini.model,
                name=self.agent_name,
                instruction=self.agent_description,
                tools=tool_functions
            )
            self.runner = Runner(
                agent=self.adk_agent,
                app_name="icp_agent_system",
                session_service=self.session_service
            )
            self.logger.info("Google ADK agent created successfully", tool_count=len(tool_functions))
        except Exception as e:
            self.logger.error("Error creating Google ADK agent", error=str(e))
            # Fallback: create agent without tools
            self.adk_agent = Agent(
                model=self.config.gemini.model,
                name=self.agent_name,
                instruction=self.agent_description,
                tools=[]
            )
            self.runner = Runner(
                agent=self.adk_agent,
                app_name="icp_agent_system",
                session_service=self.session_service
            )
    
    # Utility methods
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        return self.active_conversations.get(conversation_id)
    
    def add_message_to_conversation(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        agent_action: Optional[str] = None
    ) -> None:
        """Add a message to a conversation."""
        conversation = self.get_conversation(conversation_id)
        if conversation:
            conversation.add_message(
                role=role,
                content=content,
                agent_name=self.agent_name,
                agent_action=agent_action
            )
    
    # Abstract methods for subclasses
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of agent capabilities."""
        pass
    
    @abstractmethod
    async def execute_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a specific task."""
        pass
    
    @abstractmethod
    async def process_query(
        self,
        query: str,
        context: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> str:
        """Process a query and return a response."""
        pass