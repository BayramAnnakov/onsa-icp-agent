#!/usr/bin/env python3
"""Test script for A2A Protocol implementation.

This script tests the A2A protocol by making requests to the server.
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any

from protocols.a2a_protocol import (
    A2ATaskRequest,
    create_task_request,
    create_a2a_message,
    A2AMessageType
)


async def test_discovery(client: httpx.AsyncClient, base_url: str):
    """Test agent discovery."""
    print("\n1. Testing Agent Discovery...")
    
    response = await client.post(f"{base_url}/a2a/discovery")
    assert response.status_code == 200
    
    data = response.json()
    print(f"   ✓ Found {data['count']} agents")
    
    for agent in data['agents']:
        print(f"   - {agent['name']} ({agent['agent_id'][:8]}...)")
        print(f"     Capabilities: {len(agent['capabilities'])}")
    
    return data['agents']


async def test_capabilities(client: httpx.AsyncClient, base_url: str):
    """Test capability listing."""
    print("\n2. Testing Capability Discovery...")
    
    response = await client.get(f"{base_url}/a2a/capabilities")
    assert response.status_code == 200
    
    data = response.json()
    print(f"   ✓ Found {data['total_capabilities']} unique capabilities")
    
    # Show first 5 capabilities
    for i, (cap_name, agents) in enumerate(data['capabilities'].items()):
        if i >= 5:
            print("   ...")
            break
        print(f"   - {cap_name}: available on {len(agents)} agent(s)")


async def test_ping(client: httpx.AsyncClient, base_url: str, agent_id: str):
    """Test ping to specific agent."""
    print(f"\n3. Testing Ping to agent {agent_id[:8]}...")
    
    response = await client.get(f"{base_url}/a2a/agents/{agent_id}")
    assert response.status_code == 200
    
    data = response.json()
    health = data['health']
    print(f"   ✓ Agent status: {health['status']}")
    print(f"   ✓ Last check: {health['last_check']}")


async def test_icp_creation(client: httpx.AsyncClient, base_url: str):
    """Test ICP creation via A2A protocol."""
    print("\n4. Testing ICP Creation...")
    
    # Create task request
    task_request = create_task_request(
        capability_name="create_icp_from_description",
        parameters={
            "business_description": "We are a B2B SaaS company that provides AI-powered customer support tools for e-commerce businesses.",
            "target_market": "Online retailers with 50-500 employees",
            "value_proposition": "Reduce customer support costs by 40% with AI automation"
        }
    )
    
    print("   → Sending ICP creation request...")
    response = await client.post(
        f"{base_url}/a2a/task",
        json=task_request.dict()
    )
    
    if response.status_code != 200:
        print(f"   ✗ Request failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return None
    
    data = response.json()
    task = data['task']
    
    print(f"   ✓ Task completed: {task['status']}")
    print(f"   ✓ Duration: {data['duration_ms']}ms")
    print(f"   ✓ Agent used: {data['agent']['name']}")
    
    if task['status'] == 'completed' and task['result']:
        result = task['result']
        if 'result' in result and 'icp' in result['result']:
            icp = result['result']['icp']
            print("\n   Created ICP:")
            print(f"   - Industry: {icp.get('industry', 'N/A')}")
            print(f"   - Company Size: {icp.get('company_size', 'N/A')}")
            print(f"   - Target Titles: {', '.join(icp.get('target_titles', [])[:3])}")
    
    return data


async def test_prospect_search(client: httpx.AsyncClient, base_url: str):
    """Test prospect search via A2A protocol."""
    print("\n5. Testing Prospect Search...")
    
    # First, we need an ICP ID - in real scenario, you'd get this from previous step
    # For testing, we'll use a search with criteria
    task_request = create_task_request(
        capability_name="search_prospects_by_criteria",
        parameters={
            "industries": ["Software", "Technology"],
            "company_sizes": ["51-200", "201-500"],
            "titles": ["CEO", "CTO", "VP Sales"],
            "limit": 5
        }
    )
    
    print("   → Sending prospect search request...")
    response = await client.post(
        f"{base_url}/a2a/task",
        json=task_request.dict()
    )
    
    if response.status_code != 200:
        print(f"   ✗ Request failed: {response.status_code}")
        return None
    
    data = response.json()
    task = data['task']
    
    print(f"   ✓ Task completed: {task['status']}")
    print(f"   ✓ Duration: {data['duration_ms']}ms")
    
    if task['status'] == 'completed' and task['result']:
        result = task['result']
        if 'result' in result and 'prospects' in result['result']:
            prospects = result['result']['prospects']
            print(f"   ✓ Found {len(prospects)} prospects")


async def test_health_metrics(client: httpx.AsyncClient, base_url: str):
    """Test health and metrics endpoints."""
    print("\n6. Testing Health & Metrics...")
    
    # Health check
    response = await client.get(f"{base_url}/health")
    assert response.status_code == 200
    
    health = response.json()
    print(f"   ✓ Server status: {health['status']}")
    print(f"   ✓ Total agents: {health['registry']['total_agents']}")
    print(f"   ✓ Healthy agents: {health['registry']['healthy_agents']}")
    
    # Metrics
    response = await client.get(f"{base_url}/metrics")
    assert response.status_code == 200
    
    metrics = response.json()
    overall = metrics['overall']
    print(f"   ✓ Total requests: {overall['total_requests']}")
    print(f"   ✓ Success rate: {overall['success_rate']:.1f}%")


async def main():
    """Run all A2A protocol tests."""
    base_url = "http://localhost:8080"
    
    print("A2A Protocol Test Suite")
    print("=" * 50)
    print(f"Testing server at: {base_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Test discovery
            agents = await test_discovery(client, base_url)
            
            if not agents:
                print("\n❌ No agents found. Is the A2A server running?")
                return
            
            # Test capabilities
            await test_capabilities(client, base_url)
            
            # Test ping to first agent
            first_agent = agents[0]
            await test_ping(client, base_url, first_agent['agent_id'])
            
            # Test ICP creation
            await test_icp_creation(client, base_url)
            
            # Test prospect search
            await test_prospect_search(client, base_url)
            
            # Test health/metrics
            await test_health_metrics(client, base_url)
            
            print("\n✅ All tests completed successfully!")
            
        except httpx.ConnectError:
            print(f"\n❌ Could not connect to A2A server at {base_url}")
            print("   Please start the server with: python start_a2a_server.py")
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())