# Unified Deployment Architecture

## Overview

The ADK Multi-Agent Sales Lead Generation System now uses a unified codebase for both local and Cloud Run deployments. This ensures feature parity and reduces maintenance overhead.

## Architecture

### Single Source of Truth: `web_interface.py`

All UI functionality, including async message streaming and prospect table display, is implemented in `web_interface.py`. This file supports multiple deployment modes:

- **Local mode**: Direct Gradio server on port 7860
- **Cloud Run mode**: FastAPI-mounted Gradio on port 8080 with health checks

### Deployment Mode Selection

The deployment mode is controlled by the `DEPLOYMENT_MODE` environment variable:

```bash
# For local development
export DEPLOYMENT_MODE=local  # or leave unset (defaults to local)
python web_interface.py

# For Cloud Run (automatically set in Dockerfile)
export DEPLOYMENT_MODE=cloud_run
python web_interface.py  # or python main.py
```

### Key Features in Both Modes

1. **Async Message Streaming**: Native async/await support for real-time responses
2. **Prospect Table Display**: Dynamic table that appears when prospects are found
3. **Session Management**: Save/load conversation sessions
4. **Multi-Agent Support**: Direct access to ICP, Research, and Prospect agents
5. **Health Checks**: Available at `/health` in Cloud Run mode
6. **API Status Display**: Shows which external APIs are configured

## Implementation Details

### Async Handling

The system uses Gradio's native async support:

```python
async def respond(message, chat_history, agent, attach_text):
    async for updated_history, new_status, table_data, table_visible in web_interface.process_message_stream(...):
        if table_visible and table_data:
            yield updated_history, new_status, gr.update(value=table_data, visible=True)
        else:
            yield updated_history, new_status, gr.update(visible=False)
```

### Cloud Run Entry Point

`main.py` is now a thin wrapper that:
1. Sets `DEPLOYMENT_MODE=cloud_run`
2. Imports and runs `run_cloud_server()` from `web_interface.py`

### Local Development

For local development, simply run:
```bash
python web_interface.py
```

The system will automatically:
- Use port 7860 (or `PORT` env var)
- Launch Gradio directly without FastAPI
- Enable all UI features

### Cloud Run Deployment

The Dockerfile sets:
- `DEPLOYMENT_MODE=cloud_run`
- `PORT=8080`
- Runs `web_interface.py` which detects Cloud Run mode

## Benefits

1. **Single Codebase**: All features in one file
2. **Feature Parity**: No missing features between deployments
3. **Easier Testing**: Test all features locally before deploying
4. **Reduced Maintenance**: Update one file instead of two
5. **Consistent Async**: Same async handling in both modes

## Testing

Run the test script to verify both modes work:
```bash
python test_async_interface.py
```

This tests:
- Deployment mode switching
- Async message streaming
- Prospect table updates
- Error handling