#!/bin/bash

# ADK Multi-Agent Sales Lead Generation System - Cloud Run Deployment Script

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"bayram-adk-hack"}
SERVICE_NAME=${SERVICE_NAME:-"adk-sales-system"}
REGION=${REGION:-"us-central1"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying ADK Multi-Agent Sales System to Cloud Run"
echo "================================================="
echo "Project: ${PROJECT_ID}"
echo "Service: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE_NAME}"
echo ""

# Check if required tools are installed
command -v gcloud >/dev/null 2>&1 || { echo "❌ gcloud CLI is required but not installed. Aborting." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }

# Validate environment variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  Warning: GOOGLE_API_KEY not set. Make sure to configure it in Cloud Run."
fi

echo "1️⃣ Configuring gcloud..."
gcloud config set project $PROJECT_ID

echo "2️⃣ Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    aiplatform.googleapis.com

echo "3️⃣ Building Docker image..."
docker build -t $IMAGE_NAME .

echo "4️⃣ Pushing image to Container Registry..."
docker push $IMAGE_NAME

echo "5️⃣ Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 10 \
    --max-instances 5 \
    --set-env-vars="PORT=8080" \
    --port 8080

echo "6️⃣ Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo "================================================="
echo "Service URL: $SERVICE_URL"
echo ""
echo "🔧 Next steps:"
echo "1. Set environment variables (API keys) in Cloud Run console"
echo "2. Configure custom domain if needed"
echo "3. Set up monitoring and alerting"
echo ""
echo "📝 Environment variables to configure:"
echo "   - GOOGLE_API_KEY (required)"
echo "   - HDW_API_TOKEN (optional)"
echo "   - EXA_API_KEY (optional)"
echo "   - FIRECRAWL_API_KEY (optional)"
echo ""
echo "🌐 Access your application at: $SERVICE_URL"