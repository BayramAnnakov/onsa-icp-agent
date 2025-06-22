#!/usr/bin/env python3
"""
Master test runner for all intent understanding tests.

Runs all test suites and generates a comprehensive report.
"""

import asyncio
import sys
import time
from datetime import datetime
import json
from pathlib import Path

# Import all test modules
from test_intent_understanding_comprehensive import test_comprehensive_intent_understanding
from test_intent_workflow_states import test_workflow_state_intents
from test_intent_mixed_complex import test_mixed_complex_intents
from test_intent_error_recovery import test_error_recovery
from test_intent_conversation_flows import test_conversation_flows


async def run_all_tests():
    """Run all intent understanding tests."""
    
    print("=" * 80)
    print("COMPREHENSIVE INTENT UNDERSTANDING TEST SUITE")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Track overall results
    test_results = {
        "start_time": datetime.now().isoformat(),
        "test_suites": [],
        "overall_summary": {}
    }
    
    # Define test suites
    test_suites = [
        {
            "name": "Comprehensive Intent Tests",
            "function": test_comprehensive_intent_understanding,
            "description": "Tests all basic intent categories with typos, errors, and edge cases"
        },
        {
            "name": "Workflow State Tests",
            "function": test_workflow_state_intents,
            "description": "Tests how workflow state affects intent interpretation"
        },
        {
            "name": "Mixed & Complex Intent Tests",
            "function": test_mixed_complex_intents,
            "description": "Tests messages with multiple intents and complex patterns"
        },
        {
            "name": "Error Recovery Tests",
            "function": test_error_recovery,
            "description": "Tests system resilience with malformed inputs and errors"
        },
        {
            "name": "Conversation Flow Tests",
            "function": test_conversation_flows,
            "description": "Tests complete multi-turn conversations"
        }
    ]
    
    # Run each test suite
    for i, suite in enumerate(test_suites, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST SUITE {i}/{len(test_suites)}: {suite['name']}")
        print(f"Description: {suite['description']}")
        print("=" * 80)
        
        suite_start = time.time()
        
        try:
            # Run the test
            await suite["function"]()
            
            suite_time = time.time() - suite_start
            
            # Find the most recent results file
            results_files = list(Path(".").glob(f"*_results_*.json"))
            if results_files:
                latest_file = max(results_files, key=lambda p: p.stat().st_mtime)
                
                # Load results
                with open(latest_file, 'r') as f:
                    suite_results = json.load(f)
                
                test_results["test_suites"].append({
                    "name": suite["name"],
                    "status": "passed",
                    "duration": suite_time,
                    "results_file": str(latest_file),
                    "summary": suite_results.get("summary", {})
                })
                
                print(f"\n✓ {suite['name']} completed in {suite_time:.2f}s")
            else:
                test_results["test_suites"].append({
                    "name": suite["name"],
                    "status": "no_results",
                    "duration": suite_time
                })
                print(f"\n⚠ {suite['name']} completed but no results file found")
                
        except AssertionError as e:
            suite_time = time.time() - suite_start
            test_results["test_suites"].append({
                "name": suite["name"],
                "status": "failed",
                "duration": suite_time,
                "error": str(e)
            })
            print(f"\n✗ {suite['name']} FAILED: {str(e)}")
            
        except Exception as e:
            suite_time = time.time() - suite_start
            test_results["test_suites"].append({
                "name": suite["name"],
                "status": "error",
                "duration": suite_time,
                "error": str(e)
            })
            print(f"\n✗ {suite['name']} ERROR: {str(e)}")
    
    # Calculate overall summary
    total_suites = len(test_suites)
    passed_suites = sum(1 for s in test_results["test_suites"] if s["status"] == "passed")
    failed_suites = sum(1 for s in test_results["test_suites"] if s["status"] in ["failed", "error"])
    
    # Aggregate test counts
    total_tests = 0
    successful_tests = 0
    
    for suite in test_results["test_suites"]:
        if suite["status"] == "passed" and "summary" in suite:
            summary = suite["summary"]
            if "total_tests" in summary:
                total_tests += summary["total_tests"]
                successful_tests += summary.get("successful_tests", 0)
            elif "total_flows" in summary:
                total_tests += summary["total_flows"]
                successful_tests += summary.get("successful_flows", 0)
    
    overall_accuracy = (successful_tests / total_tests * 100) if total_tests > 0 else 0
    
    test_results["overall_summary"] = {
        "total_suites": total_suites,
        "passed_suites": passed_suites,
        "failed_suites": failed_suites,
        "total_individual_tests": total_tests,
        "successful_individual_tests": successful_tests,
        "overall_accuracy": overall_accuracy,
        "total_duration": sum(s["duration"] for s in test_results["test_suites"])
    }
    
    test_results["end_time"] = datetime.now().isoformat()
    
    # Print final summary
    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY")
    print("=" * 80)
    print(f"Test Suites: {passed_suites}/{total_suites} passed")
    print(f"Individual Tests: {successful_tests}/{total_tests} passed ({overall_accuracy:.1f}% accuracy)")
    print(f"Total Duration: {test_results['overall_summary']['total_duration']:.2f}s")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save master results
    master_results_file = f"intent_test_master_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(master_results_file, 'w') as f:
        json.dump(test_results, f, indent=2)
    
    print(f"\nMaster results saved to: {master_results_file}")
    
    # Print recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if overall_accuracy < 80:
        print("⚠️  Overall accuracy is below 80%. Consider:")
        print("   - Reviewing and improving intent detection prompts")
        print("   - Adding more training examples to the LLM prompt")
        print("   - Implementing better fallback mechanisms")
    
    if failed_suites > 0:
        print(f"⚠️  {failed_suites} test suite(s) failed. Review:")
        for suite in test_results["test_suites"]:
            if suite["status"] in ["failed", "error"]:
                print(f"   - {suite['name']}: {suite.get('error', 'Unknown error')}")
    
    # Identify weak areas
    weak_categories = []
    for suite in test_results["test_suites"]:
        if suite["status"] == "passed" and "summary" in suite:
            if "by_category" in suite["summary"]:
                for cat, stats in suite["summary"]["by_category"].items():
                    if isinstance(stats, dict) and "success" in stats and "total" in stats:
                        accuracy = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
                        if accuracy < 70:
                            weak_categories.append((cat, accuracy))
    
    if weak_categories:
        print("\n⚠️  Weak intent categories (< 70% accuracy):")
        for cat, acc in sorted(weak_categories, key=lambda x: x[1]):
            print(f"   - {cat}: {acc:.1f}%")
    
    print("\n" + "=" * 80)
    
    # Return success/failure
    return passed_suites == total_suites and overall_accuracy >= 75


def main():
    """Main entry point."""
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()