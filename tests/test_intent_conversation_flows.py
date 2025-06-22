"""
Test suite for complete conversation flows and multi-turn intent understanding.

Tests full user journeys from start to finish with realistic conversation patterns.
"""

import asyncio
import pytest
from typing import Dict, List, Any, Tuple
from datetime import datetime
import json

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config


class ConversationFlowTester:
    """Tests complete conversation flows."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.test_results = []
    
    async def test_conversation_flow(
        self,
        flow_name: str,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Test a complete conversation flow."""
        
        # Start conversation
        conversation_id = await self.orchestrator.start_conversation(f"flow_test_{flow_name}")
        conversation = self.orchestrator.conversations[conversation_id]
        
        flow_result = {
            "flow_name": flow_name,
            "total_messages": len(messages),
            "message_results": [],
            "workflow_transitions": [],
            "overall_success": True,
            "final_workflow_step": None
        }
        
        previous_step = conversation.current_step
        
        for i, msg_data in enumerate(messages):
            message = msg_data["message"]
            expected_intent = msg_data.get("expected_intent")
            expected_step = msg_data.get("expected_step")
            
            # Analyze intent
            try:
                intent = await self.orchestrator._analyze_user_intent(
                    message,
                    conversation,
                    []
                )
                
                # Process message to advance workflow
                response = await self.orchestrator.process_user_message(
                    conversation_id,
                    message,
                    []
                )
                
                # Check intent match
                intent_match = True
                if expected_intent:
                    intent_match = intent.get("intent_type") == expected_intent
                
                # Check workflow step
                step_match = True
                if expected_step:
                    step_match = conversation.current_step == expected_step
                
                # Record workflow transition
                if conversation.current_step != previous_step:
                    flow_result["workflow_transitions"].append({
                        "from": previous_step.value,
                        "to": conversation.current_step.value,
                        "after_message": i + 1
                    })
                    previous_step = conversation.current_step
                
                message_result = {
                    "message_index": i + 1,
                    "message": message[:100] if len(message) > 100 else message,
                    "detected_intent": intent.get("intent_type"),
                    "expected_intent": expected_intent,
                    "intent_match": intent_match,
                    "confidence": intent.get("confidence", 0),
                    "current_step": conversation.current_step.value,
                    "expected_step": expected_step.value if expected_step else None,
                    "step_match": step_match,
                    "success": intent_match and step_match
                }
                
                if not message_result["success"]:
                    flow_result["overall_success"] = False
                
                flow_result["message_results"].append(message_result)
                
            except Exception as e:
                flow_result["message_results"].append({
                    "message_index": i + 1,
                    "message": message[:100],
                    "error": str(e),
                    "success": False
                })
                flow_result["overall_success"] = False
            
            # Small delay between messages
            await asyncio.sleep(0.2)
        
        flow_result["final_workflow_step"] = conversation.current_step.value
        self.test_results.append(flow_result)
        
        return flow_result


def get_happy_path_flows() -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Get happy path conversation flows."""
    
    return [
        (
            "complete_simple_flow",
            [
                {"message": "Hi", "expected_intent": "casual_greeting", "expected_step": WorkflowStep.BUSINESS_DESCRIPTION},
                {"message": "I run a B2B SaaS company that helps with data analytics", "expected_intent": "provide_business_info", "expected_step": WorkflowStep.BUSINESS_DESCRIPTION},
                {"message": "Create an ICP for me", "expected_intent": "request_icp_creation", "expected_step": WorkflowStep.ICP_CREATION},
                {"message": "Yes, that looks good", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_SEARCH},
                {"message": "These prospects look great", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.FINAL_APPROVAL},
            ]
        ),
        (
            "detailed_business_flow",
            [
                {"message": "Hello, I need help finding customers", "expected_intent": "casual_greeting", "expected_step": WorkflowStep.BUSINESS_DESCRIPTION},
                {"message": "We're TechFlow Inc, check out techflow.com. We provide AI-powered inventory management for retailers", "expected_intent": "provide_business_info", "expected_step": WorkflowStep.BUSINESS_DESCRIPTION},
                {"message": "Our best customers are mid-market retailers with 50-200 stores", "expected_intent": "provide_business_info", "expected_step": WorkflowStep.BUSINESS_DESCRIPTION},
                {"message": "Now create an ideal customer profile", "expected_intent": "request_icp_creation", "expected_step": WorkflowStep.ICP_CREATION},
                {"message": "Perfect, find prospects", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_SEARCH},
                {"message": "I like these, can you find more?", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_REVIEW},
                {"message": "Great work, I'm satisfied", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.FINAL_APPROVAL},
            ]
        ),
        (
            "quick_to_prospects",
            [
                {"message": "I'm the CEO of DataSync, we do B2B integrations, create an ICP and find prospects ASAP", "expected_intent": "provide_business_info", "expected_step": WorkflowStep.ICP_CREATION},
                {"message": "yes proceed", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_SEARCH},
                {"message": "looks good", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.FINAL_APPROVAL},
            ]
        ),
    ]


def get_refinement_flows() -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Get flows with refinements and iterations."""
    
    return [
        (
            "icp_refinement_flow",
            [
                {"message": "hey", "expected_intent": "casual_greeting"},
                {"message": "My company provides HR software", "expected_intent": "provide_business_info"},
                {"message": "create an ICP", "expected_intent": "request_icp_creation"},
                {"message": "Change the company size to enterprises only", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.ICP_REFINEMENT},
                {"message": "Also focus on tech companies", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.ICP_REFINEMENT},
                {"message": "Now it's good, find prospects", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_SEARCH},
            ]
        ),
        (
            "prospect_refinement_flow",
            [
                {"message": "We sell cybersecurity solutions to banks", "expected_intent": "provide_business_info"},
                {"message": "Build an ICP based on that", "expected_intent": "request_icp_creation"},
                {"message": "approved", "expected_intent": "provide_feedback"},
                {"message": "These prospects are too small, find bigger ones", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_REVIEW},
                {"message": "Still not right, focus on investment banks only", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.PROSPECT_REVIEW},
                {"message": "Much better, these work", "expected_intent": "provide_feedback", "expected_step": WorkflowStep.FINAL_APPROVAL},
            ]
        ),
    ]


def get_navigation_flows() -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Get flows with navigation and backtracking."""
    
    return [
        (
            "start_over_flow",
            [
                {"message": "Hi, I need an ICP", "expected_intent": "casual_greeting"},
                {"message": "We make project management software", "expected_intent": "provide_business_info"},
                {"message": "Actually, let me start over", "expected_intent": "navigate_workflow", "expected_step": WorkflowStep.BUSINESS_DESCRIPTION},
                {"message": "We're actually a marketing automation platform", "expected_intent": "provide_business_info"},
                {"message": "Create the ICP now", "expected_intent": "request_icp_creation"},
            ]
        ),
        (
            "skip_ahead_flow",
            [
                {"message": "I already know my ICP, just find prospects", "expected_intent": "find_prospects"},
                {"message": "Mid-market SaaS companies in fintech", "expected_intent": "provide_business_info"},
                {"message": "50-200 employees, series B or later", "expected_intent": "provide_business_info"},
                {"message": "Go ahead and search", "expected_intent": "find_prospects"},
            ]
        ),
    ]


def get_error_recovery_flows() -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Get flows that test error recovery."""
    
    return [
        (
            "unclear_to_clear_flow",
            [
                {"message": "thing", "expected_intent": "unclear"},
                {"message": "sorry, I meant create an ICP", "expected_intent": "request_icp_creation"},
                {"message": "My company is in the IoT space", "expected_intent": "provide_business_info"},
                {"message": "We help manufacturers monitor equipment", "expected_intent": "provide_business_info"},
                {"message": "ok create it", "expected_intent": "request_icp_creation"},
            ]
        ),
        (
            "typo_recovery_flow",
            [
                {"message": "helo", "expected_intent": "casual_greeting"},
                {"message": "i neeed hlp with custmers", "expected_intent": "find_prospects"},
                {"message": "my cmpany is fintech startup", "expected_intent": "provide_business_info"},
                {"message": "creat icp pls", "expected_intent": "request_icp_creation"},
                {"message": "ths looks god", "expected_intent": "provide_feedback"},
            ]
        ),
    ]


def get_mixed_intent_flows() -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Get flows with mixed and complex intents."""
    
    return [
        (
            "question_and_action_flow",
            [
                {"message": "What's an ICP?", "expected_intent": "ask_question"},
                {"message": "OK, create one for my edtech startup", "expected_intent": "request_icp_creation"},
                {"message": "We sell online courses to universities", "expected_intent": "provide_business_info"},
                {"message": "How do you score prospects?", "expected_intent": "ask_question"},
                {"message": "Interesting, please continue", "expected_intent": "unclear"},  # Ambiguous but should continue
                {"message": "The ICP is perfect", "expected_intent": "provide_feedback"},
            ]
        ),
        (
            "memory_and_new_flow",
            [
                {"message": "Do you remember our last conversation?", "expected_intent": "memory_query"},
                {"message": "Let's create a new ICP anyway", "expected_intent": "request_icp_creation"},
                {"message": "This time focus on enterprise clients", "expected_intent": "provide_business_info"},
                {"message": "We're a compliance software company", "expected_intent": "provide_business_info"},
                {"message": "Make the ICP", "expected_intent": "request_icp_creation"},
            ]
        ),
    ]


def get_realistic_conversation_flows() -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Get realistic, natural conversation flows."""
    
    return [
        (
            "natural_sales_conversation",
            [
                {"message": "hey there, I'm looking for some help with lead generation", "expected_intent": "casual_greeting"},
                {"message": "So basically we're a startup in the HR tech space, been around for 2 years", "expected_intent": "provide_business_info"},
                {"message": "We mainly work with growing companies, like 50-500 employees", "expected_intent": "provide_business_info"},
                {"message": "The thing is, we're not sure exactly who our best customers are... can you help?", "expected_intent": "ask_question"},
                {"message": "Yeah, let's create that ICP thing you mentioned", "expected_intent": "request_icp_creation"},
                {"message": "Hmm, I think the company size should be bigger, like 100-1000", "expected_intent": "provide_feedback"},
                {"message": "And add healthcare and finance industries", "expected_intent": "provide_feedback"},
                {"message": "OK that's better, now find me some leads", "expected_intent": "find_prospects"},
                {"message": "These are great! Especially the third one", "expected_intent": "provide_feedback"},
                {"message": "Can you export these for me?", "expected_intent": "ask_question"},
            ]
        ),
        (
            "impatient_user_flow",
            [
                {"message": "I don't have much time, need prospects NOW", "expected_intent": "find_prospects"},
                {"message": "We sell to retailers, that's all you need to know", "expected_intent": "provide_business_info"},
                {"message": "Just make something and find companies", "expected_intent": "request_icp_creation"},
                {"message": "whatever, these are fine", "expected_intent": "provide_feedback"},
                {"message": "good enough", "expected_intent": "provide_feedback"},
            ]
        ),
        (
            "detailed_user_flow",
            [
                {"message": "Good morning! I'd like to explore using your tool for our sales team", "expected_intent": "casual_greeting"},
                {"message": "Let me give you some context about our business first", "expected_intent": "provide_business_info"},
                {"message": "We're called TechVantage Solutions, and we've been in business for 5 years", "expected_intent": "provide_business_info"},
                {"message": "Our main product is an AI-powered supply chain optimization platform", "expected_intent": "provide_business_info"},
                {"message": "We typically work with manufacturing companies and distributors", "expected_intent": "provide_business_info"},
                {"message": "Our sweet spot is companies doing $50M-$500M in revenue", "expected_intent": "provide_business_info"},
                {"message": "Based on all that, could you create an ideal customer profile?", "expected_intent": "request_icp_creation"},
                {"message": "This is excellent! I especially like how you identified the pain points", "expected_intent": "provide_feedback"},
                {"message": "One thing though - can we also include logistics companies?", "expected_intent": "provide_feedback"},
                {"message": "Perfect. Now let's find some actual prospects", "expected_intent": "find_prospects"},
                {"message": "Wow, these look very promising. How confident are you in these scores?", "expected_intent": "ask_question"},
                {"message": "I see. Well, I'm happy with these results!", "expected_intent": "provide_feedback"},
            ]
        ),
    ]


@pytest.mark.asyncio
async def test_conversation_flows():
    """Test complete conversation flows."""
    
    tester = ConversationFlowTester()
    
    # Collect all flows
    all_flows = []
    all_flows.extend([("happy_path", f) for f in get_happy_path_flows()])
    all_flows.extend([("refinement", f) for f in get_refinement_flows()])
    all_flows.extend([("navigation", f) for f in get_navigation_flows()])
    all_flows.extend([("error_recovery", f) for f in get_error_recovery_flows()])
    all_flows.extend([("mixed_intent", f) for f in get_mixed_intent_flows()])
    all_flows.extend([("realistic", f) for f in get_realistic_conversation_flows()])
    
    print("\n=== CONVERSATION FLOW TESTS ===")
    print(f"Testing {len(all_flows)} conversation flows...\n")
    
    results_by_category = {}
    
    for category, (flow_name, messages) in all_flows:
        if category not in results_by_category:
            results_by_category[category] = {"total": 0, "successful": 0, "flows": []}
        
        print(f"\nTesting {category}/{flow_name} ({len(messages)} messages)...")
        
        result = await tester.test_conversation_flow(flow_name, messages)
        
        results_by_category[category]["total"] += 1
        if result["overall_success"]:
            results_by_category[category]["successful"] += 1
        
        results_by_category[category]["flows"].append(result)
        
        # Print summary
        status = "✓" if result["overall_success"] else "✗"
        print(f"{status} {flow_name}: {result['final_workflow_step']}")
        
        # Print message results
        for msg_result in result["message_results"]:
            msg_status = "✓" if msg_result.get("success", False) else "✗"
            print(f"  {msg_status} Msg {msg_result['message_index']}: {msg_result.get('detected_intent', 'error')} "
                  f"(step: {msg_result.get('current_step', 'unknown')})")
            
            if not msg_result.get("success", False):
                if msg_result.get("expected_intent"):
                    print(f"     Expected intent: {msg_result['expected_intent']}")
                if msg_result.get("expected_step"):
                    print(f"     Expected step: {msg_result['expected_step']}")
                if msg_result.get("error"):
                    print(f"     Error: {msg_result['error']}")
        
        # Print workflow transitions
        if result["workflow_transitions"]:
            print(f"  Workflow: {' → '.join([t['from'] for t in result['workflow_transitions']] + [result['final_workflow_step']])}")
    
    # Summary
    print("\n=== FLOW TEST SUMMARY ===")
    
    total_flows = 0
    successful_flows = 0
    
    for category, stats in results_by_category.items():
        total = stats["total"]
        successful = stats["successful"]
        total_flows += total
        successful_flows += successful
        
        accuracy = (successful / total * 100) if total > 0 else 0
        print(f"{category}: {successful}/{total} flows passed ({accuracy:.1f}%)")
        
        # Analyze message-level success
        total_messages = sum(len(f["message_results"]) for f in stats["flows"])
        successful_messages = sum(
            sum(1 for m in f["message_results"] if m.get("success", False))
            for f in stats["flows"]
        )
        msg_accuracy = (successful_messages / total_messages * 100) if total_messages > 0 else 0
        print(f"  Messages: {successful_messages}/{total_messages} ({msg_accuracy:.1f}%)")
    
    overall_accuracy = (successful_flows / total_flows * 100) if total_flows > 0 else 0
    
    print(f"\nOverall: {successful_flows}/{total_flows} flows passed ({overall_accuracy:.1f}%)")
    
    # Save detailed results
    results_data = {
        "test_type": "conversation_flows",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_flows": total_flows,
            "successful_flows": successful_flows,
            "accuracy_percentage": overall_accuracy,
            "by_category": results_by_category
        },
        "flow_results": tester.test_results
    }
    
    filename = f"conversation_flow_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {filename}")
    
    # Assert minimum accuracy
    min_accuracy = 70.0  # Lower threshold for complex flows
    assert overall_accuracy >= min_accuracy, \
        f"Conversation flow accuracy {overall_accuracy:.1f}% below minimum {min_accuracy}%"


if __name__ == "__main__":
    asyncio.run(test_conversation_flows())