"""
Test suite for workflow state-dependent intent understanding.

Tests how the same message can have different intents based on the current workflow step.
"""

import asyncio
import pytest
from typing import Dict, List, Any

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config


class WorkflowStateIntentTester:
    """Tests intent detection across different workflow states."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.test_results = []
    
    async def test_intent_in_state(
        self, 
        message: str, 
        workflow_state: WorkflowStep,
        expected_intent: str,
        test_name: str
    ) -> Dict[str, Any]:
        """Test intent detection in a specific workflow state."""
        
        # Create conversation in specific state
        conversation_id = await self.orchestrator.start_conversation("state_test_user")
        conversation = self.orchestrator.conversations[conversation_id]
        
        # Set up conversation state
        conversation.current_step = workflow_state
        
        # Add context based on state
        if workflow_state in [WorkflowStep.ICP_REFINEMENT, WorkflowStep.PROSPECT_SEARCH]:
            conversation.business_info = {"description": "Test company"}
            conversation.current_icp_id = "test_icp_123"
        
        if workflow_state == WorkflowStep.PROSPECT_REVIEW:
            conversation.current_prospects = ["prospect_1", "prospect_2"]
        
        # Analyze intent
        intent = await self.orchestrator._analyze_user_intent(message, conversation, [])
        
        success = intent.get("intent_type") == expected_intent
        
        result = {
            "test_name": test_name,
            "message": message,
            "workflow_state": workflow_state.value,
            "expected_intent": expected_intent,
            "detected_intent": intent.get("intent_type"),
            "confidence": intent.get("confidence", 0),
            "success": success,
            "reasoning": intent.get("reasoning", "")
        }
        
        self.test_results.append(result)
        return result


def get_workflow_state_test_cases() -> List[Dict[str, Any]]:
    """Get test cases that depend on workflow state."""
    
    return [
        # "looks good" - different meanings in different states
        {
            "message": "looks good",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "unclear",
                WorkflowStep.ICP_REFINEMENT: "provide_feedback",  # Approval
                WorkflowStep.PROSPECT_REVIEW: "provide_feedback",  # Approval
                WorkflowStep.ICP_CREATION: "unclear"
            },
            "test_name": "approval_context_dependent"
        },
        
        # "create an ICP" - different handling based on state
        {
            "message": "create an ICP",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "request_icp_creation",
                WorkflowStep.ICP_CREATION: "request_icp_creation",  # Already creating
                WorkflowStep.ICP_REFINEMENT: "navigate_workflow",  # Want to recreate
                WorkflowStep.PROSPECT_SEARCH: "navigate_workflow"  # Want to go back
            },
            "test_name": "icp_request_state_dependent"
        },
        
        # "find prospects" - depends on having an ICP
        {
            "message": "find prospects",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "find_prospects",  # Will need ICP first
                WorkflowStep.ICP_CREATION: "find_prospects",  # Jump ahead
                WorkflowStep.ICP_REFINEMENT: "find_prospects",  # Natural progression
                WorkflowStep.PROSPECT_SEARCH: "find_prospects",  # Already doing it
                WorkflowStep.PROSPECT_REVIEW: "provide_feedback"  # Want more prospects
            },
            "test_name": "prospect_search_state_dependent"
        },
        
        # "change it" - ambiguous without context
        {
            "message": "change it",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "unclear",
                WorkflowStep.ICP_REFINEMENT: "provide_feedback",  # Change ICP
                WorkflowStep.PROSPECT_REVIEW: "provide_feedback",  # Change prospects
                WorkflowStep.ICP_CREATION: "unclear"
            },
            "test_name": "change_request_ambiguous"
        },
        
        # "no" - rejection means different things
        {
            "message": "no",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "unclear",
                WorkflowStep.ICP_REFINEMENT: "provide_feedback",  # Reject ICP
                WorkflowStep.PROSPECT_REVIEW: "provide_feedback",  # Reject prospects
                WorkflowStep.AUTOMATION_SETUP: "provide_feedback"  # Decline automation
            },
            "test_name": "negative_response_context"
        },
        
        # "start over" - navigation intent
        {
            "message": "start over",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "navigate_workflow",
                WorkflowStep.ICP_CREATION: "navigate_workflow",
                WorkflowStep.PROSPECT_SEARCH: "navigate_workflow",
                WorkflowStep.FINAL_APPROVAL: "navigate_workflow"
            },
            "test_name": "start_over_navigation"
        },
        
        # "yes" - affirmative has many meanings
        {
            "message": "yes",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "unclear",
                WorkflowStep.ICP_REFINEMENT: "provide_feedback",  # Approve ICP
                WorkflowStep.PROSPECT_REVIEW: "provide_feedback",  # Approve prospects
                WorkflowStep.AUTOMATION_SETUP: "provide_feedback"  # Accept automation
            },
            "test_name": "affirmative_response_context"
        },
        
        # "what's next?" - question or navigation
        {
            "message": "what's next?",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "ask_question",
                WorkflowStep.ICP_REFINEMENT: "ask_question",  # Or could be approval
                WorkflowStep.PROSPECT_REVIEW: "ask_question",
                WorkflowStep.FINAL_APPROVAL: "ask_question"
            },
            "test_name": "next_step_question"
        },
        
        # Business info in wrong state
        {
            "message": "my company is Acme Corp",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "provide_business_info",
                WorkflowStep.ICP_CREATION: "provide_business_info",  # Additional info
                WorkflowStep.PROSPECT_SEARCH: "provide_business_info",  # Late addition
                WorkflowStep.PROSPECT_REVIEW: "unclear"  # Too late
            },
            "test_name": "business_info_timing"
        },
        
        # Complex intent in different states
        {
            "message": "this doesn't look right, can we try again?",
            "states": {
                WorkflowStep.BUSINESS_DESCRIPTION: "unclear",
                WorkflowStep.ICP_REFINEMENT: "provide_feedback",  # Negative + retry
                WorkflowStep.PROSPECT_REVIEW: "provide_feedback",  # Want different prospects
                WorkflowStep.ICP_CREATION: "navigate_workflow"  # Start over
            },
            "test_name": "negative_retry_complex"
        }
    ]


@pytest.mark.asyncio
async def test_workflow_state_intents():
    """Test intent detection across workflow states."""
    
    tester = WorkflowStateIntentTester()
    test_cases = get_workflow_state_test_cases()
    
    total_tests = 0
    successful_tests = 0
    
    print("\n=== WORKFLOW STATE INTENT TESTS ===")
    
    for test_case in test_cases:
        message = test_case["message"]
        test_name = test_case["test_name"]
        
        print(f"\nTesting: '{message}' ({test_name})")
        
        for state, expected_intent in test_case["states"].items():
            result = await tester.test_intent_in_state(
                message=message,
                workflow_state=state,
                expected_intent=expected_intent,
                test_name=f"{test_name}_{state.value}"
            )
            
            total_tests += 1
            if result["success"]:
                successful_tests += 1
                status = "✓"
            else:
                status = "✗"
            
            print(f"  {status} {state.value}: Expected '{expected_intent}', Got '{result['detected_intent']}' (confidence: {result['confidence']:.2f})")
            
            if not result["success"]:
                print(f"     Reasoning: {result['reasoning']}")
    
    accuracy = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"\n=== RESULTS ===")
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Accuracy: {accuracy:.1f}%")
    
    # Write detailed results
    import json
    from datetime import datetime
    
    results_data = {
        "test_type": "workflow_state_intents",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "accuracy_percentage": accuracy
        },
        "test_results": tester.test_results
    }
    
    filename = f"workflow_state_intent_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {filename}")
    
    # Assert minimum accuracy
    min_accuracy = 75.0  # Lower threshold for state-dependent tests
    assert accuracy >= min_accuracy, \
        f"Workflow state intent accuracy {accuracy:.1f}% below minimum {min_accuracy}%"


if __name__ == "__main__":
    asyncio.run(test_workflow_state_intents())