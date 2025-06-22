#!/usr/bin/env python3
"""Test the flexible industry search functionality."""

import asyncio
import os
from pathlib import Path
import sys

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config
from agents.adk_prospect_agent import ADKProspectAgent
from utils.logging_config import setup_logging, get_logger

# Setup logging
setup_logging(
    log_file="logs/test_flexible_industry.log",
    console_level="INFO",
    file_level="DEBUG"
)
logger = get_logger(__name__)


async def test_industry_fallback():
    """Test the flexible industry fallback functionality."""
    
    # Load config
    config = Config.load_from_file()
    
    # Initialize prospect agent
    prospect_agent = ADKProspectAgent(config)
    
    print("\n=== Testing Flexible Industry Search ===\n")
    
    # Test cases with different specific industries
    test_cases = [
        {
            "name": "AI/ML Industries",
            "industries": ["Artificial Intelligence", "Machine Learning", "GenAI"],
            "expected_broader": ["Technology", "Software", "Computer Software"]
        },
        {
            "name": "FinTech Industries", 
            "industries": ["FinTech", "Digital Banking", "Cryptocurrency"],
            "expected_broader": ["Financial Services", "Technology", "Banking"]
        },
        {
            "name": "BioTech Industries",
            "industries": ["Biotechnology", "Genomics", "Bioinformatics"],
            "expected_broader": ["Healthcare", "Pharmaceuticals", "Life Sciences"]
        },
        {
            "name": "GreenTech Industries",
            "industries": ["Clean Energy", "Solar Power", "Sustainable Technology"],
            "expected_broader": ["Energy", "Renewables & Environment", "Technology"]
        },
        {
            "name": "EdTech Industries",
            "industries": ["Educational Technology", "E-Learning", "Online Education"],
            "expected_broader": ["Education", "Technology", "Software"]
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Specific industries: {test_case['industries']}")
        
        # Test the _get_broader_industries method
        broader_industries = await prospect_agent._get_broader_industries(test_case['industries'])
        
        print(f"LLM suggested broader industries: {broader_industries}")
        print(f"Expected types: {test_case['expected_broader']}")
        
        # Check if any expected industry was suggested
        matches = [ind for ind in broader_industries if ind in test_case['expected_broader']]
        if matches:
            print(f"✅ Found matching broader industries: {matches}")
        else:
            print(f"⚠️  No exact matches, but got: {broader_industries}")
    
    print("\n=== Testing Keyword Enhancement ===\n")
    
    # Test keyword enhancement
    keyword_tests = [
        {
            "base": "VP Sales",
            "industries": ["Artificial Intelligence", "Machine Learning"],
            "description": "AI/ML Sales Executive"
        },
        {
            "base": "Marketing Director", 
            "industries": ["FinTech", "Blockchain"],
            "description": "FinTech Marketing Leader"
        },
        {
            "base": "Business Development",
            "industries": ["Healthcare Technology", "Digital Health"],
            "description": "HealthTech BD"
        }
    ]
    
    for test in keyword_tests:
        print(f"\nTest: {test['description']}")
        print(f"Base keywords: '{test['base']}'")
        print(f"Industries: {test['industries']}")
        
        enhanced = await prospect_agent._enhance_search_keywords(test['base'], test['industries'])
        
        print(f"Enhanced keywords: '{enhanced}'")
        
        if enhanced != test['base']:
            print("✅ Keywords were enhanced")
        else:
            print("⚠️  Keywords unchanged")
    
    print("\n=== Test Complete ===\n")


async def test_full_search_with_fallback():
    """Test a full prospect search with industry fallback."""
    
    # Load config
    config = Config.load_from_file()
    
    # Initialize prospect agent  
    prospect_agent = ADKProspectAgent(config)
    
    print("\n=== Testing Full Search with Fallback ===\n")
    
    # Test with a niche industry that likely won't have direct URNs
    icp_criteria = {
        "company_criteria": {
            "industry": {
                "values": ["Quantum Computing", "Quantum Technology"],
                "weight": 0.3
            },
            "company_size": {
                "values": ["51-200", "201-500"],
                "weight": 0.2
            }
        },
        "person_criteria": {
            "titles": {
                "values": ["CTO", "VP Engineering", "Head of Technology"],
                "weight": 0.3
            }
        }
    }
    
    print("Searching with ICP criteria:")
    print(f"Industries: {icp_criteria['company_criteria']['industry']['values']}")
    print(f"Target roles: {icp_criteria['person_criteria']['titles']['values']}")
    
    # Perform search (limit to 3 for testing)
    result = await prospect_agent.search_prospects_multi_source(
        icp_criteria=icp_criteria,
        search_limit=3,
        sources=["hdw"],  # Just HDW for this test
        location_filter="United States"
    )
    
    if result["status"] == "success":
        print(f"\n✅ Search completed successfully!")
        print(f"Prospects found: {result.get('prospect_count', 0)}")
    else:
        print(f"\n❌ Search failed: {result.get('error_message', 'Unknown error')}")


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY environment variable not set")
        sys.exit(1)
    
    # Run tests
    asyncio.run(test_industry_fallback())
    
    # Optional: Run full search test if HDW token is available
    if os.getenv("HDW_API_TOKEN"):
        print("\n" + "="*50 + "\n")
        asyncio.run(test_full_search_with_fallback())
    else:
        print("\nSkipping full search test (HDW_API_TOKEN not set)")