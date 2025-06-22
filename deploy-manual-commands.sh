#!/bin/bash

# Manual Cloud Run deployment commands
# Run these commands one by one after Docker is running

# 1. Set variables
export PROJECT_ID="bayram-adk-hack"
export SERVICE_NAME="onsa-icp-agent"
export REGION="us-central1"
export IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# 2. Configure gcloud
gcloud config set project $PROJECT_ID

# 3. Build the Docker image
docker build -t $IMAGE_NAME .

# 4. Push to Container Registry
docker push $IMAGE_NAME

# 5. Deploy to Cloud Run
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
    --set-env-vars="PORT=8080,DEPLOYMENT_MODE=cloud_run" \
    --port 8080

# 6. Get the service URL
gcloud run services describe $SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --format 'value(status.url)'

# 7. Set up secrets (run these after deployment)
# For GOOGLE_API_KEY
echo -n "YOUR_GOOGLE_API_KEY_HERE" | gcloud secrets create google-api-key --data-file=-
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-secrets="GOOGLE_API_KEY=google-api-key:latest"

# For HDW_API_TOKEN
echo -n "YOUR_HDW_API_TOKEN_HERE" | gcloud secrets create hdw-api-token --data-file=-
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --update-secrets="HDW_API_TOKEN=hdw-api-token:latest"

# For EXA_API_KEY
echo -n "YOUR_EXA_API_KEY_HERE" | gcloud secrets create exa-api-key --data-file=-
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --update-secrets="EXA_API_KEY=exa-api-key:latest"

# For FIRECRAWL_API_KEY
echo -n "YOUR_FIRECRAWL_API_KEY_HERE" | gcloud secrets create firecrawl-api-key --data-file=-
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --update-secrets="FIRECRAWL_API_KEY=firecrawl-api-key:latest"