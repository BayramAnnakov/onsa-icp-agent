#!/usr/bin/env python3
"""Start the A2A Protocol Server with all ADK agents registered.

This script initializes all agents and registers them with the A2A server.
"""

import asyncio
import os
from pathlib import Path

# Setup Python path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from a2a_server import app, run_server
from services.agent_registry import get_agent_registry
from utils.config import Config
from utils.logging_config import setup_logging, get_logger

# Import agents
from agents.adk_icp_agent import ADKICPAgent
from agents.adk_research_agent import ADKResearchAgent
from agents.adk_prospect_agent import ADKProspectAgent

# Setup logging
setup_logging(
    log_file="logs/a2a_server.log",
    console_level="INFO",
    file_level="DEBUG"
)
logger = get_logger(__name__)


async def initialize_agents():
    """Initialize and register all agents."""
    logger.info("Initializing ADK agents for A2A server")
    
    # Load configuration
    config = Config.load_from_file()
    config.ensure_directories()
    
    # Initialize memory manager if enabled
    memory_manager = None
    if config.vertexai.enabled:
        try:
            from services.vertex_memory_service import VertexMemoryManager
            memory_manager = VertexMemoryManager(config.vertexai)
            logger.info("VertexAI memory manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize VertexAI memory: {str(e)}")
    
    # Initialize agents
    agents = []
    
    try:
        # ICP Agent
        icp_agent = ADKICPAgent(config, memory_manager=memory_manager)
        agents.append(icp_agent)
        logger.info("ICP Agent initialized")
        
        # Research Agent
        research_agent = ADKResearchAgent(config, memory_manager=memory_manager)
        agents.append(research_agent)
        logger.info("Research Agent initialized")
        
        # Prospect Agent
        prospect_agent = ADKProspectAgent(config, memory_manager=memory_manager)
        agents.append(prospect_agent)
        logger.info("Prospect Agent initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize agents: {str(e)}")
        raise
    
    # Register agents with A2A registry
    registry = get_agent_registry()
    
    for agent in agents:
        # Create A2A info for each agent
        a2a_info = agent._create_a2a_info()
        registry.register_agent(a2a_info, agent)
        logger.info(f"Registered {agent.agent_name} with A2A server")
    
    # Log summary
    stats = registry.get_registry_stats()
    logger.info(f"A2A Server initialized with {stats['total_agents']} agents")
    
    # Log available capabilities
    all_capabilities = set()
    for agent in agents:
        capabilities = agent.get_capabilities()
        all_capabilities.update(capabilities)
    
    logger.info(f"Total capabilities available: {len(all_capabilities)}")
    for cap in sorted(all_capabilities):
        logger.info(f"  - {cap}")


def main():
    """Main entry point."""
    print("🚀 Starting A2A Protocol Server for ADK Multi-Agent System")
    print("=" * 60)
    
    # Check environment
    required_env_vars = ["GOOGLE_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {missing_vars}")
        print("   Some agent capabilities may be limited")
    
    # Initialize agents
    try:
        asyncio.run(initialize_agents())
    except Exception as e:
        print(f"❌ Failed to initialize agents: {str(e)}")
        return
    
    # Get server configuration
    host = os.environ.get("A2A_HOST", "0.0.0.0")
    port = int(os.environ.get("A2A_PORT", 8080))
    
    print(f"\n✅ A2A Server ready!")
    print(f"🌐 Server starting at http://{host}:{port}")
    print("\n📍 Available endpoints:")
    print(f"   - Discovery: http://{host}:{port}/a2a/discovery")
    print(f"   - Capabilities: http://{host}:{port}/a2a/capabilities")
    print(f"   - Execute Task: http://{host}:{port}/a2a/task")
    print(f"   - Health: http://{host}:{port}/health")
    print(f"   - Metrics: http://{host}:{port}/metrics")
    print(f"   - WebSocket: ws://{host}:{port}/a2a/ws/{{client_id}}")
    print(f"   - API Docs: http://{host}:{port}/docs")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Run server
    try:
        run_server(host=host, port=port)
    except KeyboardInterrupt:
        print("\n👋 Shutting down A2A server")
    except Exception as e:
        print(f"\n❌ Server error: {str(e)}")


if __name__ == "__main__":
    main()