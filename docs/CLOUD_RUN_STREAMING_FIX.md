# Cloud Run Streaming and Prospect Search Fix

## Issues Fixed

### 1. Streaming Not Working on Cloud Run
**Problem**: Cloud Run has limited support for streaming responses with Gradio's async generators.

**Solution**: 
- Added deployment mode detection via `DEPLOYMENT_MODE` environment variable
- Implemented `process_message_non_stream` method as fallback for Cloud Run
- Cloud Run now collects complete response before sending to client

### 2. Prospect Search Validation Error
**Problem**: LLM returned total_score of 1.1 which exceeds ProspectScore validation limit of 1.0.

**Solution**:
- Added score clamping to ensure all scores stay within [0.0, 1.0] range
- Added validation before creating ProspectScore objects
- Implemented fallback scoring when JSON parsing fails

### 3. API Timeout Issues
**Problem**: Long-running API calls to HDW/Exa causing timeouts.

**Solution**:
- Added explicit timeout handling (30s per API call, max 60s total)
- Improved error logging with exception types
- Added timeout parameters to API calls

## Files Modified

### `/agents/adk_prospect_agent.py`
```python
# Fix 1: Score validation
total_score = min(1.0, max(0.0, score_info.get("total_score", 0.5)))
company_score = min(1.0, max(0.0, score_info.get("company_match_score", 0.5)))
person_score = min(1.0, max(0.0, score_info.get("person_match_score", 0.5)))

# Fix 2: JSON validation
if not (json_str.strip().startswith('[') or json_str.strip().startswith('{')):
    logger.error(f"Invalid JSON format, does not start with [ or {{: {json_str[:100]}...")
    raise ValueError("Invalid JSON format in response")

# Fix 3: Fallback scoring on JSON parse error
except json.JSONDecodeError as e:
    # Use fallback scoring for all prospects
    scored_prospects = []
    for prospect in prospects:
        prospect.score = self._fallback_scoring(prospect, icp_criteria)
```

### `/web_interface.py`
```python
# Fix 1: Deployment mode detection
self.deployment_mode = os.environ.get("DEPLOYMENT_MODE", "local").lower()
self.is_cloud_run = self.deployment_mode == "cloud_run"
logger.info(f"Deployment mode detected: {self.deployment_mode}")

# Fix 2: Non-streaming for Cloud Run
if deployment_mode == "cloud_run":
    # Use non-streaming mode for Cloud Run deployment
    updated_history, new_status, table_data, table_visible = await web_interface.process_message_non_stream(...)
else:
    # Use streaming mode for local deployment
    async for updated_history, new_status, table_data, table_visible in web_interface.process_message_stream(...):
```

### `/Dockerfile`
```dockerfile
# Set deployment mode
ENV DEPLOYMENT_MODE=cloud_run

# Use entrypoint script
CMD ["./scripts/cloud_run_entrypoint.sh"]
```

### `/scripts/cloud_run_entrypoint.sh`
```bash
#!/bin/bash
# Set deployment mode for Cloud Run
export DEPLOYMENT_MODE="cloud_run"

# Start the web interface
exec python web_interface.py
```

### `/service.yaml`
```yaml
# Reduced concurrency for stability
containerConcurrency: 5

# Adequate timeout for long operations
run.googleapis.com/timeout: "3600s"
```

## Testing

Use the provided test script to verify deployment:
```bash
./scripts/test_cloud_run_deployment.sh
```

This checks:
1. Health endpoint
2. Root redirect to /gradio
3. Environment variables
4. Recent error logs
5. Streaming-related logs

## How It Works

### Local Mode
1. User sends message
2. Gradio calls `process_message_stream`
3. Response streams back chunk by chunk
4. UI updates in real-time

### Cloud Run Mode
1. User sends message
2. Gradio calls `process_message_non_stream`
3. Complete response generated server-side
4. Full response sent back at once
5. UI updates with complete data

## Deployment

To deploy with fixes:
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/adk-sales-system
gcloud run deploy onsa-icp-agent \
  --image gcr.io/$PROJECT_ID/adk-sales-system \
  --region us-central1 \
  --service-account adk-agent-memory@$PROJECT_ID.iam.gserviceaccount.com
```

## Monitoring

Check logs for deployment mode:
```bash
gcloud logging read "resource.type=cloud_run_revision AND textPayload:'Deployment mode detected'" --limit=5
```

Check for streaming errors:
```bash
gcloud logging read "resource.type=cloud_run_revision AND textPayload:'streaming'" --limit=10
```