"""Comprehensive test runner for all agents."""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import test functions
from test_base_agent import run_base_agent_tests
from test_icp_agent import run_icp_agent_tests
from test_research_agent import run_research_agent_tests
from test_prospect_agent import run_prospect_agent_tests


def print_header(title: str):
    """Print formatted test section header."""
    print(f"\n{'='*70}")
    print(f"🧪 {title}")
    print(f"{'='*70}")


def print_summary(results: dict):
    """Print test results summary."""
    print_header("AGENT TESTS SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    for agent_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{agent_name:<20} | {status}")
    
    print(f"\n📊 Results: {passed_tests}/{total_tests} tests passed")
    
    if failed_tests > 0:
        print(f"❌ {failed_tests} test(s) failed")
        return False
    else:
        print("🎉 All agent tests passed!")
        return True


def check_environment():
    """Check required environment variables."""
    print_header("ENVIRONMENT CHECK")
    
    required_vars = [
        "GOOGLE_API_KEY",
        "HDW_API_TOKEN", 
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var} = {value[:10]}...")
        else:
            print(f"❌ {var} = NOT SET")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️ Missing environment variables: {missing_vars}")
        print("Some tests may fail or be skipped.")
        return False
    else:
        print("\n✅ All required environment variables are set!")
        return True


def run_all_agent_tests():
    """Run all agent tests."""
    print_header("MULTI-AGENT SYSTEM - AGENT TESTS")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Check environment
    env_ok = check_environment()
    
    # Test results
    results = {}
    
    # 1. Base Agent Tests
    print_header("BASE AGENT TESTS")
    try:
        results["Base Agent"] = run_base_agent_tests()
    except Exception as e:
        print(f"❌ Base Agent tests failed with exception: {e}")
        results["Base Agent"] = False
    
    # 2. ICP Agent Tests
    print_header("ICP AGENT TESTS")
    try:
        results["ICP Agent"] = run_icp_agent_tests()
    except Exception as e:
        print(f"❌ ICP Agent tests failed with exception: {e}")
        results["ICP Agent"] = False
    
    # 3. Research Agent Tests
    print_header("RESEARCH AGENT TESTS")
    try:
        results["Research Agent"] = run_research_agent_tests()
    except Exception as e:
        print(f"❌ Research Agent tests failed with exception: {e}")
        results["Research Agent"] = False
    
    # 4. Prospect Agent Tests
    print_header("PROSPECT AGENT TESTS")
    try:
        results["Prospect Agent"] = run_prospect_agent_tests()
    except Exception as e:
        print(f"❌ Prospect Agent tests failed with exception: {e}")
        results["Prospect Agent"] = False
    
    # Print summary
    success = print_summary(results)
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    
    return success


def run_specific_agent_test(agent_name: str):
    """Run tests for a specific agent."""
    agent_name_lower = agent_name.lower()
    
    if agent_name_lower == "base":
        print_header("BASE AGENT TESTS")
        return run_base_agent_tests()
    elif agent_name_lower == "icp":
        print_header("ICP AGENT TESTS")
        return run_icp_agent_tests()
    elif agent_name_lower == "research":
        print_header("RESEARCH AGENT TESTS")
        return run_research_agent_tests()
    elif agent_name_lower == "prospect":
        print_header("PROSPECT AGENT TESTS")
        return run_prospect_agent_tests()
    else:
        print(f"❌ Unknown agent: {agent_name}")
        print("Available agents: base, icp, research, prospect")
        return False


def run_integration_test():
    """Run basic integration test with all agents."""
    print_header("AGENT INTEGRATION TEST")
    
    try:
        from utils.config import Config
        from utils.cache import CacheManager, CacheConfig
        from agents.icp_agent import ICPAgent
        from agents.research_agent import ResearchAgent
        from agents.prospect_agent import ProspectAgent
        
        # Initialize configuration and cache
        config = Config.load_from_file("config.yaml")
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        cache_manager = CacheManager(cache_config)
        
        # Initialize all agents
        icp_agent = ICPAgent(config=config, cache_manager=cache_manager)
        research_agent = ResearchAgent(config=config, cache_manager=cache_manager)
        prospect_agent = ProspectAgent(config=config, cache_manager=cache_manager)
        
        print("✅ All agents initialized successfully")
        
        # Test agent capabilities
        icp_caps = icp_agent.get_capabilities()
        research_caps = research_agent.get_capabilities()
        prospect_caps = prospect_agent.get_capabilities()
        
        print(f"✅ ICP Agent capabilities: {len(icp_caps)}")
        print(f"✅ Research Agent capabilities: {len(research_caps)}")
        print(f"✅ Prospect Agent capabilities: {len(prospect_caps)}")
        
        # Test agent IDs are unique
        agent_ids = [icp_agent.agent_id, research_agent.agent_id, prospect_agent.agent_id]
        assert len(set(agent_ids)) == 3, "Agent IDs should be unique"
        print("✅ All agent IDs are unique")
        
        # Test FastAPI apps are created
        assert icp_agent.app is not None, "ICP Agent FastAPI app should be created"
        assert research_agent.app is not None, "Research Agent FastAPI app should be created"
        assert prospect_agent.app is not None, "Prospect Agent FastAPI app should be created"
        print("✅ All agent FastAPI apps created")
        
        print("\n🎉 Agent integration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Agent integration test failed: {e}")
        return False


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run agent tests")
    parser.add_argument(
        "--agent", 
        type=str, 
        help="Run tests for specific agent (base, icp, research, prospect)"
    )
    parser.add_argument(
        "--integration", 
        action="store_true",
        help="Run integration tests"
    )
    parser.add_argument(
        "--smoke", 
        action="store_true",
        help="Run quick smoke tests only"
    )
    
    args = parser.parse_args()
    
    if args.integration:
        success = run_integration_test()
    elif args.agent:
        success = run_specific_agent_test(args.agent)
    elif args.smoke:
        # Quick smoke test - just check initialization
        print_header("AGENT SMOKE TESTS")
        check_environment()
        success = run_integration_test()
    else:
        success = run_all_agent_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()