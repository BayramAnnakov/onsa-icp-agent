#!/bin/bash
# Create a real RAG corpus using gcloud CLI

PROJECT_ID="bayram-adk-hack"
LOCATION="us-central1"
CORPUS_NAME="adk-agent-memory-prod"
CORPUS_DESCRIPTION="Production memory storage for ADK multi-agent system"

echo "Creating RAG Corpus using gcloud..."
echo "==================================="

# Create the RAG corpus
echo "Creating corpus: $CORPUS_NAME"
gcloud ai rag-corpora create \
    --display-name="$CORPUS_NAME" \
    --description="$CORPUS_DESCRIPTION" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" \
    --format="value(name)"

# The command will output the full resource name
# Extract the corpus ID from it
echo ""
echo "✅ RAG Corpus created!"
echo ""
echo "To get your corpus ID, run:"
echo "gcloud ai rag-corpora list --project=$PROJECT_ID --location=$LOCATION"
echo ""
echo "The corpus ID is the number at the end of the resource name."