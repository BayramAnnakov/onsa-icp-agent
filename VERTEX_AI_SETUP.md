# VertexAI Setup Guide

## Required Environment Variables

To use VertexAI memory services, you need to set the following environment variables:

```bash
# Basic GCP Configuration
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"

# Enable VertexAI
export VERTEX_AI_ENABLED="true"

# Reasoning Engine Configuration (REQUIRED for VertexAI)
export REASONING_ENGINE_ID="your-reasoning-engine-id"

# OR provide the full resource name:
export REASONING_ENGINE_APP_NAME="projects/your-project-id/locations/us-central1/reasoningEngines/your-reasoning-engine-id"
```

## Creating a Reasoning Engine

If you don't have a reasoning engine yet, you need to create one in Google Cloud:

1. Go to the Google Cloud Console
2. Navigate to Vertex AI > Reasoning Engine
3. Create a new reasoning engine
4. Note the engine ID from the created resource

## Example Configuration

```bash
# Example with actual values
export GOOGLE_CLOUD_PROJECT="bayram-adk-hack"
export GOOGLE_CLOUD_LOCATION="us-central1" 
export VERTEX_AI_ENABLED="true"
export REASONING_ENGINE_ID="adk-agent-engine"
```

## Fallback Behavior

If VertexAI is not properly configured or the reasoning engine is not available:
- The system will automatically fall back to MockMemoryService
- You'll see a warning in the logs: "Falling back to mock memory services"
- The application will continue to work with in-memory storage

## Verifying Setup

Check the logs for these messages:
- Success: "VertexAI services initialized successfully"
- Fallback: "Falling back to mock memory services"

The app_name error "App name icp_agent_system is not valid" indicates that the reasoning engine is not configured.