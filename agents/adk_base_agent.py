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
from google.adk.tools import FunctionTool, load_memory
from google.adk.sessions import InMemorySessionService
from google.genai import types

import structlog
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from models import Conversation, ConversationMessage, MessageRole
from utils.config import Config
from utils.cache import CacheManager
from utils.logging_config import get_logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.vertex_memory_service import VertexMemoryManager


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
        tools: Optional[List[Any]] = None,
        memory_manager: Optional['VertexMemoryManager'] = None
    ):
        # Store configuration
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.agent_id = str(uuid.uuid4())
        self.config = config
        self.cache_manager = cache_manager or CacheManager(config.cache)
        self.memory_manager = memory_manager
        
        # Set up logging
        self.logger = get_logger(f"agents.{agent_name}")
        
        # Agent state
        self.active_conversations = {}
        
        # External API clients (to be initialized by subclasses)
        self.external_clients = {}
        
        # Tool list for Google ADK
        self.tools = tools or []
        
        # Session service for Google ADK
        # Will be set based on memory_manager availability
        self.session_service = None
        self.memory_service = None
        self._init_session_services()
        
        # Initialize the Google ADK Agent
        self.adk_agent = None
        self.runner = None
        
        # Memory-aware instruction
        self.memory_aware_instruction = self._create_memory_aware_instruction()
        
        self.logger.info(f"ADK Agent initialized - Model: {config.gemini.model}, Memory enabled: {bool(memory_manager)}")
    
    def _get_app_name(self) -> str:
        """Get the appropriate app name for VertexAI services.
        
        Returns reasoning engine app name if available, otherwise default.
        """
        if self.memory_manager and hasattr(self.memory_manager.config, 'reasoning_engine_app_name'):
            return self.memory_manager.config.reasoning_engine_app_name or "icp_agent_system"
        return "icp_agent_system"
    
    def _init_session_services(self):
        """Initialize session and memory services based on configuration."""
        if self.memory_manager:
            # Services will be initialized lazily by memory manager
            self.session_service = None  # Will be set from memory manager
            self.memory_service = None   # Will be set from memory manager
            self.logger.info("Using VertexAI services (lazy initialization)")
        else:
            # Fallback to in-memory services
            from google.adk.memory import InMemoryMemoryService
            self.session_service = InMemorySessionService()
            self.memory_service = InMemoryMemoryService()
            self.logger.info("Using in-memory services")
    
    def _create_memory_aware_instruction(self) -> str:
        """Create memory-aware agent instruction."""
        base_instruction = self.agent_description
        
        if self.memory_manager:
            memory_context = f"""
{base_instruction}

You have access to persistent memory through the load_memory tool. 

IMPORTANT: When users ask about:
- Previous ICPs, prospects, or companies analyzed
- Past conversations or sessions
- "What we did before" or "last time"
- Any reference to previous interactions

You MUST use the load_memory tool to search for relevant past conversations.

The load_memory tool allows you to:
- Search for specific topics from past conversations
- Retrieve ICPs, prospects, and analysis from previous sessions
- Continue where you left off
- Provide context-aware responses based on history

Always check memory first when the user references past work or asks about previous sessions."""
            return memory_context
        else:
            return base_instruction
    
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
        
        # Don't recreate agent immediately - defer until first use
        if hasattr(self, '_adk_agent_initialized'):
            self._adk_agent_initialized = False
        
        self.logger.info(f"Added external tool: {name}")
    
    async def _ensure_runner_initialized(self):
        """Ensure the runner is initialized with the appropriate session and memory services."""
        if self.memory_manager and getattr(self, '_runner_needs_init', False):
            # Get both session and memory services from memory manager
            session_service = await self.memory_manager.session_service
            memory_service = await self.memory_manager.memory_service
            self.runner = Runner(
                agent=self.adk_agent,
                app_name=self._get_app_name(),
                session_service=session_service,
                memory_service=memory_service
            )
            self._runner_needs_init = False
            self.logger.info("Runner initialized with VertexAI session and memory services")
    
    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process a message using Google ADK."""
        
        # Ensure ADK agent is created or recreated if tools changed
        if not self.adk_agent or not getattr(self, '_adk_agent_initialized', False):
            self._create_adk_agent()
            self._adk_agent_initialized = True
        
        # Ensure runner is initialized
        await self._ensure_runner_initialized()
        
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
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
            conversation = Conversation(
                id=conversation_id,
                user_id="default"
            )
            self.active_conversations[conversation_id] = conversation
        
        # Add user message to conversation
        conversation.add_message(MessageRole.USER, message)
        
        # Create or get session
        user_id = conversation.user_id
        
        # Get appropriate session service
        if self.memory_manager:
            session_service = await self.memory_manager.session_service
        else:
            session_service = self.session_service
            
        # Determine app name based on service type
        if hasattr(session_service, '__class__') and 'VertexAi' in session_service.__class__.__name__:
            # For VertexAI, use reasoning engine app name if available
            app_name = self._get_app_name()
                
            # Let VertexAI auto-generate the session ID
            session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id
            )
            # Store mapping of conversation_id to session_id for later reference
            conversation.metadata["vertex_session_id"] = session.id
        else:
            # For other services, we can provide our own session_id
            session = await session_service.create_session(
                app_name=self._get_app_name(),
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
            
            # Add session to memory after successful processing
            await self._add_session_to_memory(session.id, user_id)
            
            return response_text
            
        except Exception as e:
            self.logger.error(f"Error processing message - Error: {str(e)}")
            raise
    
    async def process_message_stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Process a message using Google ADK with streaming responses.
        
        Yields streaming response parts from the agent including progress updates.
        """
        
        # Ensure ADK agent is created or recreated if tools changed
        if not self.adk_agent or not getattr(self, '_adk_agent_initialized', False):
            self._create_adk_agent()
            self._adk_agent_initialized = True
        
        # Ensure runner is initialized
        await self._ensure_runner_initialized()
        
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
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
            conversation = Conversation(
                id=conversation_id,
                user_id="default"
            )
            self.active_conversations[conversation_id] = conversation
        
        # Add user message to conversation
        conversation.add_message(MessageRole.USER, message)
        
        # Create or get session
        user_id = conversation.user_id
        
        # Get appropriate session service
        if self.memory_manager:
            session_service = await self.memory_manager.session_service
        else:
            session_service = self.session_service
            
        # Determine app name based on service type
        if hasattr(session_service, '__class__') and 'VertexAi' in session_service.__class__.__name__:
            # For VertexAI, use reasoning engine app name if available
            app_name = self._get_app_name()
                
            # Let VertexAI auto-generate the session ID
            session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id
            )
            # Store mapping of conversation_id to session_id for later reference
            conversation.metadata["vertex_session_id"] = session.id
        else:
            # For other services, we can provide our own session_id
            session = await session_service.create_session(
                app_name=self._get_app_name(),
                user_id=user_id,
                session_id=conversation_id
            )
        
        try:
            # Create content for Google ADK
            content = types.Content(
                role='user',
                parts=[types.Part(text=message)]
            )
            
            # Yield initial thinking message
            yield f"🤖 {self.agent_name} is processing your request...\n\n"
            
            # Run the agent with streaming
            full_response = ""
            events_async = self.runner.run_async(
                session_id=session.id,
                user_id=user_id,
                new_message=content
            )
            
            async for event in events_async:
                if event.content and event.content.parts:
                    if text := ''.join(part.text or '' for part in event.content.parts):
                        full_response += text
                        yield text
            
            # Add complete response to conversation history
            conversation.add_message(
                MessageRole.ASSISTANT,
                full_response,
                agent_name=self.agent_name
            )
            
            # Add session to memory after successful processing
            await self._add_session_to_memory(session.id, user_id)
            
        except Exception as e:
            self.logger.error(f"Error processing message stream - Error: {str(e)}")
            yield f"\n\n❌ Error: {str(e)}"
    
    def _format_conversation_history(self, conversation: Conversation) -> str:
        """Format conversation history for the model."""
        history_lines = []
        for msg in conversation.messages[-10:]:  # Last 10 messages
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            history_lines.append(f"{role}: {msg.content}")
        
        return "\n".join(history_lines) if history_lines else ""
    
    async def process_message_with_memory(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process a message with memory context enhancement.
        
        This method:
        1. Retrieves relevant memories from previous conversations
        2. Enhances the message with memory context
        3. Processes the enhanced message
        4. Ingests the interaction into memory
        
        Args:
            message: User message
            conversation_id: Conversation identifier
            context: Optional context dictionary
            
        Returns:
            Agent response
        """
        if not self.memory_manager:
            # Fallback to regular processing if no memory manager
            return await self.process_message(message, conversation_id, context)
        
        # Extract user_id from context or use default
        user_id = context.get("user_id", "default") if context else "default"
        
        try:
            # Query relevant memories
            memories = await self.memory_manager.query_memory(
                app_name=self._get_app_name(),
                user_id=user_id,
                query=message,
                top_k=self.config.vertexai.similarity_top_k if hasattr(self.config, 'vertexai') else 5
            )
            
            # Format memories for context
            memory_context = self.memory_manager.format_memories_for_context(memories)
            
            # Enhance message with memory context
            enhanced_message = message
            if memories:
                enhanced_message = f"{memory_context}\n\nCurrent query: {message}"
                self.logger.info(f"Enhanced message with memory context - Memory_Count: {len(memories)}")
            
            # Process the enhanced message
            response = await self.process_message(
                enhanced_message,
                conversation_id,
                context
            )
            
            # Ingest the interaction into memory
            await self.memory_manager.ingest_memory(
                app_name=self._get_app_name(),
                user_id=user_id,
                session_id=conversation_id or f"session_{int(datetime.now().timestamp())}",
                messages=[
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response}
                ],
                metadata={
                    "agent": self.agent_name,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in memory-enhanced processing - Error: {str(e)}")
            # Fallback to regular processing
            return await self.process_message(message, conversation_id, context)
    
    async def _add_session_to_memory(self, session_id: str, user_id: str) -> None:
        """Add a completed session to memory service.
        
        This is called after processing messages to persist the session.
        
        Args:
            session_id: The session ID to persist
            user_id: The user ID associated with the session
        """
        try:
            # Get appropriate services
            if self.memory_manager:
                session_service = await self.memory_manager.session_service
                memory_service = await self.memory_manager.memory_service
            else:
                session_service = self.session_service
                memory_service = self.memory_service
                
            if not memory_service:
                return
                
            # Get the session
            session = await session_service.get_session(
                app_name=self._get_app_name(),
                user_id=user_id,
                session_id=session_id
            )
            
            if session and hasattr(memory_service, 'add_session_to_memory'):
                # Add the session to memory
                await memory_service.add_session_to_memory(session)
                self.logger.debug(f"Session added to memory - Session_Id: {session_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to add session to memory: {e}")
    
    async def load_memory(
        self,
        query: str,
        user_id: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Load relevant memories from previous conversations.
        
        This tool allows agents to query past conversations and retrieve relevant context.
        
        Args:
            query: Search query to find relevant memories
            user_id: Optional user ID to filter memories (defaults to current user)
            top_k: Number of memories to retrieve
            
        Returns:
            Dictionary with status and retrieved memories
        """
        try:
            # Use memory manager if available
            if self.memory_manager:
                user_id = user_id or "default"
                memories = await self.memory_manager.query_memory(
                    app_name=self._get_app_name(),
                    user_id=user_id,
                    query=query,
                    top_k=top_k
                )
                
                # Format memories for response
                memory_context = self.memory_manager.format_memories_for_context(memories)
                
                return {
                    "status": "success",
                    "memories_found": len(memories),
                    "context": memory_context
                }
            else:
                return {
                    "status": "no_memory_service",
                    "memories_found": 0,
                    "context": "Memory service is not available."
                }
                
        except Exception as e:
            self.logger.error(f"Error loading memory - Error: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e),
                "memories_found": 0,
                "context": "Failed to retrieve memories."
            }
    
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
                timeout=30  # Reduced from 300
            )
            
            # Convert dataclass objects to dictionaries for caching
            companies_dict = []
            for company in companies:
                if hasattr(company, '__dict__'):
                    companies_dict.append(company.__dict__)
                elif hasattr(company, 'model_dump'):
                    companies_dict.append(company.model_dump())
                else:
                    # Fallback - convert to dict manually
                    companies_dict.append({
                        'name': getattr(company, 'name', ''),
                        'alias': getattr(company, 'alias', ''),
                        'urn': str(getattr(company, 'urn', ''))
                    })
            
            # Cache the result
            self.cache_manager.set(cache_key, companies_dict)
            
            self.logger.info(f"Companies found via HDW - Count: {len(companies)}")
            return {"status": "success", "companies": companies}
            
        except Exception as e:
            self.logger.error(f"Error searching companies with HDW - Error: {str(e)}")
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
                timeout=30  # Reduced from 300
            )
            
            # Convert to standard format
            people = []
            for user in users:
                # Extract first and last name from full name
                name_parts = user.name.split() if user.name else ["Unknown"]
                first_name = name_parts[0] if name_parts else "Unknown"
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                
                # Get current position and company from current_companies
                current_title = user.current_companies[0].position if user.current_companies else user.headline
                current_company = user.current_companies[0].company.name if user.current_companies and hasattr(user.current_companies[0].company, 'name') else "Unknown"
                
                people.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "name": user.name,
                    "title": current_title,
                    "company": current_company,
                    "linkedin_url": user.url,
                    "location": user.location.name if hasattr(user.location, 'name') else str(user.location),
                    "source": "hdw"
                })
            
            # Cache the result
            self.cache_manager.set(cache_key, people)
            
            self.logger.info(f"People found via HDW - Count: {len(people)}")
            return {"status": "success", "people": people}
            
        except Exception as e:
            self.logger.error(f"Error searching people with HDW - Error: {str(e)}")
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
                self.logger.warning(f"Exa API not configured - Error: {str(e)}")
                return {"status": "error", "error_message": "Exa API key not configured"}
            
            # Cache the result
            self.cache_manager.set(cache_key, people)
            
            self.logger.info(f"People found via Exa - Count: {len(people)}")
            return {"status": "success", "people": people}
            
        except Exception as e:
            self.logger.error(f"Error searching people with Exa - Error: {str(e)}")
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
            scrape_result = await firecrawl_client.scrape_url(
                url=url,
                include_links=include_links,
                include_metadata=True,
                format_type="markdown"
            )
            
            # The scrape_result is already a processed dictionary with "content" key
            content = scrape_result.get("content", "")
            metadata = scrape_result.get("metadata", {})
            
            # Cache the content string
            self.cache_manager.set(cache_key, content)
            
            self.logger.info(f"Website scraped via Firecrawl - Url: {url}")
            return {"status": "success", "content": content, "metadata": metadata}
            
        except Exception as e:
            self.logger.error(f"Error scraping website with Firecrawl - Error: {str(e)}")
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
                timeout=30  # Reduced from 300
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
            self.logger.error(f"Error searching industries with HDW - Error: {str(e)}")
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
                timeout=30  # Reduced from 300
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
            self.logger.error(f"Error with HDW nav search - Error: {str(e)}")
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
                timeout=30  # Reduced from 300
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
            self.logger.error(f"Error searching locations with HDW - Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    def setup_external_tools(self) -> None:
        """Setup external API tools. Override in subclasses to add specific tools."""
        # Base implementation sets up memory tools if available
        if self.memory_manager or self.memory_service:
            self.setup_memory_tools()
        # Subclasses should call specific tool setup methods as needed
        pass
    
    def setup_memory_tools(self) -> None:
        """Setup memory tools for accessing past conversations."""
        # Use ADK's built-in load_memory tool directly
        if self.memory_manager or self.memory_service:
            self.tools.append(load_memory)
            self.logger.info("Added ADK load_memory tool for past conversation access")
    
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
        
        # Check if we need to recreate the agent (only if tools changed)
        if hasattr(self, '_last_tool_count') and self._last_tool_count == len(tool_functions):
            self.logger.debug("Tools unchanged, skipping agent recreation")
            return
        
        # Create agent with simplified configuration
        try:
            self.adk_agent = Agent(
                model=self.config.gemini.model,
                name=self.agent_name,
                instruction=self.memory_aware_instruction,
                tools=tool_functions
            )
            # Get session service for runner
            if self.memory_manager:
                # For async session service, we'll create runner after initialization
                self.runner = None
                self._runner_needs_init = True
            else:
                self.runner = Runner(
                    agent=self.adk_agent,
                    app_name=self._get_app_name(),
                    session_service=self.session_service,
                    memory_service=self.memory_service
                )
            self._last_tool_count = len(tool_functions)
            self.logger.info(f"Google ADK agent created successfully - Tool_Count: {len(tool_functions)}")
        except Exception as e:
            self.logger.error(f"Error creating Google ADK agent - Error: {str(e)}")
            # Fallback: create agent without tools
            self.adk_agent = Agent(
                model=self.config.gemini.model,
                name=self.agent_name,
                instruction=self.memory_aware_instruction,
                tools=[]
            )
            # Get session service for runner
            if self.memory_manager:
                # For async session service, we'll create runner after initialization
                self.runner = None
                self._runner_needs_init = True
            else:
                self.runner = Runner(
                    agent=self.adk_agent,
                    app_name=self._get_app_name(),
                    session_service=self.session_service,
                    memory_service=self.memory_service
                )
            self._last_tool_count = 0
    
    @asynccontextmanager
    async def json_generation_mode(self):
        """Context manager to temporarily disable tools for JSON generation.
        
        This prevents infinite recursion when a tool function needs the agent
        to generate JSON output. The agent might otherwise call the tool
        recursively instead of returning JSON.
        
        Usage:
            async with self.json_generation_mode():
                response = await self.process_message(prompt)
        """
        # Save current tools
        saved_tools = self.tools
        saved_adk_agent = self.adk_agent
        saved_runner = self.runner
        
        try:
            # Temporarily clear tools
            self.tools = []
            
            # Create a tool-less agent for JSON generation
            self.logger.debug("Entering JSON generation mode - tools disabled")
            self._create_adk_agent()
            
            yield
            
        finally:
            # Restore original tools and agent
            self.tools = saved_tools
            self.adk_agent = saved_adk_agent
            self.runner = saved_runner
            self.logger.debug("Exited JSON generation mode - tools restored")
    
    async def process_json_request(self, prompt: str) -> str:
        """Process a request that expects JSON output without tool calls.
        
        This method ensures the agent generates pure JSON without attempting
        to call any tools, preventing infinite recursion issues.
        
        Args:
            prompt: The prompt requesting JSON generation
            
        Returns:
            The JSON response as a string
        """
        # Create a separate agent without tools for JSON generation
        json_agent = Agent(
            model=self.config.gemini.model,
            name=self.agent_name,
            instruction=self.agent_description,
            tools=[]  # No tools to prevent function calling
        )
        # Get session and memory services
        if self.memory_manager:
            session_service = await self.memory_manager.session_service
            memory_service = await self.memory_manager.memory_service
        else:
            session_service = self.session_service
            memory_service = self.memory_service
        
        json_runner = Runner(
            agent=json_agent,
            app_name=self._get_app_name(),
            session_service=session_service,
            memory_service=memory_service
        )
        
        # Process message with the tool-less agent
        session_id = f"json_gen_{uuid.uuid4().hex[:12]}"
        
        # Check if this is VertexAI session service
        if hasattr(session_service, '__class__') and 'VertexAi' in session_service.__class__.__name__:
            # For VertexAI, use reasoning engine app name if available
            app_name = self._get_app_name()
                
            # Let VertexAI auto-generate the session ID
            session = await session_service.create_session(
                app_name=app_name,
                user_id="system"
            )
        else:
            session = await session_service.create_session(
                app_name=self._get_app_name(),
                user_id="system",
                session_id=session_id
            )
        
        content = types.Content(
            role='user',
            parts=[types.Part(text=prompt)]
        )
        
        response_text = ""
        events_async = json_runner.run_async(
            session_id=session.id,
            user_id="system",
            new_message=content
        )
        
        async for event in events_async:
            if event.content and event.content.parts:
                if text := ''.join(part.text or '' for part in event.content.parts):
                    response_text += text
        
        # Clean up markdown formatting if present
        if response_text.strip().startswith("```json"):
            response_text = response_text.strip()[7:-3].strip()
        elif response_text.strip().startswith("```"):
            response_text = response_text.strip()[3:-3].strip()
        
        return response_text
    
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
    
    # A2A Protocol Support
    
    def get_openapi_spec(self) -> Dict[str, Any]:
        """Generate OpenAPI specification for agent capabilities.
        
        Returns:
            OpenAPI 3.0 specification as a dictionary
        """
        from protocols.a2a_protocol import Capability
        
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": f"{self.agent_name} API",
                "description": self.agent_description,
                "version": "1.0.0"
            },
            "servers": [
                {
                    "url": f"/agents/{self.agent_name}",
                    "description": f"{self.agent_name} endpoint"
                }
            ],
            "paths": {}
        }
        
        # Generate paths for each capability
        for capability_name in self.get_capabilities():
            path = f"/capabilities/{capability_name}"
            
            # Get tool metadata if available
            tool_metadata = getattr(self, 'tool_metadata', {}).get(capability_name, {})
            
            spec["paths"][path] = {
                "post": {
                    "summary": capability_name,
                    "description": tool_metadata.get('description', f"Execute {capability_name}"),
                    "operationId": capability_name,
                    "tags": [self.agent_name],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": self._get_capability_schema(capability_name)
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "result": {"type": "object"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Bad request"
                        },
                        "500": {
                            "description": "Internal server error"
                        }
                    }
                }
            }
        
        return spec
    
    def _get_capability_schema(self, capability_name: str) -> Dict[str, Any]:
        """Get parameter schema for a capability.
        
        Args:
            capability_name: Name of the capability
            
        Returns:
            Schema properties dictionary
        """
        schema_props = {}
        
        # Try to find the tool function and extract parameters
        for tool in self.tools:
            if hasattr(tool, 'func') and tool.func.__name__ == capability_name:
                import inspect
                sig = inspect.signature(tool.func)
                
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    
                    # Basic type mapping
                    param_schema = {"type": "string"}  # Default
                    
                    if param.annotation != inspect.Parameter.empty:
                        annotation_str = str(param.annotation)
                        if 'int' in annotation_str:
                            param_schema = {"type": "integer"}
                        elif 'float' in annotation_str:
                            param_schema = {"type": "number"}
                        elif 'bool' in annotation_str:
                            param_schema = {"type": "boolean"}
                        elif 'List' in annotation_str:
                            param_schema = {"type": "array", "items": {"type": "string"}}
                        elif 'Dict' in annotation_str:
                            param_schema = {"type": "object"}
                    
                    schema_props[param_name] = param_schema
                
                break
        
        return schema_props
    
    async def handle_a2a_request(
        self,
        capability_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle an A2A protocol request.
        
        Args:
            capability_name: Name of the capability to invoke
            parameters: Parameters for the capability
            context: Optional execution context
            
        Returns:
            Result dictionary with status and data
        """
        try:
            # Validate capability exists
            if capability_name not in self.get_capabilities():
                return {
                    "status": "error",
                    "error": f"Capability '{capability_name}' not found"
                }
            
            # Find and execute the tool function
            for tool in self.tools:
                if hasattr(tool, 'func') and tool.func.__name__ == capability_name:
                    # Execute the function
                    result = await tool.func(**parameters)
                    
                    return {
                        "status": "success",
                        "result": result
                    }
            
            # If we get here, the capability wasn't found in tools
            return {
                "status": "error",
                "error": f"Tool function for '{capability_name}' not found"
            }
            
        except Exception as e:
            self.logger.error(f"Error handling A2A request - Capability: {capability_name}, Error: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
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