#!/bin/bash

# Setup script for local VertexAI testing

echo "🚀 Setting up local VertexAI testing environment"
echo "=============================================="

# Set environment variables
export GOOGLE_CLOUD_PROJECT="bayram-adk-hack"
export GOOGLE_CLOUD_LOCATION="us-central1"
export VERTEX_AI_ENABLED="true"

# Authenticate with gcloud
echo "1️⃣ Authenticating with Google Cloud..."
gcloud auth application-default login

# Set the project
echo "2️⃣ Setting default project..."
gcloud config set project $GOOGLE_CLOUD_PROJECT

# Create storage bucket if needed
BUCKET_NAME="${GOOGLE_CLOUD_PROJECT}-adk-sessions"
echo "3️⃣ Checking storage bucket..."
if ! gsutil ls -b gs://$BUCKET_NAME >/dev/null 2>&1; then
    echo "Creating storage bucket: $BUCKET_NAME"
    gcloud storage buckets create gs://$BUCKET_NAME \
        --location=$GOOGLE_CLOUD_LOCATION \
        --project=$GOOGLE_CLOUD_PROJECT
else
    echo "✅ Storage bucket exists: $BUCKET_NAME"
fi

# Grant your user account necessary permissions
USER_EMAIL=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
echo "4️⃣ Granting permissions to your account: $USER_EMAIL"

# Storage permissions
gcloud storage buckets add-iam-policy-binding gs://$BUCKET_NAME \
    --member=user:$USER_EMAIL \
    --role=roles/storage.objectUser

# Vertex AI permissions
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member=user:$USER_EMAIL \
    --role=roles/aiplatform.user

echo ""
echo "✅ Setup complete!"
echo ""
echo "To test locally, run:"
echo "  export VERTEX_AI_ENABLED=true"
echo "  python web_interface.py"
echo ""
echo "Or test memory directly:"
echo "  python tests/test_vertex_memory.py"