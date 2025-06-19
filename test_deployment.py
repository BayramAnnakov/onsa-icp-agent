#!/usr/bin/env python3
"""
Test script to validate deployment readiness.
"""

import os
import sys
from pathlib import Path

def test_file_structure():
    """Test that all required files exist."""
    required_files = [
        "main.py",
        "requirements.txt", 
        "Dockerfile",
        ".dockerignore",
        "deploy-cloud-run.sh",
        "service.yaml",
        "adk_main.py",
        "web_interface.py",
        "setup_logging.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

def test_directory_structure():
    """Test that all required directories exist."""
    required_dirs = [
        "agents",
        "integrations",
        "models", 
        "utils",
        "cache",
        "logs",
        "sessions"
    ]
    
    missing_dirs = []
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"❌ Missing directories: {missing_dirs}")
        return False
    else:
        print("✅ All required directories present")
        return True

def test_environment_vars():
    """Test environment variable configuration."""
    required_vars = ["GOOGLE_API_KEY"]
    optional_vars = ["HDW_API_TOKEN", "EXA_API_KEY", "FIRECRAWL_API_KEY"]
    
    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
    
    missing_optional = []
    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)
    
    if missing_required:
        print(f"⚠️  Missing required environment variables: {missing_required}")
        print("   Set these before deployment for full functionality")
    else:
        print("✅ Required environment variables configured")
    
    if missing_optional:
        print(f"ℹ️  Optional environment variables not set: {missing_optional}")
        print("   System will work with limited functionality")
    
    return len(missing_required) == 0

def test_imports():
    """Test that main modules can be imported."""
    try:
        # Test configuration
        sys.path.insert(0, str(Path(__file__).parent))
        from utils.config import Config
        print("✅ Configuration module imports successfully")
        
        # Test ADK main  
        from adk_main import ADKAgentOrchestrator
        print("✅ ADK orchestrator imports successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Install dependencies: pip install -r requirements.txt")
        return False

def test_deployment_readiness():
    """Run all deployment readiness tests."""
    print("🔍 Testing deployment readiness for ADK Sales System")
    print("=" * 50)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Directory Structure", test_directory_structure), 
        ("Environment Variables", test_environment_vars),
        ("Module Imports", test_imports)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 50)
    if all(results):
        print("🎉 All tests passed! Ready for Cloud Run deployment")
        print("\nNext steps:")
        print("1. Set PROJECT_ID: export PROJECT_ID='your-gcp-project-id'")
        print("2. Run deployment: ./deploy-cloud-run.sh")
        return True
    else:
        print("❌ Some tests failed. Fix issues before deploying")
        return False

if __name__ == "__main__":
    success = test_deployment_readiness()
    sys.exit(0 if success else 1)