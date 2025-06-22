"""
Comprehensive Intent Understanding Test Suite

Tests the LLM-based intent detection system across all edge cases,
user errors, and unprogrammed scenarios.
"""

import asyncio
import pytest
import json
import time
from typing import Dict, List, Any, Tuple
from datetime import datetime
import statistics

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config


class IntentTestResult:
    """Stores results from an intent test."""
    
    def __init__(self, message: str, expected_intent: str, detected_intent: str, 
                 confidence: float, response_time: float, category: str, 
                 success: bool, notes: str = ""):
        self.message = message
        self.expected_intent = expected_intent
        self.detected_intent = detected_intent
        self.confidence = confidence
        self.response_time = response_time
        self.category = category
        self.success = success
        self.notes = notes
        self.timestamp = datetime.now()


class IntentUnderstandingTester:
    """Comprehensive intent understanding test framework."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.test_results: List[IntentTestResult] = []
        self.test_conversation = None
        
    async def setup_test_conversation(self) -> str:
        """Setup a test conversation for intent testing."""
        conversation_id = await self.orchestrator.start_conversation("intent_test_user")
        self.test_conversation = self.orchestrator.conversations[conversation_id]
        return conversation_id
    
    async def test_intent_detection(self, message: str, expected_intent: str, 
                                  category: str, notes: str = "") -> IntentTestResult:
        """Test intent detection for a single message."""
        
        if not self.test_conversation:
            await self.setup_test_conversation()
        
        start_time = time.time()
        
        try:
            # Call the intent analysis directly
            intent_result = await self.orchestrator._analyze_user_intent(
                message, self.test_conversation, []
            )
            
            response_time = time.time() - start_time
            detected_intent = intent_result.get("intent_type", "unknown")
            confidence = intent_result.get("confidence", 0.0)
            
            success = detected_intent == expected_intent
            
        except Exception as e:
            response_time = time.time() - start_time
            detected_intent = "error"
            confidence = 0.0
            success = False
            notes += f" ERROR: {str(e)}"
        
        result = IntentTestResult(
            message=message,
            expected_intent=expected_intent,
            detected_intent=detected_intent,
            confidence=confidence,
            response_time=response_time,
            category=category,
            success=success,
            notes=notes
        )
        
        self.test_results.append(result)
        return result
    
    async def run_test_batch(self, test_cases: List[Dict[str, Any]]) -> List[IntentTestResult]:
        """Run a batch of test cases."""
        
        results = []
        for test_case in test_cases:
            result = await self.test_intent_detection(
                message=test_case["message"],
                expected_intent=test_case["expected"],
                category=test_case["category"],
                notes=test_case.get("notes", "")
            )
            results.append(result)
            
            # Small delay to avoid overwhelming the LLM
            await asyncio.sleep(0.1)
        
        return results
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze test results and provide comprehensive metrics."""
        
        if not self.test_results:
            return {"error": "No test results available"}
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        accuracy = successful_tests / total_tests * 100
        
        # Category-wise analysis
        category_stats = {}
        for result in self.test_results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "success": 0, "avg_confidence": [], "avg_time": []}
            
            category_stats[cat]["total"] += 1
            if result.success:
                category_stats[cat]["success"] += 1
            category_stats[cat]["avg_confidence"].append(result.confidence)
            category_stats[cat]["avg_time"].append(result.response_time)
        
        # Calculate averages
        for cat in category_stats:
            stats = category_stats[cat]
            stats["accuracy"] = (stats["success"] / stats["total"]) * 100
            stats["avg_confidence"] = statistics.mean(stats["avg_confidence"])
            stats["avg_response_time"] = statistics.mean(stats["avg_time"])
        
        # Intent confusion matrix
        intent_matrix = {}
        for result in self.test_results:
            expected = result.expected_intent
            detected = result.detected_intent
            
            if expected not in intent_matrix:
                intent_matrix[expected] = {}
            if detected not in intent_matrix[expected]:
                intent_matrix[expected][detected] = 0
            intent_matrix[expected][detected] += 1
        
        # Confidence distribution
        confidence_ranges = {
            "very_low": [0.0, 0.3],
            "low": [0.3, 0.5],
            "medium": [0.5, 0.7],
            "high": [0.7, 0.9],
            "very_high": [0.9, 1.0]
        }
        
        confidence_distribution = {}
        for range_name, (low, high) in confidence_ranges.items():
            count = sum(1 for r in self.test_results if low <= r.confidence < high)
            confidence_distribution[range_name] = {
                "count": count,
                "percentage": (count / total_tests) * 100
            }
        
        # Failed cases analysis
        failed_cases = [r for r in self.test_results if not r.success]
        failed_by_category = {}
        for result in failed_cases:
            cat = result.category
            if cat not in failed_by_category:
                failed_by_category[cat] = []
            failed_by_category[cat].append({
                "message": result.message,
                "expected": result.expected_intent,
                "detected": result.detected_intent,
                "confidence": result.confidence,
                "notes": result.notes
            })
        
        return {
            "overall_stats": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "accuracy_percentage": accuracy,
                "avg_response_time": statistics.mean([r.response_time for r in self.test_results]),
                "avg_confidence": statistics.mean([r.confidence for r in self.test_results])
            },
            "category_analysis": category_stats,
            "intent_confusion_matrix": intent_matrix,
            "confidence_distribution": confidence_distribution,
            "failed_cases": failed_by_category,
            "test_timestamp": datetime.now().isoformat()
        }
    
    def save_results(self, filename: str = None):
        """Save test results to JSON file."""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"intent_test_results_{timestamp}.json"
        
        analysis = self.analyze_results()
        
        # Add raw results for detailed analysis
        analysis["raw_results"] = [
            {
                "message": r.message,
                "expected_intent": r.expected_intent,
                "detected_intent": r.detected_intent,
                "confidence": r.confidence,
                "response_time": r.response_time,
                "category": r.category,
                "success": r.success,
                "notes": r.notes,
                "timestamp": r.timestamp.isoformat()
            }
            for r in self.test_results
        ]
        
        with open(filename, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"Test results saved to {filename}")
        return filename


# Test cases will be imported from separate data file
from .intent_test_data import get_all_test_cases


@pytest.mark.asyncio
async def test_comprehensive_intent_understanding():
    """Main test function that runs all intent understanding tests."""
    
    tester = IntentUnderstandingTester()
    await tester.setup_test_conversation()
    
    # Get all test cases
    all_test_cases = get_all_test_cases()
    
    print(f"Running {len(all_test_cases)} intent understanding tests...")
    
    # Run all tests
    results = await tester.run_test_batch(all_test_cases)
    
    # Analyze results
    analysis = tester.analyze_results()
    
    # Save detailed results
    results_file = tester.save_results()
    
    # Print summary
    overall = analysis["overall_stats"]
    print(f"\n=== INTENT UNDERSTANDING TEST RESULTS ===")
    print(f"Total Tests: {overall['total_tests']}")
    print(f"Successful: {overall['successful_tests']}")
    print(f"Accuracy: {overall['accuracy_percentage']:.1f}%")
    print(f"Avg Response Time: {overall['avg_response_time']:.3f}s")
    print(f"Avg Confidence: {overall['avg_confidence']:.3f}")
    
    print(f"\n=== CATEGORY BREAKDOWN ===")
    for category, stats in analysis["category_analysis"].items():
        print(f"{category}: {stats['accuracy']:.1f}% ({stats['success']}/{stats['total']})")
    
    # Highlight major failures
    if analysis["failed_cases"]:
        print(f"\n=== FAILED CASES BY CATEGORY ===")
        for category, failures in analysis["failed_cases"].items():
            if failures:
                print(f"\n{category} ({len(failures)} failures):")
                for failure in failures[:3]:  # Show first 3 failures
                    print(f"  '{failure['message']}' -> Expected: {failure['expected']}, Got: {failure['detected']}")
    
    print(f"\nDetailed results saved to: {results_file}")
    
    # Assert minimum accuracy threshold
    min_accuracy = 80.0  # 80% minimum accuracy
    assert overall['accuracy_percentage'] >= min_accuracy, \
        f"Intent understanding accuracy {overall['accuracy_percentage']:.1f}% below minimum {min_accuracy}%"


if __name__ == "__main__":
    async def main():
        await test_comprehensive_intent_understanding()
    
    asyncio.run(main())