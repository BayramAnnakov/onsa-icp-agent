"""Test script for VertexAI memory functionality."""

import asyncio
import os
from datetime import datetime
from utils.config import Config
from services.vertex_memory_service import VertexMemoryManager
import structlog

# Setup logging
logger = structlog.get_logger()


async def test_memory_service():
    """Test basic memory service functionality."""
    
    print("🧪 Testing VertexAI Memory Service")
    print("=" * 50)
    
    # Load configuration
    config = Config.load_from_file()
    
    # Check if VertexAI is enabled
    if not config.vertexai.enabled:
        print("❌ VertexAI is not enabled. Set VERTEX_AI_ENABLED=true")
        return
    
    print(f"✅ VertexAI enabled for project: {config.vertexai.project_id}")
    
    try:
        # Initialize memory manager
        print("\n1️⃣ Initializing VertexAI Memory Manager...")
        memory_manager = VertexMemoryManager(config.vertexai)
        
        # Test session creation
        print("\n2️⃣ Testing session creation...")
        session = await memory_manager.create_session(
            app_name="test_app",
            user_id="test_user",
            session_id=f"test_session_{int(datetime.now().timestamp())}",
            initial_state={"test": "data"}
        )
        print(f"✅ Session created: {session.id}")
        
        # Test memory ingestion
        print("\n3️⃣ Testing memory ingestion...")
        test_messages = [
            {"role": "user", "content": "I need an ICP for B2B SaaS companies"},
            {"role": "assistant", "content": "I'll help you create an ICP for B2B SaaS companies targeting enterprise clients."}
        ]
        
        await memory_manager.ingest_memory(
            app_name="test_app",
            user_id="test_user",
            session_id=session.id,
            messages=test_messages,
            metadata={"test_run": True}
        )
        print("✅ Memory ingested successfully")
        
        # Test memory query
        print("\n4️⃣ Testing memory retrieval...")
        memories = await memory_manager.query_memory(
            app_name="test_app",
            user_id="test_user",
            query="B2B SaaS ICP",
            top_k=5
        )
        print(f"✅ Retrieved {len(memories)} memories")
        
        if memories:
            print("\n📝 Memory content preview:")
            formatted = memory_manager.format_memories_for_context(memories)
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
        
        # Test session retrieval
        print("\n5️⃣ Testing session retrieval...")
        retrieved_session = await memory_manager.get_session(
            app_name="test_app",
            session_id=session.id
        )
        if retrieved_session:
            print(f"✅ Session retrieved: {retrieved_session.id}")
            print(f"   State: {retrieved_session.state}")
        
        # Test health check
        print("\n6️⃣ Testing health check...")
        health = await memory_manager.health_check()
        print("✅ Health check results:")
        for key, value in health.items():
            print(f"   {key}: {value}")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        logger.exception("Test error")


async def test_memory_in_conversation():
    """Test memory in a simulated conversation."""
    
    print("\n\n🗣️ Testing Memory in Conversation")
    print("=" * 50)
    
    config = Config.load_from_file()
    
    if not config.vertexai.enabled:
        print("❌ VertexAI is not enabled")
        return
    
    try:
        # Initialize components
        from adk_main import ADKAgentOrchestrator
        from services.vertex_memory_service import VertexMemoryManager
        
        memory_manager = VertexMemoryManager(config.vertexai)
        orchestrator = ADKAgentOrchestrator(config, memory_manager=memory_manager)
        
        # Simulate first conversation
        print("\n📱 First Conversation:")
        conv_id_1 = await orchestrator.start_conversation("test_user")
        
        # Create an ICP
        response1 = await orchestrator.icp_agent.process_message_with_memory(
            "Create an ICP for B2B SaaS companies targeting HR departments",
            conversation_id=conv_id_1,
            context={"user_id": "test_user"}
        )
        print(f"Agent: {response1[:200]}...")
        
        # Wait a moment for memory ingestion
        await asyncio.sleep(2)
        
        # Start new conversation
        print("\n\n📱 Second Conversation (testing memory recall):")
        conv_id_2 = await orchestrator.start_conversation("test_user")
        
        # Ask about previous ICP
        response2 = await orchestrator.icp_agent.process_message_with_memory(
            "What ICPs have we created before?",
            conversation_id=conv_id_2,
            context={"user_id": "test_user"}
        )
        print(f"Agent: {response2[:300]}...")
        
        if "B2B SaaS" in response2 or "HR" in response2:
            print("\n✅ Memory recall successful! Agent remembered previous ICP.")
        else:
            print("\n⚠️ Memory recall may not be working as expected.")
        
    except Exception as e:
        print(f"\n❌ Conversation test failed: {str(e)}")
        logger.exception("Conversation test error")


async def main():
    """Run all tests."""
    
    # Ensure VertexAI is enabled
    os.environ["VERTEX_AI_ENABLED"] = "true"
    
    # Run basic tests
    await test_memory_service()
    
    # Run conversation tests
    await test_memory_in_conversation()
    
    print("\n\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())