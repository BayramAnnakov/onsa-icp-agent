#!/bin/bash
# Cloud Run entrypoint script

# Set deployment mode for Cloud Run
export DEPLOYMENT_MODE="cloud_run"

# Log environment info
echo "Starting ADK Sales System in Cloud Run mode"
echo "PORT: ${PORT:-8080}"
echo "GOOGLE_CLOUD_PROJECT: ${GOOGLE_CLOUD_PROJECT}"
echo "VERTEX_AI_ENABLED: ${VERTEX_AI_ENABLED}"

# Start the web interface
exec python web_interface.py