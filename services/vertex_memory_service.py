"""VertexAI Memory Service implementation for ADK agents.

This module provides persistent memory and session management using Google Cloud's
Vertex AI RAG service and Cloud Storage.
"""

import os
import asyncio
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import structlog
import json

from google.cloud import aiplatform
from google.cloud import storage
    
try:
    from google.adk.sessions import VertexAiSessionService
    VERTEX_SESSIONS_AVAILABLE = True
except ImportError:
    VERTEX_SESSIONS_AVAILABLE = False
    
try:
    from google.adk.memory import VertexAiRagMemoryService
    VERTEX_RAG_AVAILABLE = True
except ImportError:
    VERTEX_RAG_AVAILABLE = False
    
from google.adk.sessions import InMemorySessionService, Session
from google.adk.memory import InMemoryMemoryService, BaseMemoryService

try:
    from google.adk.sessions import DatabaseSessionService
    DATABASE_SESSIONS_AVAILABLE = True
except ImportError:
    DATABASE_SESSIONS_AVAILABLE = False
from utils.logging_config import get_logger

from utils.config import VertexAIConfig


class SimpleMemoryService(BaseMemoryService):
    """Simple in-memory implementation of memory service that follows ADK patterns."""
    
    def __init__(self):
        super().__init__()
        self.memories = {}
        self.logger = get_logger(__name__)
    
    async def add_session_to_memory(self, session: Session) -> None:
        """Add a completed session to memory following ADK pattern."""
        key = f"{session.app_name}:{session.user_id}"
        if key not in self.memories:
            self.memories[key] = []
        
        # Extract messages from session state
        messages = []
        if hasattr(session, 'state') and session.state:
            # Try to extract conversation history from session state
            for event in session.state.get('events', []):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if part.text:
                            role = 'user' if event.content.role == 'user' else 'assistant'
                            messages.append({
                                "role": role,
                                "content": part.text,
                                "timestamp": datetime.now().isoformat()
                            })
        
        if messages:
            self.memories[key].append({
                "session_id": session.id,
                "messages": messages,
                "timestamp": datetime.now().isoformat()
            })
    
    async def search_memory(self, app_name: str, user_id: str, query: str, top_k: int = 5):
        """Search memory following ADK pattern."""
        return await self.query_memory(app_name, user_id, query, top_k)
    
    async def ingest_memory(self, app_name: str, user_id: str, session_id: str, messages: list):
        """Legacy method for backward compatibility."""
        key = f"{app_name}:{user_id}"
        if key not in self.memories:
            self.memories[key] = []
        self.memories[key].append({
            "session_id": session_id,
            "messages": messages,
            "timestamp": datetime.now().isoformat()
        })
    
    async def query_memory(self, app_name: str, user_id: str, query: str, top_k: int = 5):
        """Query memory with simple relevance scoring."""
        key = f"{app_name}:{user_id}"
        user_memories = self.memories.get(key, [])
        
        # Simple relevance scoring
        results = []
        for memory in user_memories:
            score = 0
            for msg in memory["messages"]:
                if query.lower() in msg.get("content", "").lower():
                    score += 1
            if score > 0:
                results.append((score, memory))
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in results[:top_k]]


class Memory:
    """Simple memory object."""
    def __init__(self, content, metadata=None):
        self.content = content
        self.metadata = metadata or {}


class VertexMemoryManager:
    """Manages VertexAI memory and session services for the ADK agent system.
    
    This class provides:
    - Persistent memory storage using Vertex AI RAG
    - Session management using Google Cloud Storage
    - Graceful fallback to in-memory services
    - Cloud Run optimized initialization
    """
    
    def __init__(self, config: VertexAIConfig):
        """Initialize the VertexAI memory manager.
        
        Args:
            config: VertexAI configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize services
        self._initialized = False
        self._rag_corpus = None
        self._memory_service = None
        self._session_service = None
        
        # Check configuration priority:
        # 1. Database services (if enabled and available)
        # 2. Mock memory (for testing)
        # 3. VertexAI (if enabled)
        # 4. In-memory services (fallback)
        
        if config.use_database and DATABASE_SESSIONS_AVAILABLE:
            self.logger.info(f"Using database services with URL: {config.database_url}")
            self._use_database_services()
        elif os.getenv("USE_MOCK_MEMORY", "false").lower() == "true":
            # Use mock memory for local testing
            self.logger.info("Using mock memory service for local testing")
            self._use_mock_memory_services()
        elif config.enabled:
            # Lazy initialization for Cloud Run
            self.logger.info("VertexAI enabled, will initialize on first use")
        else:
            self.logger.info("Using in-memory services (no persistence)")
            self._use_in_memory_services()
    
    def _use_in_memory_services(self):
        """Configure in-memory fallback services using ADK's built-in services."""
        # Use ADK's InMemoryMemoryService when available, fallback to our custom implementation
        try:
            self._memory_service = InMemoryMemoryService()
        except Exception:
            # Fallback to our custom implementation if ADK service fails
            self._memory_service = SimpleMemoryService()
        
        self._session_service = InMemorySessionService()
        self._initialized = True
    
    def _use_database_services(self):
        """Configure database-backed services for persistent local storage."""
        try:
            # Ensure data directory exists
            db_path = self.config.database_url.replace('sqlite:///', '')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Initialize database session service
            self._session_service = DatabaseSessionService(db_url=self.config.database_url)
            
            # For memory service, we can use our SimpleMemoryService with the database session service
            # Or use InMemoryMemoryService as it will persist through the database sessions
            try:
                self._memory_service = InMemoryMemoryService()
            except Exception:
                self._memory_service = SimpleMemoryService()
            
            self._initialized = True
            self.logger.info(f"Database services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database services: {e}")
            self.logger.warning("Falling back to in-memory services")
            self._use_in_memory_services()
    
    def _use_mock_memory_services(self):
        """Configure mock memory services for local testing."""
        from .mock_memory_service import MockVertexMemoryManager
        mock_manager = MockVertexMemoryManager(self.config)
        self._memory_service = mock_manager
        self._session_service = mock_manager
        self._initialized = True
    
    async def _initialize_vertex_services(self):
        """Initialize VertexAI services (lazy loading for Cloud Run)."""
        if self._initialized:
            return
        
        try:
            # Check if required modules are available
            if not VERTEX_RAG_AVAILABLE or not VERTEX_SESSIONS_AVAILABLE:
                self.logger.warning(
                    f"VertexAI RAG or Sessions not available - RAG: {VERTEX_RAG_AVAILABLE}, Sessions: {VERTEX_SESSIONS_AVAILABLE}, Python: 3.13.1"
                )
                self.logger.info("Using mock memory service instead")
                self._use_mock_memory_services()
                return
            
            self.logger.info(f"Initializing VertexAI services - Project: {self.config.project_id}, Location: {self.config.location}")
            
            # Initialize Vertex AI
            if self.config.use_default_credentials:
                # Use Application Default Credentials (ideal for Cloud Run)
                aiplatform.init(
                    project=self.config.project_id,
                    location=self.config.location
                )
            else:
                # Use explicit credentials if provided
                aiplatform.init(
                    project=self.config.project_id,
                    location=self.config.location,
                    credentials=self._load_credentials()
                )
            
            # Initialize RAG corpus resource name
            if self.config.rag_corpus_id:
                rag_corpus_name = f"projects/{self.config.project_id}/locations/{self.config.location}/ragCorpora/{self.config.rag_corpus_id}"
            else:
                # For now, require explicit corpus ID
                self.logger.error("RAG corpus ID not configured. Please set rag_corpus_id in config.")
                self._use_mock_memory_services()
                return
            
            # Check if reasoning engine is configured
            if not self.config.reasoning_engine_app_name and not self.config.reasoning_engine_id:
                self.logger.warning("No reasoning engine configured - VertexAI requires a reasoning engine")
                self.logger.warning("Set REASONING_ENGINE_ID or REASONING_ENGINE_APP_NAME environment variable")
                raise ValueError("Reasoning engine not configured for VertexAI")
            
            # Initialize memory service following the example pattern
            self._memory_service = VertexAiRagMemoryService(
                rag_corpus=rag_corpus_name,
                similarity_top_k=self.config.similarity_top_k,
                vector_distance_threshold=0.7  # Add this parameter from example
            )
            
            # Initialize session service with project and location
            self._session_service = VertexAiSessionService(
                project=self.config.project_id,
                location=self.config.location
            )
            
            self._initialized = True
            self.logger.info("VertexAI services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize VertexAI services - Error: {str(e)}")
            self.logger.warning("Falling back to mock memory services")
            self._use_mock_memory_services()
    
    async def _initialize_rag_corpus(self):
        """Initialize or retrieve existing RAG corpus."""
        try:
            if self.config.rag_corpus_id:
                # Use existing corpus
                corpus_name = f"projects/{self.config.project_id}/locations/{self.config.location}/ragCorpora/{self.config.rag_corpus_id}"
                self.logger.info(f"Using existing RAG corpus - Corpus_Id: {self.config.rag_corpus_id}")
                return rag.RagCorpus(corpus_name=corpus_name)
            else:
                # List existing corpora to check if one with our name exists
                corpora = rag.list_corpora()
                for corpus in corpora:
                    if corpus.display_name == self.config.rag_corpus_name:
                        self.logger.info(f"Found existing RAG corpus - Name: {corpus.display_name}")
                        return corpus
                
                # Create new corpus
                self.logger.info(f"Creating new RAG corpus - Name: {self.config.rag_corpus_name}")
                return rag.create_corpus(
                    display_name=self.config.rag_corpus_name,
                    description=self.config.rag_corpus_description
                )
        except Exception as e:
            self.logger.error(f"Failed to initialize RAG corpus - Error: {str(e)}")
            raise
    
    def _load_credentials(self):
        """Load credentials from file or environment."""
        # This method is for future use if explicit credentials are needed
        # For now, we rely on Application Default Credentials
        return None
    
    @property
    async def memory_service(self):
        """Get the memory service (lazy initialization)."""
        if not self._initialized:
            await self._initialize_vertex_services()
        return self._memory_service
    
    @property
    async def session_service(self):
        """Get the session service (lazy initialization)."""
        if not self._initialized:
            await self._initialize_vertex_services()
        return self._session_service
    
    async def ingest_memory(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        messages: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Ingest conversation messages into memory.
        
        Args:
            app_name: Application name
            user_id: User identifier
            session_id: Session identifier
            messages: List of message dictionaries with 'role' and 'content'
            metadata: Optional metadata to attach
        """
        try:
            service = await self.memory_service
            
            # Check if service has the required method
            if not hasattr(service, 'ingest_memory'):
                # InMemoryMemoryService from Google ADK doesn't support ingest_memory - this is expected
                if type(service).__name__ == 'InMemoryMemoryService':
                    self.logger.debug(f"Memory service is InMemoryMemoryService - ingest_memory not available (expected)")
                else:
                    self.logger.warning(f"Memory service does not support ingest_memory - Service type: {type(service).__name__}")
                return
            
            # Format messages for ingestion
            memory_content = self._format_messages_for_memory(messages, metadata)
            
            await service.ingest_memory(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                messages=memory_content
            )
            
            self.logger.info(f"Memory ingested successfully - User_Id: {user_id}, Session_Id: {session_id}, Message_Count: {len(messages)}")
        except Exception as e:
            self.logger.error(f"Failed to ingest memory - Error: {str(e)}")
            # Don't raise - allow system to continue without memory
    
    async def query_memory(
        self,
        app_name: str,
        user_id: str,
        query: str,
        top_k: Optional[int] = None
    ) -> List[Memory]:
        """Query relevant memories for a user.
        
        Args:
            app_name: Application name
            user_id: User identifier
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of relevant memories
        """
        try:
            service = await self.memory_service
            
            # Check if service has the required method
            if not hasattr(service, 'query_memory'):
                self.logger.warning(f"Memory service does not support query_memory - Service type: {type(service).__name__}")
                return []
            
            memories = await service.query_memory(
                app_name=app_name,
                user_id=user_id,
                query=query,
                top_k=top_k or self.config.similarity_top_k
            )
            
            self.logger.info(f"Memory query successful - User_Id: {user_id}, Query: {query[:50]}, Result_Count: {len(memories)}")
            
            return memories
        except Exception as e:
            self.logger.error(f"Failed to query memory - Error: {str(e)}")
            return []
    
    async def create_session(
        self,
        app_name: str,
        user_id: str,
        session_id: Optional[str] = None,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> Session:
        """Create a new session.
        
        Args:
            app_name: Application name
            user_id: User identifier
            session_id: Optional session ID (generated if not provided)
            initial_state: Initial session state
            
        Returns:
            Created session
        """
        try:
            service = await self.session_service
            
            # VertexAI doesn't support user-provided session IDs
            # Let it auto-generate the session ID
            if isinstance(service, VertexAiSessionService):
                session = await service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    state=initial_state or {}
                )
            else:
                # For other services (like InMemorySessionService), we can provide session_id
                session = await service.create_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    state=initial_state or {}
                )
            
            self.logger.info(f"Session created - User_Id: {user_id}, Session_Id: {session.id}")
            
            return session
        except Exception as e:
            self.logger.error(f"Failed to create session - Error: {str(e)}")
            raise
    
    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[Any] = None
    ) -> Optional[Session]:
        """Retrieve a session by ID.
        
        Args:
            app_name: Application name
            user_id: User identifier
            session_id: Session identifier
            config: Optional configuration
            
        Returns:
            Session if found, None otherwise
        """
        try:
            service = await self.session_service
            
            session = await service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                config=config
            )
            
            if session:
                self.logger.debug(f"Session retrieved - Session_Id: {session_id}")
            
            return session
        except Exception as e:
            self.logger.error(f"Failed to get session - Error: {str(e)}")
            return None
    
    async def update_session(
        self,
        app_name: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """Update session state.
        
        Args:
            app_name: Application name
            session_id: Session identifier
            state: New session state
        """
        try:
            service = await self.session_service
            
            await service.update_session(
                app_name=app_name,
                session_id=session_id,
                state=state
            )
            
            self.logger.debug(f"Session updated - Session_Id: {session_id}")
        except Exception as e:
            self.logger.error(f"Failed to update session - Error: {str(e)}")
            # Don't raise - allow system to continue
    
    async def list_user_sessions(
        self,
        app_name: str,
        user_id: str,
        limit: int = 100
    ) -> List[Session]:
        """List all sessions for a user.
        
        Args:
            app_name: Application name
            user_id: User identifier
            limit: Maximum number of sessions to return
            
        Returns:
            List of user sessions
        """
        try:
            service = await self.session_service
            
            sessions = await service.list_sessions(
                app_name=app_name,
                user_id=user_id,
                limit=limit
            )
            
            self.logger.info(f"Listed user sessions - User_Id: {user_id}, Session_Count: {len(sessions)}")
            
            return sessions
        except Exception as e:
            self.logger.error(f"Failed to list sessions - Error: {str(e)}")
            return []
    
    def _format_messages_for_memory(
        self,
        messages: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Format messages for memory ingestion.
        
        Args:
            messages: Raw messages
            metadata: Optional metadata
            
        Returns:
            Formatted messages for ingestion
        """
        formatted_messages = []
        
        for msg in messages:
            formatted_msg = {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": datetime.now().isoformat()
            }
            
            # Add metadata if provided
            if metadata:
                formatted_msg["metadata"] = metadata
            
            formatted_messages.append(formatted_msg)
        
        return formatted_messages
    
    def format_memories_for_context(self, memories: List[Memory]) -> str:
        """Format retrieved memories for LLM context.
        
        Args:
            memories: List of retrieved memories
            
        Returns:
            Formatted string for LLM context
        """
        if not memories:
            return "No relevant previous context found."
        
        context_parts = ["Relevant context from previous conversations:"]
        
        for i, memory in enumerate(memories, 1):
            # Extract content and metadata
            content = memory.content if hasattr(memory, 'content') else str(memory)
            
            # Format each memory
            context_parts.append(f"\n[Memory {i}]")
            context_parts.append(content)
        
        return "\n".join(context_parts)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of VertexAI services.
        
        Returns:
            Health status dictionary
        """
        health = {
            "enabled": self.config.enabled,
            "initialized": self._initialized,
            "memory_service": "unknown",
            "session_service": "unknown",
            "rag_corpus": "unknown"
        }
        
        if self._initialized:
            # Check memory service
            try:
                service = await self.memory_service
                health["memory_service"] = "healthy" if service else "unhealthy"
            except:
                health["memory_service"] = "error"
            
            # Check session service
            try:
                service = await self.session_service
                health["session_service"] = "healthy" if service else "unhealthy"
            except:
                health["session_service"] = "error"
            
            # Check RAG corpus
            health["rag_corpus"] = "configured" if self._rag_corpus else "not_configured"
        
        return health