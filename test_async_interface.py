#!/usr/bin/env python3
"""
Test script to verify async interface works properly in both deployment modes.
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup Python path
sys.path.insert(0, str(Path(__file__).parent))

from web_interface import WebInterface


async def test_async_operations():
    """Test async operations of the web interface."""
    print("Testing async operations...")
    
    # Create web interface
    web_interface = WebInterface()
    
    # Start a conversation
    conv_id = await web_interface.start_conversation("test_user")
    print(f"✓ Started conversation: {conv_id}")
    
    # Test message processing
    test_message = "hello"
    history = []
    
    print(f"\nTesting message: '{test_message}'")
    response_count = 0
    
    async for updated_history, status, table_data, table_visible in web_interface.process_message_stream(
        message=test_message,
        history=history,
        agent_type="Main Workflow",
        attachments=None
    ):
        response_count += 1
        if response_count == 1:
            print(f"✓ First response received")
        
        # Check if we got a response
        if updated_history and len(updated_history) > 0:
            user_msg, agent_response = updated_history[-1]
            if agent_response:
                print(f"✓ Agent response: {agent_response[:100]}...")
    
    print(f"✓ Total streaming responses: {response_count}")
    
    # Test with a business description
    test_business = "We are a B2B SaaS company at https://example.com"
    history = []
    
    print(f"\nTesting business description: '{test_business}'")
    response_count = 0
    
    async for updated_history, status, table_data, table_visible in web_interface.process_message_stream(
        message=test_business,
        history=history,
        agent_type="Main Workflow",
        attachments=None
    ):
        response_count += 1
        if table_visible and table_data:
            print(f"✓ Prospect table data received: {len(table_data)} rows")
    
    print(f"✓ Total streaming responses: {response_count}")
    
    print("\n✅ All async operations completed successfully!")


def test_deployment_modes():
    """Test both deployment modes."""
    print("Testing deployment modes...")
    
    # Test local mode
    os.environ["DEPLOYMENT_MODE"] = "local"
    from web_interface import create_app_for_deployment
    
    print("\n1. Testing local deployment mode...")
    app_local = create_app_for_deployment("local")
    print("✓ Local app created successfully")
    
    # Test cloud run mode
    print("\n2. Testing cloud_run deployment mode...")
    app_cloud, web_interface = create_app_for_deployment("cloud_run")
    print("✓ Cloud Run app created successfully")
    
    print("\n✅ Both deployment modes work correctly!")


if __name__ == "__main__":
    print("ADK Web Interface Async Test\n")
    
    # Test deployment modes
    test_deployment_modes()
    
    # Test async operations
    print("\n" + "="*50 + "\n")
    asyncio.run(test_async_operations())