#!/usr/bin/env python3
"""
Comprehensive intent test report generator with a focused subset of tests.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any
import time

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config
from tests.intent_test_data import *


async def run_focused_test_suite():
    """Run a focused subset of comprehensive tests."""
    
    print("=" * 80)
    print("COMPREHENSIVE INTENT UNDERSTANDING TEST REPORT")
    print("=" * 80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize
    config = Config.load_from_file()
    orchestrator = ADKAgentOrchestrator(config)
    
    # Get test cases by category
    test_categories = {
        "Greetings": get_greeting_test_cases()[:10],
        "Business Info": get_business_info_test_cases()[:10],
        "ICP Creation": get_icp_creation_test_cases()[:10],
        "Prospect Search": get_prospect_search_test_cases()[:10],
        "Typos": get_typo_test_cases()[:10],
        "Questions": get_question_test_cases()[:10],
        "Navigation": get_navigation_test_cases()[:5],
        "Memory": get_memory_query_test_cases()[:5],
        "Ambiguous": get_ambiguous_intent_test_cases()[:10],
        "Mobile Typing": get_mobile_typing_test_cases()[:10],
        "Voice to Text": get_voice_to_text_test_cases()[:10],
        "Industry Specific": get_industry_specific_test_cases()[:10],
        "Compound Errors": get_compound_typo_test_cases()[:5],
        "Implicit Intent": get_implicit_intent_test_cases()[:10],
    }
    
    # Setup conversation
    conversation_id = await orchestrator.start_conversation("test_user")
    conversation = orchestrator.conversations[conversation_id]
    
    overall_results = {
        "test_metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_categories": len(test_categories),
            "total_tests": sum(len(cases) for cases in test_categories.values())
        },
        "category_results": {},
        "detailed_results": [],
        "error_analysis": {},
        "performance_metrics": {}
    }
    
    total_tests = 0
    total_success = 0
    start_time = time.time()
    
    print(f"Running {overall_results['test_metadata']['total_tests']} tests across {len(test_categories)} categories...\n")
    
    # Run tests by category
    for category_name, test_cases in test_categories.items():
        print(f"\n{'-' * 60}")
        print(f"CATEGORY: {category_name} ({len(test_cases)} tests)")
        print("-" * 60)
        
        category_results = {
            "total": len(test_cases),
            "successful": 0,
            "failed": 0,
            "errors": 0,
            "accuracy": 0,
            "avg_confidence": 0,
            "avg_response_time": 0,
            "failures": []
        }
        
        confidence_scores = []
        response_times = []
        
        for i, test in enumerate(test_cases, 1):
            test_start = time.time()
            
            try:
                # Analyze intent
                intent = await orchestrator._analyze_user_intent(
                    test["message"], 
                    conversation, 
                    []
                )
                
                response_time = time.time() - test_start
                detected = intent.get("intent_type", "error")
                confidence = intent.get("confidence", 0)
                success = detected == test["expected"]
                
                result = {
                    "category": category_name,
                    "message": test["message"],
                    "expected": test["expected"],
                    "detected": detected,
                    "confidence": confidence,
                    "response_time": response_time,
                    "success": success,
                    "reasoning": intent.get("reasoning", ""),
                    "test_category": test.get("category", "unknown")
                }
                
                overall_results["detailed_results"].append(result)
                
                if success:
                    category_results["successful"] += 1
                    total_success += 1
                    status = "✓"
                else:
                    category_results["failed"] += 1
                    category_results["failures"].append({
                        "message": test["message"],
                        "expected": test["expected"],
                        "detected": detected,
                        "confidence": confidence
                    })
                    status = "✗"
                
                confidence_scores.append(confidence)
                response_times.append(response_time)
                
                # Print inline result
                if i <= 5 or not success:  # Show first 5 and all failures
                    print(f"{i}. {status} '{test['message'][:50]}{'...' if len(test['message']) > 50 else ''}' → {detected} ({confidence:.2f})")
                    if not success:
                        print(f"   Expected: {test['expected']}")
                
            except Exception as e:
                category_results["errors"] += 1
                status = "⚠"
                print(f"{i}. {status} '{test['message'][:50]}' → ERROR: {str(e)[:50]}")
                
                overall_results["detailed_results"].append({
                    "category": category_name,
                    "message": test["message"],
                    "error": str(e),
                    "success": False
                })
            
            total_tests += 1
            
            # Brief delay to avoid overwhelming the API
            await asyncio.sleep(0.05)
        
        # Calculate category metrics
        if confidence_scores:
            category_results["avg_confidence"] = sum(confidence_scores) / len(confidence_scores)
        if response_times:
            category_results["avg_response_time"] = sum(response_times) / len(response_times)
        
        category_results["accuracy"] = (category_results["successful"] / category_results["total"] * 100) if category_results["total"] > 0 else 0
        
        overall_results["category_results"][category_name] = category_results
        
        # Print category summary
        print(f"\nCategory Summary: {category_results['successful']}/{category_results['total']} passed ({category_results['accuracy']:.1f}%)")
        if category_results["avg_confidence"] > 0:
            print(f"Avg Confidence: {category_results['avg_confidence']:.3f}")
            print(f"Avg Response Time: {category_results['avg_response_time']:.3f}s")
    
    # Overall metrics
    total_time = time.time() - start_time
    overall_accuracy = (total_success / total_tests * 100) if total_tests > 0 else 0
    
    overall_results["overall_summary"] = {
        "total_tests": total_tests,
        "successful_tests": total_success,
        "failed_tests": total_tests - total_success,
        "accuracy_percentage": overall_accuracy,
        "total_runtime": total_time,
        "avg_test_time": total_time / total_tests if total_tests > 0 else 0
    }
    
    # Analyze error patterns
    error_patterns = {}
    for result in overall_results["detailed_results"]:
        if not result.get("success", True):
            expected = result.get("expected", "unknown")
            detected = result.get("detected", "unknown")
            pattern = f"{expected} → {detected}"
            if pattern not in error_patterns:
                error_patterns[pattern] = 0
            error_patterns[pattern] += 1
    
    overall_results["error_analysis"]["common_misclassifications"] = sorted(
        [(pattern, count) for pattern, count in error_patterns.items()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    # Performance analysis
    all_response_times = [r.get("response_time", 0) for r in overall_results["detailed_results"] if "response_time" in r]
    if all_response_times:
        overall_results["performance_metrics"] = {
            "avg_response_time": sum(all_response_times) / len(all_response_times),
            "min_response_time": min(all_response_times),
            "max_response_time": max(all_response_times),
            "p95_response_time": sorted(all_response_times)[int(len(all_response_times) * 0.95)]
        }
    
    # Print final summary
    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {total_success}")
    print(f"Failed: {total_tests - total_success}")
    print(f"Overall Accuracy: {overall_accuracy:.1f}%")
    print(f"Total Runtime: {total_time:.2f}s")
    print(f"Avg Test Time: {overall_results['overall_summary']['avg_test_time']:.3f}s")
    
    print("\n" + "=" * 80)
    print("CATEGORY BREAKDOWN")
    print("=" * 80)
    print(f"{'Category':<20} {'Accuracy':<10} {'Tests':<10} {'Avg Conf':<10} {'Avg Time':<10}")
    print("-" * 60)
    
    for category, results in overall_results["category_results"].items():
        print(f"{category:<20} {results['accuracy']:>6.1f}% {results['successful']:>3}/{results['total']:<4} "
              f"{results['avg_confidence']:>8.3f} {results['avg_response_time']:>8.3f}s")
    
    # Identify problem areas
    problem_categories = [(cat, res) for cat, res in overall_results["category_results"].items() 
                         if res["accuracy"] < 80]
    
    if problem_categories:
        print("\n" + "=" * 80)
        print("AREAS NEEDING IMPROVEMENT (< 80% accuracy)")
        print("=" * 80)
        for category, results in problem_categories:
            print(f"\n{category}: {results['accuracy']:.1f}% accuracy")
            print("Common failures:")
            for failure in results["failures"][:3]:
                print(f"  - '{failure['message']}' expected '{failure['expected']}' but got '{failure['detected']}'")
    
    # Error pattern analysis
    if overall_results["error_analysis"]["common_misclassifications"]:
        print("\n" + "=" * 80)
        print("COMMON MISCLASSIFICATION PATTERNS")
        print("=" * 80)
        for pattern, count in overall_results["error_analysis"]["common_misclassifications"][:5]:
            print(f"{pattern}: {count} occurrences")
    
    # Save detailed results
    filename = f"comprehensive_intent_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(overall_results, f, indent=2)
    
    print(f"\n\nDetailed results saved to: {filename}")
    
    return overall_results


if __name__ == "__main__":
    results = asyncio.run(run_focused_test_suite())
    
    # Exit with appropriate code
    accuracy = results["overall_summary"]["accuracy_percentage"]
    exit(0 if accuracy >= 75 else 1)