# Google Cloud Run Deployment Guide

## ADK Multi-Agent Sales Lead Generation System

This guide covers deploying the ADK-powered sales lead generation system to Google Cloud Run for production use.

## Prerequisites

### 1. Google Cloud Setup
```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
source ~/.bashrc

# Login and set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Required APIs
```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    aiplatform.googleapis.com \
    secretmanager.googleapis.com
```

### 3. Docker Installation
- Install Docker Desktop or Docker Engine
- Ensure Docker is running and authenticated with gcloud

## Environment Variables

### Required
- `GOOGLE_API_KEY`: Google Gemini API key for ADK agents

### Optional (for enhanced functionality)
- `HDW_API_TOKEN`: HorizonDataWave API token for LinkedIn data
- `EXA_API_KEY`: Exa AI API key for web research
- `FIRECRAWL_API_KEY`: Firecrawl API key for website scraping

## Deployment Methods

### Method 1: Quick Deployment Script

1. **Configure environment:**
```bash
export PROJECT_ID="your-gcp-project-id"
export SERVICE_NAME="adk-sales-system"
export REGION="us-central1"
```

2. **Run deployment script:**
```bash
chmod +x deploy-cloud-run.sh
./deploy-cloud-run.sh
```

### Method 2: Manual Deployment

1. **Build and push Docker image:**
```bash
docker build -t gcr.io/$PROJECT_ID/adk-sales-system .
docker push gcr.io/$PROJECT_ID/adk-sales-system
```

2. **Create secrets for API keys:**
```bash
# Required
gcloud secrets create adk-secrets --data-file=/dev/stdin <<< '{"google-api-key":"YOUR_GOOGLE_API_KEY"}'

# Optional - add additional keys to the secret
gcloud secrets versions add adk-secrets --data-file=/dev/stdin <<< '{
  "google-api-key":"YOUR_GOOGLE_API_KEY",
  "hdw-api-token":"YOUR_HDW_TOKEN",
  "exa-api-key":"YOUR_EXA_KEY",
  "firecrawl-api-key":"YOUR_FIRECRAWL_KEY"
}'
```

3. **Deploy to Cloud Run:**
```bash
gcloud run deploy adk-sales-system \
    --image gcr.io/$PROJECT_ID/adk-sales-system \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 10 \
    --max-instances 5 \
    --set-env-vars="PORT=8080"
```

### Method 3: Using Service YAML

1. **Update service.yaml with your project ID**
2. **Deploy using kubectl:**
```bash
gcloud run services replace service.yaml --region=us-central1
```

## Configuration

### Resource Allocation
- **Memory**: 2GB (recommended for LLM processing)
- **CPU**: 1 vCPU
- **Timeout**: 3600s (1 hour for long prospect searches)
- **Concurrency**: 10 concurrent requests
- **Max Instances**: 5 (adjust based on expected load)

### Security
- Service runs with minimal permissions
- API keys stored in Google Secret Manager
- No persistent data storage (stateless)
- HTTPS only

### Environment Variables
```bash
# Cloud Run automatically sets
PORT=8080

# You need to configure these
GOOGLE_API_KEY=<your-google-api-key>
HDW_API_TOKEN=<optional-hdw-token>
EXA_API_KEY=<optional-exa-key>
FIRECRAWL_API_KEY=<optional-firecrawl-key>
```

## Post-Deployment

### 1. Verify Deployment
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe adk-sales-system --region=us-central1 --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Expected response:
# {"status":"healthy","service":"adk-sales-system","version":"1.0.0"}
```

### 2. Test Web Interface
Open the service URL in your browser to access the Gradio web interface.

### 3. Configure Monitoring (Optional)
```bash
# Enable monitoring
gcloud services enable monitoring.googleapis.com

# Set up alerting policies in Cloud Console
```

### 4. Custom Domain (Optional)
```bash
# Map custom domain
gcloud run domain-mappings create \
    --service adk-sales-system \
    --domain your-domain.com \
    --region us-central1
```

## Troubleshooting

### Common Issues

1. **Container fails to start**
   - Check logs: `gcloud run logs tail adk-sales-system --region=us-central1`
   - Verify environment variables are set
   - Ensure Docker image builds locally

2. **Memory issues**
   - Increase memory allocation to 4GB if needed
   - Monitor resource usage in Cloud Console

3. **Timeout errors**
   - Increase timeout for long-running prospect searches
   - Consider implementing async processing for large requests

4. **API rate limits**
   - Monitor external API usage
   - Implement request queuing if needed

### Logs and Monitoring
```bash
# View real-time logs
gcloud run logs tail adk-sales-system --region=us-central1

# View metrics in Cloud Console
https://console.cloud.google.com/run/detail/us-central1/adk-sales-system
```

## Cost Optimization

### Pricing Factors
- **Requests**: $0.40 per million requests
- **CPU**: $0.0000096 per vCPU-second
- **Memory**: $0.000001 per GB-second
- **Egress**: $0.12 per GB

### Optimization Tips
1. Use appropriate resource allocation
2. Implement request caching
3. Monitor and adjust max instances
4. Consider using scheduled scaling for predictable workloads

## Security Best Practices

1. **API Keys**: Store in Secret Manager, never in code
2. **Authentication**: Enable Cloud IAM for enterprise use
3. **Network**: Use VPC connector for private resources
4. **Logging**: Enable audit logs for compliance

## Scaling

### Automatic Scaling
- Cloud Run automatically scales 0 → N based on demand
- Configure max instances to control costs
- Set min instances to reduce cold starts

### Performance Tuning
- Monitor response times and adjust resources
- Use Cloud CDN for static assets if needed
- Consider regional deployment for global users

## Support

For issues or questions:
1. Check Cloud Run documentation
2. Review application logs
3. Test locally with Docker
4. Contact Google Cloud Support for infrastructure issues