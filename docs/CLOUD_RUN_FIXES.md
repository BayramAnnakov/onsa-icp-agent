# Cloud Run Streaming and Prospect Search Fixes

## Issues Addressed

1. **JSON Parsing Error in Prospect Agent**
   - Fixed: "cannot access local variable 'json' where it is not associated with a value"
   - Added validation check for `_extract_json_from_response` return value
   - Now properly handles cases where no JSON is found in LLM response

2. **Streaming Not Working in Cloud Run**
   - Added deployment mode detection (`DEPLOYMENT_MODE` environment variable)
   - Implemented non-streaming fallback for Cloud Run deployment
   - Added comprehensive logging for streaming progress
   - Web interface now automatically switches between streaming and non-streaming modes

3. **API Timeouts and Search Failures**
   - Added 30-second timeout for individual API calls (HDW, Exa)
   - Added overall timeout for parallel search tasks
   - Improved error logging with exception types and detailed messages
   - HDW search already had timeout configured, ensured it's working properly

4. **Resource Optimization**
   - Reduced container concurrency from 10 to 5 to prevent resource contention
   - Added proper async timeout handling to prevent hanging requests

## Changes Made

### 1. agents/adk_prospect_agent.py
- Added validation for JSON extraction before parsing
- Added timeout handling for parallel search tasks
- Added timeout for Exa API calls
- Improved error logging with more details

### 2. web_interface.py
- Added deployment mode detection in `__init__`
- Added `process_message_non_stream` method for Cloud Run
- Modified `respond` handler to use appropriate mode based on deployment
- Added logging for streaming progress
- Set `DEPLOYMENT_MODE=cloud_run` in `run_cloud_server`

### 3. service.yaml
- Reduced `containerConcurrency` from 10 to 5

### 4. scripts/cloud_run_entrypoint.sh (NEW)
- Created entrypoint script that sets `DEPLOYMENT_MODE=cloud_run`
- Logs environment information for debugging

### 5. Dockerfile
- Updated to use the new entrypoint script
- Made entrypoint script executable

## How It Works

1. **Local Development**: 
   - Uses streaming mode by default
   - Real-time response updates in the UI

2. **Cloud Run Deployment**:
   - Automatically detects Cloud Run environment
   - Falls back to non-streaming mode
   - Returns complete responses instead of streaming chunks
   - Better compatibility with Cloud Run's request/response model

## Testing

To test locally with Cloud Run mode:
```bash
export DEPLOYMENT_MODE=cloud_run
python web_interface.py
```

To deploy to Cloud Run:
```bash
./deploy-cloud-run.sh
```

## Monitoring

Look for these log entries:
- "Using non-streaming mode for Cloud Run" - Confirms fallback is active
- "Streaming completed - Total chunks: X" - Shows streaming progress
- Timeout errors will show "timed out after 30 seconds"
- API errors now include exception type and full message