"""
Test suite for mixed and complex intent scenarios.

Tests messages that contain multiple intents, priority handling, and complex real-world patterns.
"""

import asyncio
import pytest
from typing import Dict, List, Any, Tuple

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config


def get_mixed_intent_test_cases() -> List[Dict[str, Any]]:
    """Test cases with multiple intents in one message."""
    
    return [
        # Greeting + Business Info + ICP Request
        {
            "message": "Hi, I'm John from TechCorp, we make B2B software, can you create an ICP for us?",
            "primary_intent": "request_icp_creation",
            "secondary_intents": ["casual_greeting", "provide_business_info"],
            "category": "greeting_business_icp",
            "notes": "Should prioritize ICP creation request"
        },
        
        # Business Info + ICP + Prospects
        {
            "message": "My company sells AI tools to enterprises, create an ICP and find me some prospects",
            "primary_intent": "provide_business_info",  # First action needed
            "secondary_intents": ["request_icp_creation", "find_prospects"],
            "category": "full_workflow_request",
            "notes": "Should handle sequential workflow"
        },
        
        # Question + Request
        {
            "message": "What's an ICP? Can you make one for my SaaS startup?",
            "primary_intent": "ask_question",  # Question should be answered first
            "secondary_intents": ["request_icp_creation"],
            "category": "question_then_request",
            "notes": "Should answer then offer to create"
        },
        
        # Feedback + Navigation
        {
            "message": "This ICP doesn't look right, let's start over from the beginning",
            "primary_intent": "provide_feedback",
            "secondary_intents": ["navigate_workflow"],
            "category": "negative_feedback_restart",
            "notes": "Negative feedback with navigation request"
        },
        
        # Memory Query + Current Request
        {
            "message": "What was my last ICP? Actually, let's create a new one",
            "primary_intent": "memory_query",
            "secondary_intents": ["request_icp_creation"],
            "category": "memory_then_new",
            "notes": "Memory query followed by new request"
        },
        
        # Approval + Next Step
        {
            "message": "Yes, this ICP looks perfect! Now find me prospects",
            "primary_intent": "provide_feedback",  # Approval
            "secondary_intents": ["find_prospects"],
            "category": "approval_next_action",
            "notes": "Approval should trigger next step"
        },
        
        # Complex Business Description + Multiple Requests
        {
            "message": "We're Acme Corp, check out acme.com, we need enterprise customers in fintech, create an ICP focusing on CFOs and find at least 50 prospects",
            "primary_intent": "provide_business_info",
            "secondary_intents": ["analyze_resource", "request_icp_creation", "find_prospects"],
            "category": "complex_multi_request",
            "notes": "Multiple actions with specific requirements"
        },
        
        # Correction + Continuation
        {
            "message": "Sorry, I meant B2C not B2B, but yes continue with the ICP creation",
            "primary_intent": "provide_feedback",  # Correction
            "secondary_intents": ["request_icp_creation"],
            "category": "correction_continuation",
            "notes": "Error correction with continuation"
        },
        
        # Conditional Request
        {
            "message": "If you can analyze websites, check example.com, otherwise just create an ICP based on what I told you",
            "primary_intent": "analyze_resource",
            "secondary_intents": ["request_icp_creation"],
            "category": "conditional_request",
            "notes": "Conditional logic in request"
        },
        
        # Frustrated + Request
        {
            "message": "This is taking too long! Just find me any B2B software companies NOW",
            "primary_intent": "find_prospects",
            "secondary_intents": ["provide_feedback"],  # Frustration
            "category": "emotional_request",
            "notes": "Emotional state with clear request"
        }
    ]


def get_priority_conflict_test_cases() -> List[Dict[str, Any]]:
    """Test cases where intent priority matters."""
    
    return [
        # ICP creation should override business info when explicit
        {
            "message": "I run a tech company, create an ICP",
            "expected_intent": "request_icp_creation",
            "conflicting_intent": "provide_business_info",
            "category": "explicit_override"
        },
        
        # Navigation should override other intents
        {
            "message": "Actually, let me start over and tell you about my business differently",
            "expected_intent": "navigate_workflow",
            "conflicting_intent": "provide_business_info",
            "category": "navigation_priority"
        },
        
        # Memory query with embedded info
        {
            "message": "Show me the ICP we created for my company TechFlow last week",
            "expected_intent": "memory_query",
            "conflicting_intent": "provide_business_info",
            "category": "memory_priority"
        },
        
        # Question should be answered even with embedded request
        {
            "message": "I don't understand what an ICP is, but create one anyway",
            "expected_intent": "ask_question",
            "conflicting_intent": "request_icp_creation",
            "category": "question_first"
        }
    ]


def get_complex_real_world_test_cases() -> List[Dict[str, Any]]:
    """Complex real-world message patterns."""
    
    return [
        # Stream of consciousness
        {
            "message": "ok so basically we're like uber but for B2B services and we mainly work with companies that have between 50-500 employees but honestly we're open to bigger ones too if they're a good fit and we really need to find decision makers who understand digital transformation because that's our main value prop oh and can you look at our competitors too?",
            "expected_intent": "provide_business_info",
            "confidence_min": 0.6,
            "category": "stream_of_consciousness"
        },
        
        # Multiple questions and requests
        {
            "message": "How accurate is your data? Do you have access to recent information? Anyway, I need an ICP for fintech companies, specifically ones using AI, and then find me their CTOs or heads of engineering, but only if they're actively hiring",
            "expected_intent": "ask_question",  # Questions come first
            "confidence_min": 0.5,
            "category": "questions_then_requests"
        },
        
        # Conversational with embedded intent
        {
            "message": "You know what, I've been thinking about this all wrong. Instead of targeting small businesses, let's focus on mid-market companies. Can you redo the ICP with that in mind? I think 200-1000 employees would be the sweet spot",
            "expected_intent": "provide_feedback",
            "confidence_min": 0.7,
            "category": "conversational_refinement"
        },
        
        # Technical jargon mixed with request
        {
            "message": "Our ICP should focus on companies with high NPS, low CAC, strong product-market fit, preferably Series B or later, ARR of $5M+, and make sure they use modern tech stack - create this and find prospects ASAP",
            "expected_intent": "request_icp_creation",
            "confidence_min": 0.8,
            "category": "technical_specifications"
        },
        
        # Interrupted thought with multiple pivots
        {
            "message": "So we need... wait, first tell me, can you search LinkedIn? Actually, nevermind, just create an ICP for... hmm, let me think... ok, enterprise software companies, but not too big, maybe Fortune 1000?",
            "expected_intent": "request_icp_creation",
            "confidence_min": 0.5,
            "category": "interrupted_pivoting"
        },
        
        # Polite but complex request
        {
            "message": "Good morning! I hope you're doing well. I was wondering if you could help me with something. My company, DataFlow Analytics, provides business intelligence solutions, and we're looking to expand our customer base. Could you possibly create a detailed ICP and, if it's not too much trouble, find some prospects? We're particularly interested in retail and e-commerce companies. Thank you so much!",
            "expected_intent": "request_icp_creation",
            "confidence_min": 0.8,
            "category": "polite_complex"
        },
        
        # Negative start but positive intent
        {
            "message": "I'm not sure this will work, but let's try anyway. Create an ICP for companies that actually need our product - you know, the ones struggling with data integration",
            "expected_intent": "request_icp_creation",
            "confidence_min": 0.7,
            "category": "skeptical_request"
        },
        
        # Reference to external context
        {
            "message": "Like we discussed in our meeting (not with you, with my team), we need to target healthtech companies, so build an ICP around that and include telemedicine providers",
            "expected_intent": "request_icp_creation",
            "confidence_min": 0.8,
            "category": "external_reference"
        }
    ]


def get_ambiguous_edge_cases() -> List[Dict[str, Any]]:
    """Truly ambiguous cases that test fallback handling."""
    
    return [
        # Could be many things
        {
            "message": "not really",
            "expected_intent": "unclear",
            "possible_intents": ["provide_feedback", "casual_greeting", "navigate_workflow"],
            "category": "highly_ambiguous"
        },
        
        # Depends entirely on context
        {
            "message": "the first one",
            "expected_intent": "unclear",
            "possible_intents": ["provide_feedback", "navigate_workflow"],
            "category": "context_dependent"
        },
        
        # Multiple negations
        {
            "message": "no wait yes actually no",
            "expected_intent": "unclear",
            "possible_intents": ["provide_feedback", "navigate_workflow"],
            "category": "contradictory"
        },
        
        # Just an emoji
        {
            "message": "👍",
            "expected_intent": "unclear",
            "possible_intents": ["provide_feedback", "casual_greeting"],
            "category": "emoji_only"
        },
        
        # Incomplete fragment
        {
            "message": "because the",
            "expected_intent": "unclear",
            "possible_intents": [],
            "category": "incomplete_fragment"
        }
    ]


class MixedIntentTester:
    """Tests complex and mixed intent scenarios."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.test_results = []
    
    async def test_mixed_intent(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test a mixed intent scenario."""
        
        # Create conversation
        conversation_id = await self.orchestrator.start_conversation("mixed_intent_test")
        conversation = self.orchestrator.conversations[conversation_id]
        
        # Analyze intent
        intent = await self.orchestrator._analyze_user_intent(
            test_case["message"], 
            conversation, 
            []
        )
        
        # Determine success based on test type
        if "expected_intent" in test_case:
            success = intent.get("intent_type") == test_case["expected_intent"]
        elif "primary_intent" in test_case:
            success = intent.get("intent_type") == test_case["primary_intent"]
        else:
            success = intent.get("intent_type") != "unclear"
        
        # Check confidence if specified
        if "confidence_min" in test_case:
            confidence_ok = intent.get("confidence", 0) >= test_case["confidence_min"]
            success = success and confidence_ok
        
        result = {
            "message": test_case["message"],
            "category": test_case.get("category", "unknown"),
            "detected_intent": intent.get("intent_type"),
            "confidence": intent.get("confidence", 0),
            "reasoning": intent.get("reasoning", ""),
            "success": success,
            "notes": test_case.get("notes", "")
        }
        
        if "expected_intent" in test_case:
            result["expected_intent"] = test_case["expected_intent"]
        if "primary_intent" in test_case:
            result["primary_intent"] = test_case["primary_intent"]
            result["secondary_intents"] = test_case.get("secondary_intents", [])
        
        self.test_results.append(result)
        return result


@pytest.mark.asyncio
async def test_mixed_complex_intents():
    """Test mixed and complex intent scenarios."""
    
    tester = MixedIntentTester()
    
    # Get all test cases
    all_tests = []
    all_tests.extend([{"type": "mixed", **tc} for tc in get_mixed_intent_test_cases()])
    all_tests.extend([{"type": "priority", **tc} for tc in get_priority_conflict_test_cases()])
    all_tests.extend([{"type": "complex", **tc} for tc in get_complex_real_world_test_cases()])
    all_tests.extend([{"type": "ambiguous", **tc} for tc in get_ambiguous_edge_cases()])
    
    print(f"\n=== MIXED & COMPLEX INTENT TESTS ===")
    print(f"Running {len(all_tests)} test cases...\n")
    
    # Run tests by type
    results_by_type = {}
    
    for test_case in all_tests:
        test_type = test_case["type"]
        if test_type not in results_by_type:
            results_by_type[test_type] = {"total": 0, "successful": 0}
        
        result = await tester.test_mixed_intent(test_case)
        
        results_by_type[test_type]["total"] += 1
        if result["success"]:
            results_by_type[test_type]["successful"] += 1
        
        # Print result
        status = "✓" if result["success"] else "✗"
        print(f"{status} [{test_type}] {test_case.get('category', 'unknown')}")
        if len(result["message"]) < 100:
            print(f"   Message: \"{result['message']}\"")
        else:
            print(f"   Message: \"{result['message'][:97]}...\"")
        print(f"   Detected: {result['detected_intent']} (confidence: {result['confidence']:.2f})")
        
        if not result["success"]:
            if "expected_intent" in result:
                print(f"   Expected: {result['expected_intent']}")
            elif "primary_intent" in result:
                print(f"   Expected primary: {result['primary_intent']}")
            print(f"   Reasoning: {result['reasoning']}")
        
        print()
        
        # Small delay
        await asyncio.sleep(0.1)
    
    # Summary
    print("\n=== RESULTS BY TYPE ===")
    total_all = 0
    successful_all = 0
    
    for test_type, stats in results_by_type.items():
        total = stats["total"]
        successful = stats["successful"]
        accuracy = (successful / total * 100) if total > 0 else 0
        
        total_all += total
        successful_all += successful
        
        print(f"{test_type}: {successful}/{total} ({accuracy:.1f}%)")
    
    overall_accuracy = (successful_all / total_all * 100) if total_all > 0 else 0
    
    print(f"\n=== OVERALL RESULTS ===")
    print(f"Total Tests: {total_all}")
    print(f"Successful: {successful_all}")
    print(f"Accuracy: {overall_accuracy:.1f}%")
    
    # Save detailed results
    import json
    from datetime import datetime
    
    results_data = {
        "test_type": "mixed_complex_intents",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_all,
            "successful_tests": successful_all,
            "accuracy_percentage": overall_accuracy,
            "by_type": results_by_type
        },
        "test_results": tester.test_results
    }
    
    filename = f"mixed_complex_intent_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {filename}")
    
    # Assert minimum accuracy (lower for complex cases)
    min_accuracy = 70.0
    assert overall_accuracy >= min_accuracy, \
        f"Mixed intent accuracy {overall_accuracy:.1f}% below minimum {min_accuracy}%"


if __name__ == "__main__":
    asyncio.run(test_mixed_complex_intents())