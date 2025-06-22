#!/usr/bin/env python3
"""Deploy the actual ADK agent system as a Reasoning Engine."""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import aiplatform
from google.cloud.aiplatform import reasoning_engines

# Import your actual agent system
from adk_main import ADKAgentOrchestrator
from utils.config import Config

# Configuration
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT', 'bayram-adk-hack')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
STAGING_BUCKET = f"gs://{PROJECT_ID}-reasoning-engines"

class ProductionADKAgent:
    """Production wrapper for ADK agent system."""
    
    def __init__(self, project: str, location: str, corpus_id: str):
        self.project = project
        self.location = location
        self.corpus_id = corpus_id
        self.config = Config()
        
        # Override config for production
        self.config.vertexai.project_id = project
        self.config.vertexai.location = location
        self.config.vertexai.rag_corpus_id = corpus_id
        self.config.vertexai.enabled = True
        
        # Initialize the orchestrator
        self.orchestrator = ADKAgentOrchestrator(self.config)
        
    def query(self, input_text: str, user_id: str = "default") -> dict:
        """Process a query through the agent system.
        
        Args:
            input_text: The user's query
            user_id: User identifier for session management
            
        Returns:
            Dictionary with response and metadata
        """
        import asyncio
        
        # Run the async orchestrator
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                self.orchestrator.process_user_input(input_text, user_id)
            )
            return {
                "response": result.get("response", ""),
                "status": result.get("status", "success"),
                "metadata": result.get("metadata", {})
            }
        finally:
            loop.close()

def deploy_production_agent(corpus_id: str):
    """Deploy the production agent as a reasoning engine."""
    
    # Initialize Vertex AI
    aiplatform.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
    
    print(f"Deploying Production ADK Agent System")
    print(f"Project: {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"RAG Corpus: {corpus_id}")
    print("=" * 50)
    
    # Read requirements from requirements.txt
    with open("requirements.txt", "r") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    # Create the reasoning engine with your actual agent
    reasoning_engine = reasoning_engines.ReasoningEngine.create(
        display_name="adk-multi-agent-production",
        description="Production ADK multi-agent system for B2B sales lead generation",
        reasoning_engine=ProductionADKAgent(PROJECT_ID, LOCATION, corpus_id),
        requirements=requirements,
        extra_packages=[
            "./agents",  # Include your agent modules
            "./integrations",  # Include integrations
            "./utils",  # Include utilities
            "./models",  # Include models
            "./services",  # Include services
        ],
    )
    
    engine_id = reasoning_engine.resource_name.split('/')[-1]
    
    print(f"\n✅ Production Agent deployed successfully!")
    print(f"Engine ID: {engine_id}")
    print(f"Full resource name: {reasoning_engine.resource_name}")
    print(f"\nUpdate your production environment variables:")
    print(f"export REASONING_ENGINE_ID=\"{engine_id}\"")
    print(f"export REASONING_ENGINE_APP_NAME=\"{reasoning_engine.resource_name}\"")
    print(f"export VERTEX_AI_RAG_CORPUS_ID=\"{corpus_id}\"")
    
    # Test the deployment
    print("\nTesting the deployment...")
    test_response = reasoning_engine.query(
        input="Test query to verify deployment",
        user_id="deployment_test"
    )
    print(f"Test response: {test_response}")
    
    return reasoning_engine

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy ADK agents to production")
    parser.add_argument(
        "--corpus-id", 
        required=True,
        help="RAG Corpus ID from step 1"
    )
    
    args = parser.parse_args()
    
    # Create staging bucket if needed
    from google.cloud import storage
    client = storage.Client(project=PROJECT_ID)
    bucket_name = f"{PROJECT_ID}-reasoning-engines"
    
    try:
        client.create_bucket(bucket_name, location=LOCATION)
        print(f"Created staging bucket: {bucket_name}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"Using existing staging bucket: {bucket_name}")
        else:
            raise
    
    # Deploy the agent
    deploy_production_agent(args.corpus_id)