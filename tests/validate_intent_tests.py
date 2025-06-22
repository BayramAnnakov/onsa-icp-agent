#!/usr/bin/env python3
"""
Validation script to ensure all intent test modules are properly structured.
"""

import importlib
import sys
from pathlib import Path


def validate_test_modules():
    """Validate that all test modules can be imported and have required functions."""
    
    test_modules = [
        "test_intent_understanding_comprehensive",
        "test_intent_workflow_states", 
        "test_intent_mixed_complex",
        "test_intent_error_recovery",
        "test_intent_conversation_flows"
    ]
    
    data_modules = [
        "intent_test_data"
    ]
    
    print("Validating Intent Test Suite...")
    print("=" * 50)
    
    errors = []
    
    # Check test modules
    for module_name in test_modules:
        try:
            module = importlib.import_module(module_name)
            print(f"✓ {module_name} - imported successfully")
            
            # Check for main test function
            test_func_name = module_name.replace("test_", "")
            if not hasattr(module, test_func_name):
                # Try alternate naming
                if hasattr(module, "test_" + module_name.replace("test_", "")):
                    print(f"  ✓ Found test function")
                else:
                    errors.append(f"{module_name}: Missing main test function")
                    print(f"  ✗ Missing test function: {test_func_name}")
            else:
                print(f"  ✓ Found test function: {test_func_name}")
                
        except ImportError as e:
            errors.append(f"{module_name}: Import error - {str(e)}")
            print(f"✗ {module_name} - IMPORT ERROR: {e}")
    
    # Check data module
    print("\nChecking test data module...")
    try:
        data_module = importlib.import_module("intent_test_data")
        print(f"✓ intent_test_data - imported successfully")
        
        # Check for get_all_test_cases function
        if hasattr(data_module, "get_all_test_cases"):
            test_cases = data_module.get_all_test_cases()
            print(f"  ✓ Found get_all_test_cases() - returns {len(test_cases)} test cases")
            
            # Validate test case structure
            if test_cases:
                sample = test_cases[0]
                required_fields = ["message", "expected", "category"]
                missing_fields = [f for f in required_fields if f not in sample]
                if missing_fields:
                    errors.append(f"Test cases missing fields: {missing_fields}")
                    print(f"  ✗ Test case structure invalid - missing: {missing_fields}")
                else:
                    print(f"  ✓ Test case structure valid")
        else:
            errors.append("intent_test_data: Missing get_all_test_cases function")
            print(f"  ✗ Missing get_all_test_cases function")
            
    except ImportError as e:
        errors.append(f"intent_test_data: Import error - {str(e)}")
        print(f"✗ intent_test_data - IMPORT ERROR: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    if errors:
        print(f"❌ Validation FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"   - {error}")
        return False
    else:
        print("✅ All tests validated successfully!")
        print(f"\nTotal test modules: {len(test_modules)}")
        print(f"Total test cases: {len(test_cases) if 'test_cases' in locals() else 'Unknown'}")
        return True


def check_dependencies():
    """Check if required dependencies are installed."""
    
    print("\nChecking dependencies...")
    print("=" * 50)
    
    required_packages = [
        "pytest",
        "asyncio",
        "structlog",
        "google.adk",
        "models",
        "utils.config"
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            if "." in package:
                # Handle module paths
                parts = package.split(".")
                importlib.import_module(parts[0])
            else:
                importlib.import_module(package)
            print(f"✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"✗ {package} - NOT FOUND")
    
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        print("Some tests may not run properly without these dependencies.")
    else:
        print("\n✅ All dependencies found!")
    
    return len(missing) == 0


if __name__ == "__main__":
    # Add tests directory to path
    sys.path.insert(0, str(Path(__file__).parent))
    
    print("Intent Understanding Test Suite Validator")
    print("=" * 50)
    
    # Validate modules
    modules_valid = validate_test_modules()
    
    # Check dependencies
    deps_valid = check_dependencies()
    
    # Final result
    print("\n" + "=" * 50)
    if modules_valid and deps_valid:
        print("✅ VALIDATION PASSED - Test suite is ready to run!")
        print("\nRun all tests with: python tests/run_all_intent_tests.py")
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED - Please fix the errors above")
        sys.exit(1)