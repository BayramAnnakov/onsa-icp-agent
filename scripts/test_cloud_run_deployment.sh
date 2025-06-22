#!/bin/bash
# Test Cloud Run deployment

SERVICE_NAME="onsa-icp-agent"
REGION="us-central1"

echo "Testing Cloud Run deployment for $SERVICE_NAME..."
echo "================================================="

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
echo "Service URL: $SERVICE_URL"

# Test health endpoint
echo -e "\n1. Testing health endpoint..."
curl -s "$SERVICE_URL/health" | jq '.'

# Test root redirect
echo -e "\n2. Testing root redirect..."
curl -I -s "$SERVICE_URL/" | grep -E "(Location|HTTP)"

# Check environment variables
echo -e "\n3. Checking deployment configuration..."
gcloud run services describe $SERVICE_NAME --region=$REGION --format=json | jq '.spec.template.spec.containers[0].env[] | select(.name == "DEPLOYMENT_MODE")'

# Check recent logs for errors
echo -e "\n4. Recent error logs..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=ERROR" --limit=10 --format=json | jq -r '.[].textPayload // .[].jsonPayload.message' | head -20

# Check for streaming-related logs
echo -e "\n5. Streaming-related logs..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND (textPayload:streaming OR jsonPayload.message:streaming)" --limit=10 --format=json | jq -r '.[].textPayload // .[].jsonPayload.message' | head -20

echo -e "\nDone!"