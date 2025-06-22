#!/usr/bin/env python3
"""Create a RAG corpus for ADK agent memory storage."""

import os
from google.cloud import aiplatform

# Configuration
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT', 'bayram-adk-hack')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
CORPUS_NAME = "adk-agent-memory"
CORPUS_DESCRIPTION = "Memory storage for ADK multi-agent system"

def create_rag_corpus():
    """Create a new RAG corpus."""
    try:
        # Initialize Vertex AI
        aiplatform.init(project=PROJECT_ID, location=LOCATION)
        
        # Import the correct client
        try:
            from google.cloud.aiplatform import rag
            print("Using google.cloud.aiplatform.rag module")
        except ImportError:
            print("❌ RAG module not found. You may need to update google-cloud-aiplatform:")
            print("pip install --upgrade google-cloud-aiplatform")
            return None
        
        print(f"Creating RAG corpus '{CORPUS_NAME}'...")
        
        # Create corpus using the rag module
        corpus = rag.create_corpus(
            display_name=CORPUS_NAME,
            description=CORPUS_DESCRIPTION,
            project=PROJECT_ID,
            location=LOCATION
        )
        
        # Extract corpus ID from the resource name
        # Format: projects/{project}/locations/{location}/ragCorpora/{corpus_id}
        corpus_id = corpus.name.split('/')[-1]
        
        print(f"\n✅ RAG Corpus created successfully!")
        print(f"Corpus ID: {corpus_id}")
        print(f"Full name: {corpus.name}")
        print(f"\nSet this environment variable:")
        print(f"export VERTEX_AI_RAG_CORPUS_ID=\"{corpus_id}\"")
        
        return corpus_id
        
    except Exception as e:
        print(f"❌ Error creating RAG corpus: {e}")
        print("\nMake sure you have:")
        print("1. Enabled Vertex AI API")
        print("2. Proper permissions (roles/aiplatform.user)")
        print("3. Run: gcloud auth application-default login")
        return None

if __name__ == "__main__":
    create_rag_corpus()