#!/bin/bash
# Script to check existing Vertex AI resources

PROJECT_ID="bayram-adk-hack"
LOCATION="us-central1"

echo "Checking Vertex AI resources for project: $PROJECT_ID"
echo "==========================================="

# Check for RAG corpora
echo -e "\n1. RAG Corpora:"
gcloud ai rag-corpora list --project=$PROJECT_ID --location=$LOCATION 2>/dev/null || echo "No RAG corpora found or API not enabled"

# Check for Reasoning Engines
echo -e "\n2. Reasoning Engines:"
gcloud ai reasoning-engines list --project=$PROJECT_ID --location=$LOCATION 2>/dev/null || echo "No reasoning engines found or API not enabled"

# Check for deployed models
echo -e "\n3. Deployed Models:"
gcloud ai models list --project=$PROJECT_ID --region=$LOCATION 2>/dev/null || echo "No models found"

echo -e "\nIf you see 'API not enabled' errors, you may need to enable the Vertex AI API."