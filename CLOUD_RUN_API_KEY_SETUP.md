# Setting up GOOGLE_API_KEY on Cloud Run

The application requires GOOGLE_API_KEY to be set for proper intent detection and agent functionality.

## Option 1: Using Secret Manager (Recommended for Production)

1. Create a secret in Google Secret Manager:
```bash
# Create the secret
echo -n "YOUR_GOOGLE_API_KEY_HERE" | gcloud secrets create google-api-key --data-file=-

# Grant access to the Cloud Run service account
gcloud secrets add-iam-policy-binding google-api-key \
  --member="serviceAccount:193823146879-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

2. Update Cloud Run service to use the secret:
```bash
gcloud run services update onsa-icp-agent \
  --region=us-central1 \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest"
```

## Option 2: Direct Environment Variable (Quick Testing)

```bash
gcloud run services update onsa-icp-agent \
  --region=us-central1 \
  --set-env-vars "GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY_HERE"
```

**Note**: This method exposes the API key in the Cloud Run configuration. Use Secret Manager for production.

## Verifying the Configuration

After setting the API key, you can verify it's working by:

1. Checking the service logs:
```bash
gcloud run services logs read onsa-icp-agent --region=us-central1 --limit=50
```

2. Testing a greeting:
- Visit your Cloud Run URL
- Type "hello" or "hi"
- You should receive a proper greeting response instead of "I'm not quite sure what you'd like me to do..."

## Other Required API Keys

For full functionality, you may also want to set:
- `HDW_API_TOKEN` - For HorizonDataWave LinkedIn data
- `EXA_API_KEY` - For Exa web research
- `FIRECRAWL_API_KEY` - For Firecrawl website analysis

These can be set using the same methods as above.