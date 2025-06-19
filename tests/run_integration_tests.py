"""Run all integration tests for external APIs."""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables
load_dotenv()

from test_firecrawl_integration import run_firecrawl_tests
from test_hdw_integration import run_hdw_tests
from test_exa_integration import run_exa_tests


def check_environment():
    """Check if all required environment variables are set."""
    print("🔍 Checking Environment Variables")
    print("=" * 50)
    
    required_vars = {
        "GOOGLE_API_KEY": "Google Gemini API",
        "HDW_API_TOKEN": "HorizonDataWave API", 
        "EXA_API_KEY": "Exa AI API",
        "FIRECRAWL_API_KEY": "Firecrawl API"
    }
    
    missing_vars = []
    
    for var_name, service_name in required_vars.items():
        value = os.getenv(var_name)
        if value:
            print(f"✅ {service_name}: {var_name} = {value[:10]}...")
        else:
            print(f"❌ {service_name}: {var_name} = NOT SET")
            missing_vars.append(var_name)
    
    if missing_vars:
        print(f"\n⚠️ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file before running tests")
        return False
    else:
        print("\n✅ All environment variables are set!")
        return True


def run_all_integration_tests():
    """Run all integration tests."""
    print("🧪 Multi-Agent Lead Generation System - Integration Tests")
    print("=" * 70)
    
    # Check environment first
    if not check_environment():
        print("\n❌ Environment check failed. Please fix missing variables.")
        return False
    
    print("\n" + "=" * 70)
    
    results = {}
    
    # Test 1: Firecrawl Integration
    print("\n1️⃣ FIRECRAWL INTEGRATION TESTS")
    print("-" * 40)
    try:
        results["firecrawl"] = run_firecrawl_tests()
    except Exception as e:
        print(f"❌ Firecrawl tests crashed: {e}")
        results["firecrawl"] = False
    
    print("\n" + "-" * 70)
    
    # Test 2: HorizonDataWave Integration
    print("\n2️⃣ HORIZONDATAWAVE (HDW) INTEGRATION TESTS")
    print("-" * 40)
    try:
        results["hdw"] = run_hdw_tests()
    except Exception as e:
        print(f"❌ HDW tests crashed: {e}")
        results["hdw"] = False
    
    print("\n" + "-" * 70)
    
    # Test 3: Exa Websets Integration
    print("\n3️⃣ EXA WEBSETS INTEGRATION TESTS")
    print("-" * 40)
    try:
        results["exa"] = run_exa_tests()
    except Exception as e:
        print(f"❌ Exa tests crashed: {e}")
        results["exa"] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 INTEGRATION TESTS SUMMARY")
    print("=" * 70)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for service, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{service.upper():15} | {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} integrations passed")
    
    if passed_tests == total_tests:
        print("🎉 All integration tests passed!")
        return True
    else:
        print("⚠️ Some integration tests failed. Check the logs above for details.")
        return False


def run_quick_smoke_tests():
    """Run quick smoke tests to verify basic connectivity."""
    print("💨 Quick Smoke Tests")
    print("=" * 50)
    
    smoke_results = {}
    
    # Quick Firecrawl test
    try:
        from integrations.firecrawl import FirecrawlClient
        client = FirecrawlClient()
        print("✅ Firecrawl client initialization: PASSED")
        smoke_results["firecrawl"] = True
    except Exception as e:
        print(f"❌ Firecrawl client initialization: FAILED ({e})")
        smoke_results["firecrawl"] = False
    
    # Quick HDW test
    try:
        from integrations.hdw import HorizonDataWave
        client = HorizonDataWave(cache_enabled=True)
        print("✅ HDW client initialization: PASSED")
        smoke_results["hdw"] = True
    except Exception as e:
        print(f"❌ HDW client initialization: FAILED ({e})")
        smoke_results["hdw"] = False
    
    # Quick Exa test
    try:
        from integrations.exa_websets import ExaWebsetsAPI, YCFoundersExaExtractor
        api_client = ExaWebsetsAPI()
        extractor = YCFoundersExaExtractor()
        print("✅ Exa clients initialization: PASSED")
        smoke_results["exa"] = True
    except Exception as e:
        print(f"❌ Exa clients initialization: FAILED ({e})")
        smoke_results["exa"] = False
    
    passed = sum(1 for result in smoke_results.values() if result)
    total = len(smoke_results)
    
    print(f"\nSmoke Tests: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run integration tests for external APIs")
    parser.add_argument("--smoke", action="store_true", help="Run quick smoke tests only")
    parser.add_argument("--service", choices=["firecrawl", "hdw", "exa"], help="Run tests for specific service only")
    
    args = parser.parse_args()
    
    if args.smoke:
        success = run_quick_smoke_tests()
    elif args.service:
        # Run specific service test
        if args.service == "firecrawl":
            success = run_firecrawl_tests()
        elif args.service == "hdw":
            success = run_hdw_tests()
        elif args.service == "exa":
            success = run_exa_tests()
    else:
        success = run_all_integration_tests()
    
    sys.exit(0 if success else 1)