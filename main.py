#!/usr/bin/env python3
"""
Cloud Run entry point for ADK Multi-Agent Sales Lead Generation System.

This is a thin wrapper that uses the unified web_interface.py with cloud_run deployment mode.
"""

import os
import sys
from pathlib import Path

# Setup Python path
sys.path.insert(0, str(Path(__file__).parent))

# Force cloud_run deployment mode
os.environ["DEPLOYMENT_MODE"] = "cloud_run"

# Import and run the cloud server from web_interface
from web_interface import run_cloud_server

if __name__ == "__main__":
    # Ensure required directories exist
    for directory in ["cache", "logs", "sessions", "data"]:
        Path(directory).mkdir(exist_ok=True)
    
    # Run the cloud server
    run_cloud_server()