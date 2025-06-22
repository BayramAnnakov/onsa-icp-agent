#!/usr/bin/env python3
"""Deploy ADK agents as a Reasoning Engine in Vertex AI."""

import os
from google.cloud import aiplatform
from google.cloud.aiplatform import reasoning_engines

# Configuration
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT', 'bayram-adk-hack')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
STAGING_BUCKET = f"gs://{PROJECT_ID}-reasoning-engines"

def create_reasoning_engine():
    """Create and deploy a reasoning engine."""
    
    # Initialize Vertex AI
    aiplatform.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
    
    print(f"Deploying Reasoning Engine to project: {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print("=" * 50)
    
    # Define the agent application
    class ADKAgentApp:
        """Wrapper for ADK multi-agent system."""
        
        def __init__(self, project: str, location: str):
            self.project = project
            self.location = location
            
        def query(self, input_text: str) -> str:
            """Process a query through the agent system."""
            # This is a simplified example - in production, you would:
            # 1. Import your actual agent orchestrator
            # 2. Process the query through your agents
            # 3. Return the response
            
            # For now, return a placeholder
            return f"Processed query: {input_text}"
    
    # Create the reasoning engine
    reasoning_engine = reasoning_engines.ReasoningEngine.create(
        display_name="adk-multi-agent-system",
        description="Production ADK multi-agent system for sales lead generation",
        reasoning_engine=ADKAgentApp(PROJECT_ID, LOCATION),
        requirements=[
            "google-cloud-aiplatform>=1.98.0",
            "google-adk[vertexai]>=0.5.0",
            "pydantic>=2.0.0",
            "structlog>=24.0.0",
            # Add your other requirements here
        ],
    )
    
    print(f"\n✅ Reasoning Engine deployed successfully!")
    print(f"Engine ID: {reasoning_engine.resource_name.split('/')[-1]}")
    print(f"Full resource name: {reasoning_engine.resource_name}")
    print(f"\nSet this environment variable:")
    print(f"export REASONING_ENGINE_ID=\"{reasoning_engine.resource_name.split('/')[-1]}\"")
    print(f"export REASONING_ENGINE_APP_NAME=\"{reasoning_engine.resource_name}\"")
    
    return reasoning_engine

def create_staging_bucket():
    """Create staging bucket if it doesn't exist."""
    from google.cloud import storage
    
    client = storage.Client(project=PROJECT_ID)
    bucket_name = f"{PROJECT_ID}-reasoning-engines"
    
    try:
        bucket = client.create_bucket(bucket_name, location=LOCATION)
        print(f"Created staging bucket: {bucket_name}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"Staging bucket already exists: {bucket_name}")
        else:
            raise

if __name__ == "__main__":
    # Create staging bucket first
    create_staging_bucket()
    
    # Deploy the reasoning engine
    create_reasoning_engine()