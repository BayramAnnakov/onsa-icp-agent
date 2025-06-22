"""Mock memory service for local testing without VertexAI."""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import structlog
from pathlib import Path

from google.adk.sessions import InMemorySessionService, Session, BaseSessionService
from google.adk.memory import InMemoryMemoryService, BaseMemoryService
from google.adk.memory.memory_entry import MemoryEntry
from utils.config import VertexAIConfig


class PersistentInMemoryMemoryService(BaseMemoryService):
    """A memory service that persists to disk for testing."""
    
    def __init__(self, storage_file: Path):
        super().__init__()
        self.storage_file = storage_file
        self.memories_data = {}
        self._load_data()
    
    def _load_data(self):
        """Load existing data from storage."""
        if self.storage_file.exists():
            with open(self.storage_file, 'r') as f:
                self.memories_data = json.load(f)
    
    def _save_data(self):
        """Save data to storage."""
        with open(self.storage_file, 'w') as f:
            json.dump(self.memories_data, f, indent=2)
    
    async def add_session_to_memory(self, session: Session) -> None:
        """Add a session to memory storage."""
        key = f"{session.app_name}:{session.user_id}"
        if key not in self.memories_data:
            self.memories_data[key] = []
        
        # Convert session state to memory entry
        session_entry = {
            "session_id": session.id,
            "app_name": session.app_name,
            "user_id": session.user_id,
            "state": session.state,
            "timestamp": datetime.now().isoformat()
        }
        
        self.memories_data[key].append(session_entry)
        self._save_data()
    
    async def search_memory(self, *, app_name: str, user_id: str, query: str):
        """Search for sessions that match the query."""
        # Import the response type
        from google.adk.memory.base_memory_service import SearchMemoryResponse
        
        key = f"{app_name}:{user_id}"
        user_memories = self.memories_data.get(key, [])
        
        # Simple relevance scoring
        relevant_memories = []
        query_lower = query.lower()
        
        for memory in user_memories:
            score = 0
            # Check state content for relevance
            state_str = str(memory.get("state", "")).lower()
            if any(term in state_str for term in query_lower.split()):
                score += 1
            
            if score > 0:
                # Create memory entry
                memory_content = f"Session {memory['session_id']}: {state_str}"
                entry = MemoryEntry(
                    content=memory_content,
                    metadata={"session_id": memory["session_id"], "timestamp": memory["timestamp"]}
                )
                relevant_memories.append((score, entry))
        
        # Sort by score and return top results
        relevant_memories.sort(key=lambda x: x[0], reverse=True)
        memories = [mem[1] for mem in relevant_memories[:5]]
        
        return SearchMemoryResponse(memories=memories)
    
    async def query_memories(self, query: str, user_id: str, app_name: str, top_k: int = 5) -> List[MemoryEntry]:
        """Query memories for a user.""" 
        result = await self.search_memory(app_name=app_name, user_id=user_id, query=query)
        return result.memories[:top_k]


class MockVertexMemoryManager(BaseSessionService, BaseMemoryService):
    """Mock VertexAI memory manager for local testing.
    
    This simulates VertexAI behavior using local file storage.
    """
    
    def __init__(self, config: VertexAIConfig):
        """Initialize mock memory manager."""
        # Initialize parent classes
        BaseSessionService.__init__(self)
        BaseMemoryService.__init__(self)
        
        self.config = config
        self.logger = structlog.get_logger().bind(component="mock_vertex_memory")
        
        # Local storage paths
        self.storage_dir = Path("./mock_vertex_storage")
        self.memories_dir = self.storage_dir / "memories"
        self.sessions_dir = self.storage_dir / "sessions"
        
        # Create directories
        self.memories_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory services as base
        self._memory_service = PersistentInMemoryMemoryService(self.memories_dir / "memory_service.json")
        self._session_service = InMemorySessionService()
        
        # Local storage for persistence simulation
        self._memories_file = self.memories_dir / "memories.json"
        self._sessions_file = self.sessions_dir / "sessions.json"
        
        # Load existing data
        self._load_data()
        
        self.logger.info("Mock VertexAI memory manager initialized")
    
    # Session service interface methods
    async def create_session(self, app_name: str, user_id: str, session_id: str) -> Session:
        """Create a new session."""
        session = Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state={}
        )
        
        # Store in sessions data
        session_key = f"{app_name}:{user_id}:{session_id}"
        self._sessions_data[session_key] = {
            "session_id": session_id,
            "app_name": app_name,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "state": {}
        }
        self._save_sessions()
        
        self.logger.debug(f"Created mock session - Session_Id: {session_id}")
        return session
    
    async def get_session(self, app_name: str, user_id: str, session_id: str) -> Optional[Session]:
        """Get an existing session."""
        session_key = f"{app_name}:{user_id}:{session_id}"
        session_data = self._sessions_data.get(session_key)
        
        if session_data:
            return Session(
                id=session_id,
                app_name=app_name,
                user_id=user_id,
                state=session_data.get("state", {})
            )
        return None
    
    async def delete_session(self, app_name: str, user_id: str, session_id: str) -> bool:
        """Delete a session."""
        session_key = f"{app_name}:{user_id}:{session_id}"
        if session_key in self._sessions_data:
            del self._sessions_data[session_key]
            self._save_sessions()
            self.logger.debug(f"Deleted mock session - Session_Id: {session_id}")
            return True
        return False
    
    async def search_memory(self, app_name: str, user_id: str, query: str, **kwargs):
        """Search memory (required by BaseMemoryService)."""
        memories = await self.query_memory(app_name, user_id, query, kwargs.get('top_k', 5))
        
        # Return in the format expected by ADK
        class SearchResult:
            def __init__(self, memories):
                self.memories = memories
        
        return SearchResult(memories)
    
    async def add_session_to_memory(self, session: Session) -> None:
        """Add a session to memory storage (mock implementation)."""
        self.logger.debug(f"Adding session to memory (mock) - Session_Id: {session.id}")
        # Extract conversation from session state if available
        # For mock, we'll just log this action
        pass
    
    def _load_data(self):
        """Load existing data from local storage."""
        # Load memories
        if self._memories_file.exists():
            with open(self._memories_file, 'r') as f:
                self._memories_data = json.load(f)
        else:
            self._memories_data = {}
        
        # Load sessions
        if self._sessions_file.exists():
            with open(self._sessions_file, 'r') as f:
                self._sessions_data = json.load(f)
        else:
            self._sessions_data = {}
    
    def _save_memories(self):
        """Save memories to local storage."""
        with open(self._memories_file, 'w') as f:
            json.dump(self._memories_data, f, indent=2)
    
    def _save_sessions(self):
        """Save sessions to local storage."""
        with open(self._sessions_file, 'w') as f:
            json.dump(self._sessions_data, f, indent=2)
    
    @property
    async def memory_service(self):
        """Get the memory service."""
        return self._memory_service
    
    @property
    async def session_service(self):
        """Get the session service."""
        return self._session_service
    
    async def ingest_memory(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        messages: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Ingest conversation messages into memory."""
        self.logger.info(f"Ingesting memory (mock) - User_Id: {user_id}, Session_Id: {session_id}")
        
        # Create memory key
        memory_key = f"{app_name}:{user_id}:{session_id}:{datetime.now().isoformat()}"
        
        # Store memory
        memory_entry = {
            "app_name": app_name,
            "user_id": user_id,
            "session_id": session_id,
            "messages": messages,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to user's memories
        user_key = f"{app_name}:{user_id}"
        if user_key not in self._memories_data:
            self._memories_data[user_key] = []
        
        self._memories_data[user_key].append(memory_entry)
        
        # Save to disk
        self._save_memories()
        
        # Also use in-memory service
        await self._memory_service.ingest_memory(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            messages=messages
        )
    
    async def query_memory(
        self,
        app_name: str,
        user_id: str,
        query: str,
        top_k: Optional[int] = None
    ) -> List[Any]:
        """Query relevant memories for a user."""
        self.logger.info(f"Querying memory (mock) - User_Id: {user_id}, Query: {query[:50]}")
        
        # Get user's memories
        user_key = f"{app_name}:{user_id}"
        user_memories = self._memories_data.get(user_key, [])
        
        # Simple relevance scoring (mock)
        relevant_memories = []
        query_lower = query.lower()
        
        for memory in user_memories:
            # Check if query terms appear in messages
            relevance_score = 0
            for msg in memory["messages"]:
                content_lower = msg.get("content", "").lower()
                if any(term in content_lower for term in query_lower.split()):
                    relevance_score += 1
            
            if relevance_score > 0:
                # Create mock Memory object
                memory_text = "\n".join([
                    f"{msg['role']}: {msg['content']}" 
                    for msg in memory["messages"]
                ])
                
                # Create a simple Memory-like object
                class MockMemory:
                    def __init__(self, content, metadata):
                        self.content = content
                        self.metadata = metadata
                
                relevant_memories.append((
                    relevance_score,
                    MockMemory(memory_text, memory["metadata"])
                ))
        
        # Sort by relevance and return top_k
        relevant_memories.sort(key=lambda x: x[0], reverse=True)
        top_k = top_k or self.config.similarity_top_k
        
        return [mem[1] for mem in relevant_memories[:top_k]]
    
    async def create_session(
        self,
        app_name: str,
        user_id: str,
        session_id: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None
    ) -> Session:
        """Create a new session."""
        session_id = session_id or f"session_{int(datetime.now().timestamp())}"
        
        # Create session in in-memory service
        session = await self._session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=state or {}
        )
        
        # Store in local storage
        session_key = f"{app_name}:{session_id}"
        self._sessions_data[session_key] = {
            "app_name": app_name,
            "user_id": user_id,
            "session_id": session_id,
            "state": state or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._save_sessions()
        
        return session
    
    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[Any] = None
    ) -> Optional[Session]:
        """Retrieve a session by ID."""
        # Try in-memory first
        session = await self._session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            config=config
        )
        
        if session:
            return session
        
        # Check local storage
        session_key = f"{app_name}:{session_id}"
        if session_key in self._sessions_data:
            # Recreate session in in-memory service
            data = self._sessions_data[session_key]
            return await self._session_service.create_session(
                app_name=app_name,
                user_id=data["user_id"],
                session_id=session_id,
                state=data["state"]
            )
        
        return None
    
    async def update_session(
        self,
        app_name: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """Update session state."""
        await self._session_service.update_session(
            app_name=app_name,
            session_id=session_id,
            state=state
        )
        
        # Update local storage
        session_key = f"{app_name}:{session_id}"
        if session_key in self._sessions_data:
            self._sessions_data[session_key]["state"] = state
            self._sessions_data[session_key]["updated_at"] = datetime.now().isoformat()
            self._save_sessions()
    
    async def list_sessions(
        self,
        app_name: str,
        user_id: str,
        limit: int = 100
    ) -> List[Session]:
        """List all sessions for a user."""
        sessions = await self._session_service.list_sessions(
            app_name=app_name,
            user_id=user_id,
            limit=limit
        )
        
        # Also check local storage for persisted sessions
        for key, data in self._sessions_data.items():
            if data["app_name"] == app_name and data["user_id"] == user_id:
                # Ensure it's in in-memory service
                session_exists = any(s.id == data["session_id"] for s in sessions)
                if not session_exists:
                    session = await self.create_session(
                        app_name=app_name,
                        user_id=user_id,
                        session_id=data["session_id"],
                        state=data["state"]
                    )
                    sessions.append(session)
        
        return sessions[:limit]
    
    def format_memories_for_context(self, memories: List[Any]) -> str:
        """Format retrieved memories for LLM context."""
        if not memories:
            return "No relevant previous context found."
        
        context_parts = ["Relevant context from previous conversations:"]
        
        for i, memory in enumerate(memories, 1):
            content = memory.content if hasattr(memory, 'content') else str(memory)
            context_parts.append(f"\n[Memory {i}]")
            context_parts.append(content)
        
        return "\n".join(context_parts)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of mock services."""
        return {
            "enabled": True,
            "initialized": True,
            "memory_service": "healthy",
            "session_service": "healthy",
            "type": "mock",
            "storage_dir": str(self.storage_dir),
            "memories_count": sum(len(mems) for mems in self._memories_data.values()),
            "sessions_count": len(self._sessions_data)
        }