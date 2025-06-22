#!/usr/bin/env python3
"""Example A2A Protocol Client.

This example shows how to interact with the A2A server to use agent capabilities.
"""

import asyncio
import httpx
import json
from typing import Dict, Any, List, Optional


class A2AClient:
    """Simple client for interacting with A2A Protocol Server."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def discover_agents(self, capability: Optional[str] = None) -> List[Dict[str, Any]]:
        """Discover available agents."""
        filters = {"capability": capability} if capability else None
        response = await self.client.post(
            f"{self.base_url}/a2a/discovery",
            json=filters
        )
        response.raise_for_status()
        return response.json()["agents"]
    
    async def get_capabilities(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available capabilities."""
        response = await self.client.get(f"{self.base_url}/a2a/capabilities")
        response.raise_for_status()
        return response.json()["capabilities"]
    
    async def execute_task(
        self,
        capability: str,
        parameters: Dict[str, Any],
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a task on an agent."""
        from protocols.a2a_protocol import create_task_request
        
        task_request = create_task_request(
            capability_name=capability,
            parameters=parameters
        )
        
        if agent_id:
            # Execute on specific agent
            url = f"{self.base_url}/a2a/agents/{agent_id}/task"
        else:
            # Execute on any available agent
            url = f"{self.base_url}/a2a/task"
        
        response = await self.client.post(url, json=task_request.dict())
        response.raise_for_status()
        return response.json()
    
    async def get_agent_info(self, agent_id: str) -> Dict[str, Any]:
        """Get information about a specific agent."""
        response = await self.client.get(f"{self.base_url}/a2a/agents/{agent_id}")
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()


async def example_workflow():
    """Example workflow using the A2A client."""
    
    print("A2A Client Example: B2B Sales Lead Generation")
    print("=" * 50)
    
    async with A2AClient() as client:
        # 1. Check server health
        print("\n1. Checking server health...")
        health = await client.health_check()
        print(f"   Server status: {health['status']}")
        print(f"   Active agents: {health['registry']['total_agents']}")
        
        # 2. Discover available agents
        print("\n2. Discovering agents...")
        agents = await client.discover_agents()
        for agent in agents:
            print(f"   - {agent['name']}: {agent['description']}")
        
        # 3. Get available capabilities
        print("\n3. Getting capabilities...")
        capabilities = await client.get_capabilities()
        print(f"   Found {len(capabilities)} unique capabilities")
        
        # Show ICP-related capabilities
        icp_capabilities = [
            cap for cap in capabilities.keys()
            if 'icp' in cap.lower()
        ]
        print(f"   ICP capabilities: {', '.join(icp_capabilities)}")
        
        # 4. Create an ICP
        print("\n4. Creating an ICP...")
        icp_result = await client.execute_task(
            capability="create_icp_from_description",
            parameters={
                "business_description": """
                We are a cloud infrastructure monitoring platform that helps DevOps teams 
                track and optimize their AWS, Azure, and GCP costs. Our AI-powered 
                recommendations have saved customers an average of 30% on cloud bills.
                """,
                "target_market": "Technology companies with 100-1000 employees",
                "value_proposition": "Reduce cloud costs by 30% with AI-powered optimization"
            }
        )
        
        if icp_result["task"]["status"] == "completed":
            print("   ✓ ICP created successfully!")
            icp_data = icp_result["task"]["result"]["result"]["icp"]
            print(f"   Industry: {icp_data.get('industry', 'N/A')}")
            print(f"   Company Size: {icp_data.get('company_size', 'N/A')}")
            
            # Store ICP ID for later use
            icp_id = icp_data.get('id')
        
        # 5. Research a company
        print("\n5. Researching a company...")
        research_result = await client.execute_task(
            capability="analyze_company_comprehensive",
            parameters={
                "company_identifier": "https://datadog.com",
                "analysis_depth": "standard",
                "focus_areas": ["business_model", "technology", "market_position"]
            }
        )
        
        if research_result["task"]["status"] == "completed":
            print("   ✓ Company research completed!")
            print(f"   Duration: {research_result['duration_ms']}ms")
        
        # 6. Search for prospects
        print("\n6. Searching for prospects...")
        prospect_result = await client.execute_task(
            capability="search_prospects_by_criteria",
            parameters={
                "industries": ["Software", "Technology", "Cloud Computing"],
                "company_sizes": ["201-500", "501-1000"],
                "titles": ["VP Engineering", "CTO", "Director of DevOps"],
                "limit": 10
            }
        )
        
        if prospect_result["task"]["status"] == "completed":
            prospects = prospect_result["task"]["result"]["result"]["prospects"]
            print(f"   ✓ Found {len(prospects)} prospects!")
            
            # Show first 3 prospects
            for i, prospect in enumerate(prospects[:3]):
                person = prospect.get('person', {})
                company = prospect.get('company', {})
                print(f"\n   Prospect {i+1}:")
                print(f"   - Name: {person.get('first_name', '')} {person.get('last_name', '')}")
                print(f"   - Title: {person.get('title', 'N/A')}")
                print(f"   - Company: {company.get('name', 'N/A')}")
        
        # 7. Get metrics
        print("\n7. Checking performance metrics...")
        metrics_response = await client.client.get(f"{client.base_url}/metrics")
        metrics = metrics_response.json()
        
        overall = metrics["overall"]
        print(f"   Total requests: {overall['total_requests']}")
        print(f"   Success rate: {overall['success_rate']:.1f}%")
        
        print("\n✅ Example workflow completed!")


async def example_async_execution():
    """Example of executing multiple tasks concurrently."""
    
    print("\nA2A Client Example: Concurrent Task Execution")
    print("=" * 50)
    
    async with A2AClient() as client:
        print("\nExecuting multiple research tasks concurrently...")
        
        # Define multiple research tasks
        companies = [
            "https://salesforce.com",
            "https://hubspot.com",
            "https://zendesk.com"
        ]
        
        # Execute research tasks concurrently
        tasks = []
        for company in companies:
            task = client.execute_task(
                capability="analyze_company_comprehensive",
                parameters={
                    "company_identifier": company,
                    "analysis_depth": "basic",
                    "focus_areas": ["business_model", "target_market"]
                }
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for company, result in zip(companies, results):
            if isinstance(result, Exception):
                print(f"\n❌ Error researching {company}: {str(result)}")
            else:
                status = result["task"]["status"]
                duration = result.get("duration_ms", 0)
                print(f"\n✓ {company}: {status} ({duration}ms)")


if __name__ == "__main__":
    print("Running A2A client examples...\n")
    
    # Run main workflow
    asyncio.run(example_workflow())
    
    # Run concurrent execution example
    asyncio.run(example_async_execution())