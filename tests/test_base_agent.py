"""Test Base Agent functionality."""

import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from agents.base_agent import BaseAgent, A2AMessage, A2AResponse
from models import Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager, CacheConfig


class TestBaseAgent:
    """Test suite for Base Agent."""
    
    class ConcreteAgent(BaseAgent):
        """Concrete implementation of BaseAgent for testing."""
        
        def get_capabilities(self):
            return ["test_capability_1", "test_capability_2"]
        
        async def process_query(self, query: str, conversation_id: str = None):
            # Simple implementation for testing
            conversation = Conversation(id=conversation_id or "test-conv", user_id="test-user")
            
            # Add user message
            conversation.add_message(MessageRole.USER, query)
            
            # Generate response using Gemini
            response = await self.generate_with_gemini(
                f"Respond to this query: {query}",
                cache_key=f"test_query_{hash(query)}"
            )
            
            # Add assistant response
            conversation.add_message(MessageRole.ASSISTANT, response)
            
            return conversation
        
        async def execute_task(self, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a specific task."""
            return {"status": "completed", "result": f"Task {task_type} executed with data: {task_data}"}
        
        async def receive_data(self, data_type: str, data: Dict[str, Any]) -> bool:
            """Receive and process data from other agents."""
            return True
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config.load_from_file("config.yaml")
    
    @pytest.fixture
    def cache_manager(self):
        """Create test cache manager."""
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        return CacheManager(cache_config)
    
    @pytest.fixture
    def base_agent(self, config, cache_manager):
        """Create concrete base agent for testing."""
        return self.ConcreteAgent(
            agent_name="Test Agent",
            agent_description="Test agent for base functionality",
            config=config,
            cache_manager=cache_manager
        )
    
    def test_agent_initialization(self, base_agent):
        """Test base agent initialization."""
        assert base_agent.agent_name == "Test Agent"
        assert base_agent.agent_description == "Test agent for base functionality"
        assert base_agent.config is not None
        assert base_agent.cache_manager is not None
        assert base_agent.logger is not None
        assert base_agent.app is not None  # FastAPI app for A2A
    
    def test_get_capabilities(self, base_agent):
        """Test capabilities retrieval."""
        capabilities = base_agent.get_capabilities()
        assert isinstance(capabilities, list)
        assert "test_capability_1" in capabilities
        assert "test_capability_2" in capabilities
    
    @pytest.mark.asyncio
    async def test_generate_with_gemini(self, base_agent):
        """Test Gemini LLM integration."""
        prompt = "What is the capital of France?"
        
        with patch('google.generativeai.GenerativeModel') as mock_model_class:
            # Mock the model instance and its generate_content method
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Paris is the capital of France."
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            response = await base_agent.generate_with_gemini(prompt)
            
            assert isinstance(response, str)
            assert response == "Paris is the capital of France."
            mock_model.generate_content.assert_called_once_with(prompt)
    
    @pytest.mark.asyncio
    async def test_generate_with_gemini_caching(self, base_agent):
        """Test Gemini LLM integration with caching."""
        prompt = "What is 2 + 2?"
        cache_key = "math_test"
        
        with patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "2 + 2 = 4"
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            # First call - should hit the model
            response1 = await base_agent.generate_with_gemini(prompt, cache_key=cache_key)
            assert response1 == "2 + 2 = 4"
            assert mock_model.generate_content.call_count == 1
            
            # Second call with same cache key - should hit cache
            response2 = await base_agent.generate_with_gemini(prompt, cache_key=cache_key)
            assert response2 == "2 + 2 = 4"
            # Should still be 1 call to the model (cached)
            assert mock_model.generate_content.call_count == 1
    
    def test_a2a_message_creation(self):
        """Test A2A message structure."""
        message = A2AMessage(
            id="test-msg-001",
            sender_agent="agent-a",
            recipient_agent="agent-b",
            message_type="test_request",
            content={"data": "test_data"}
        )
        
        assert message.id == "test-msg-001"
        assert message.sender_agent == "agent-a"
        assert message.recipient_agent == "agent-b"
        assert message.message_type == "test_request"
        assert message.content["data"] == "test_data"
        assert message.timestamp is not None
        assert message.conversation_id is None
    
    def test_a2a_response_creation(self):
        """Test A2A response structure."""
        response = A2AResponse(
            success=True,
            message="Operation completed successfully",
            data={"result": "test_result"},
            error=None
        )
        
        assert response.success is True
        assert response.message == "Operation completed successfully"
        assert response.data["result"] == "test_result"
        assert response.error is None
        
        # Test error response
        error_response = A2AResponse(
            success=False,
            message="Operation failed",
            data=None,
            error="Invalid input parameters"
        )
        
        assert error_response.success is False
        assert error_response.error == "Invalid input parameters"
    
    @pytest.mark.asyncio
    async def test_handle_a2a_message_success(self, base_agent):
        """Test successful A2A message handling."""
        message = A2AMessage(
            id="test-msg-001",
            sender_agent="test-sender",
            recipient_agent="test-agent",
            message_type="capabilities_request",
            content={}
        )
        
        response = await base_agent.handle_a2a_message(message)
        
        assert isinstance(response, A2AResponse)
        assert response.success is True
        assert "capabilities" in response.data
        assert response.data["capabilities"] == base_agent.get_capabilities()
    
    @pytest.mark.asyncio
    async def test_handle_a2a_message_query(self, base_agent):
        """Test A2A message handling for query processing."""
        message = A2AMessage(
            id="test-msg-002",
            sender_agent="test-sender",
            recipient_agent="test-agent",
            message_type="process_query",
            content={"query": "What is AI?"}
        )
        
        with patch.object(base_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = "AI stands for Artificial Intelligence."
            
            response = await base_agent.handle_a2a_message(message)
            
            assert response.success is True
            assert "conversation" in response.data
            # The conversation should be serializable
            assert isinstance(response.data["conversation"], dict)
    
    @pytest.mark.asyncio
    async def test_handle_a2a_message_unknown_type(self, base_agent):
        """Test A2A message handling for unknown message type."""
        message = A2AMessage(
            id="test-msg-003",
            sender_agent="test-sender",
            recipient_agent="test-agent",
            message_type="unknown_message_type",
            content={"some": "data"}
        )
        
        response = await base_agent.handle_a2a_message(message)
        
        assert response.success is False
        assert "Unknown message type" in response.message
        assert response.error is not None
    
    @pytest.mark.asyncio
    async def test_process_query(self, base_agent):
        """Test query processing functionality."""
        query = "What is machine learning?"
        
        with patch.object(base_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = "Machine learning is a subset of AI that enables systems to learn from data."
            
            conversation = await base_agent.process_query(query)
            
            assert isinstance(conversation, Conversation)
            assert len(conversation.messages) == 2
            assert conversation.messages[0].role == MessageRole.USER
            assert conversation.messages[0].content == query
            assert conversation.messages[1].role == MessageRole.ASSISTANT
            assert "machine learning" in conversation.messages[1].content.lower()
    
    def test_fastapi_app_creation(self, base_agent):
        """Test FastAPI app is created for A2A endpoints."""
        assert base_agent.app is not None
        
        # Check that A2A routes are registered
        routes = [route.path for route in base_agent.app.routes]
        assert "/a2a/message" in routes
        assert "/health" in routes
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, base_agent):
        """Test health check endpoint."""
        from fastapi.testclient import TestClient
        
        client = TestClient(base_agent.app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent_name"] == "Test Agent"
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_a2a_endpoint(self, base_agent):
        """Test A2A message endpoint."""
        from fastapi.testclient import TestClient
        
        client = TestClient(base_agent.app)
        
        message_data = {
            "id": "test-msg-004",
            "sender_agent": "external-agent",
            "recipient_agent": "test-agent",
            "message_type": "capabilities_request",
            "content": {},
            "timestamp": "2024-01-15T10:00:00Z"
        }
        
        response = client.post("/a2a/message", json=message_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "capabilities" in data["data"]
    
    def test_configuration_access(self, base_agent):
        """Test configuration access."""
        assert base_agent.config is not None
        assert hasattr(base_agent.config, 'gemini')
        assert hasattr(base_agent.config, 'a2a')
        assert hasattr(base_agent.config, 'scoring')
    
    def test_cache_manager_integration(self, base_agent):
        """Test cache manager integration."""
        assert base_agent.cache_manager is not None
        
        # Test cache operations
        test_key = "test_cache_key"
        test_value = "test_cache_value"
        
        base_agent.cache_manager.set(test_key, test_value)
        retrieved_value = base_agent.cache_manager.get(test_key)
        
        assert retrieved_value == test_value
    
    def test_logging_functionality(self, base_agent):
        """Test logging functionality."""
        assert base_agent.logger is not None
        
        # Test that we can log without errors
        base_agent.logger.info("Test log message")
        base_agent.logger.warning("Test warning message")
        base_agent.logger.error("Test error message")
    
    @pytest.mark.asyncio
    async def test_gemini_error_handling(self, base_agent):
        """Test Gemini error handling."""
        prompt = "Test prompt"
        
        with patch('google.generativeai.GenerativeModel') as mock_model_class:
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_model_class.return_value = mock_model
            
            with pytest.raises(Exception) as exc_info:
                await base_agent.generate_with_gemini(prompt)
            
            assert "API Error" in str(exc_info.value)
    
    def test_agent_id_generation(self, base_agent):
        """Test that agent has unique ID."""
        assert hasattr(base_agent, 'agent_id')
        assert base_agent.agent_id is not None
        assert len(base_agent.agent_id) > 0
        
        # Create another agent and verify different ID
        config = Config.from_yaml("config.yaml")
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        cache_manager = CacheManager(cache_config)
        
        another_agent = self.ConcreteAgent(
            agent_name="Another Test Agent",
            agent_description="Another test agent",
            config=config,
            cache_manager=cache_manager
        )
        
        assert another_agent.agent_id != base_agent.agent_id


def run_base_agent_tests():
    """Run Base Agent tests."""
    print("🤖 Testing Base Agent")
    print("=" * 50)
    
    try:
        # Test basic initialization
        config = Config.load_from_file("config.yaml")
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        cache_manager = CacheManager(cache_config)
        
        # Create concrete agent for testing
        class TestAgent(BaseAgent):
            def get_capabilities(self):
                return ["test_capability"]
            
            async def process_query(self, query: str, conversation_id: str = None):
                conversation = Conversation(id=conversation_id or "test", user_id="test-user")
                conversation.add_message(MessageRole.USER, query)
                conversation.add_message(MessageRole.ASSISTANT, "Test response")
                return conversation
            
            async def execute_task(self, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
                return {"status": "completed"}
            
            async def receive_data(self, data_type: str, data: Dict[str, Any]) -> bool:
                return True
        
        agent = TestAgent(
            agent_name="Test Agent",
            agent_description="Test agent for base functionality",
            config=config,
            cache_manager=cache_manager
        )
        
        print("✅ Base Agent initialization successful")
        print(f"Agent name: {agent.agent_name}")
        print(f"Agent ID: {agent.agent_id}")
        print(f"FastAPI app created: {agent.app is not None}")
        
        # Test capabilities
        capabilities = agent.get_capabilities()
        print(f"✅ Agent capabilities: {capabilities}")
        
        # Test A2A message structure
        message = A2AMessage(
            id="test-001",
            sender_agent="sender",
            recipient_agent="recipient",
            message_type="test",
            content={"test": "data"}
        )
        print(f"✅ A2A message creation: {message.id}")
        
        # Test A2A response structure
        response = A2AResponse(
            success=True,
            message="Test successful",
            data={"result": "test"}
        )
        print(f"✅ A2A response creation: {response.success}")
        
        # Test configuration access
        assert agent.config is not None
        print("✅ Configuration access working")
        
        # Test cache manager
        assert agent.cache_manager is not None
        agent.cache_manager.set("test_key", "test_value")
        cached_value = agent.cache_manager.get("test_key")
        assert cached_value == "test_value"
        print("✅ Cache manager integration working")
        
        print("\n🎉 Base Agent basic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Base Agent test failed: {e}")
        return False


if __name__ == "__main__":
    run_base_agent_tests()