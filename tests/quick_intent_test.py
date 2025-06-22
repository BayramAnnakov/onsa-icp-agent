#!/usr/bin/env python3
"""
Quick intent test to verify the system is working before running full suite.
"""

import asyncio
import json
from datetime import datetime

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config


async def quick_test():
    """Run a quick subset of intent tests."""
    
    print("QUICK INTENT TEST")
    print("=" * 50)
    
    # Initialize
    config = Config.load_from_file()
    orchestrator = ADKAgentOrchestrator(config)
    
    # Test cases
    test_cases = [
        # Basic intents
        {"message": "hi", "expected": "casual_greeting", "category": "greeting"},
        {"message": "create an ICP", "expected": "request_icp_creation", "category": "icp_request"},
        {"message": "find prospects", "expected": "find_prospects", "category": "prospect_search"},
        {"message": "my company is TechCorp", "expected": "provide_business_info", "category": "business_info"},
        
        # Typos
        {"message": "creat an icp", "expected": "request_icp_creation", "category": "typo"},
        {"message": "fnd prospects", "expected": "find_prospects", "category": "typo"},
        
        # Complex
        {"message": "Hi, I'm John from TechCorp, create an ICP", "expected": "request_icp_creation", "category": "mixed"},
        
        # Unclear
        {"message": "thing", "expected": "unclear", "category": "ambiguous"},
    ]
    
    # Setup conversation
    conversation_id = await orchestrator.start_conversation("quick_test_user")
    conversation = orchestrator.conversations[conversation_id]
    
    results = []
    
    print(f"\nRunning {len(test_cases)} quick tests...\n")
    
    for i, test in enumerate(test_cases, 1):
        try:
            # Analyze intent
            intent = await orchestrator._analyze_user_intent(
                test["message"], 
                conversation, 
                []
            )
            
            detected = intent.get("intent_type", "error")
            confidence = intent.get("confidence", 0)
            success = detected == test["expected"]
            
            result = {
                "message": test["message"],
                "expected": test["expected"],
                "detected": detected,
                "confidence": confidence,
                "success": success,
                "category": test["category"]
            }
            
            results.append(result)
            
            # Print result
            status = "✓" if success else "✗"
            print(f"{i}. {status} '{test['message']}' → {detected} ({confidence:.2f})")
            if not success:
                print(f"   Expected: {test['expected']}")
                
        except Exception as e:
            print(f"{i}. ✗ '{test['message']}' → ERROR: {str(e)}")
            results.append({
                "message": test["message"],
                "expected": test["expected"],
                "detected": "error",
                "success": False,
                "error": str(e)
            })
        
        # Small delay
        await asyncio.sleep(0.1)
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    accuracy = (successful / len(results)) * 100
    
    print(f"\n{'=' * 50}")
    print(f"RESULTS: {successful}/{len(results)} passed ({accuracy:.1f}% accuracy)")
    
    # Save results
    results_data = {
        "test_type": "quick_intent_test",
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "successful_tests": successful,
        "accuracy": accuracy,
        "results": results
    }
    
    filename = f"quick_intent_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nResults saved to: {filename}")
    
    return accuracy >= 75  # Success if 75%+ accuracy


if __name__ == "__main__":
    success = asyncio.run(quick_test())
    exit(0 if success else 1)