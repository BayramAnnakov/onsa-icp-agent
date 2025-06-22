# Exhaustive Intent Understanding Test Suite

This directory contains a comprehensive test suite for testing intent understanding in the multi-agent sales lead generation system. The tests cover every conceivable scenario, edge case, and error condition.

## Test Suite Overview

### 1. **Comprehensive Intent Tests** (`test_intent_understanding_comprehensive.py`)
The foundational test suite that covers all basic intent categories:
- Greetings (with typos, variations, formality levels)
- Business information provision
- ICP creation requests
- Prospect search requests
- Feedback (approval, refinement, rejection)
- Navigation (go back, start over, skip)
- Memory queries
- Questions
- Resource analysis
- And 20+ other categories

**Total test cases: 500+**

### 2. **Workflow State Tests** (`test_intent_workflow_states.py`)
Tests how the same message can have different intents based on workflow state:
- "looks good" → approval in ICP_REFINEMENT, unclear in BUSINESS_DESCRIPTION
- "create an ICP" → different handling based on current step
- Context-dependent interpretation

**Key insight**: Intent detection must consider conversation state

### 3. **Mixed & Complex Intent Tests** (`test_intent_mixed_complex.py`)
Tests for messages containing multiple intents:
- Combined requests ("Hi, I'm John from TechCorp, create an ICP")
- Priority handling (which intent wins)
- Real-world complex messages
- Ambiguous edge cases

**Categories tested**:
- Mixed intents
- Priority conflicts
- Complex real-world patterns
- Truly ambiguous cases

### 4. **Error Recovery Tests** (`test_intent_error_recovery.py`)
Tests system resilience:
- Malformed inputs (empty strings, special characters, extreme lengths)
- LLM failure scenarios (invalid JSON, timeouts)
- Concurrent request handling
- Security attempts (SQL injection, XSS)

**Key tests**:
- Graceful degradation
- Fallback mechanisms
- Error handling
- Performance under stress

### 5. **Conversation Flow Tests** (`test_intent_conversation_flows.py`)
Tests complete multi-turn conversations:
- Happy path flows
- Refinement iterations
- Navigation and backtracking
- Error recovery in context
- Realistic user journeys

**Flow categories**:
- Simple complete flows
- Complex refinement flows
- Natural conversations
- Impatient users
- Detailed users

## Enhanced Test Data (`intent_test_data.py`)

Added 6 new categories of test cases:

### Mobile Typing Errors
- Autocorrect failures: "create and ICP" (and vs an)
- Fat finger errors: "cteate", "fknd"
- Missing spaces: "createanICP"
- Double letters: "creeate", "finnd"

### Voice-to-Text Errors
- Homophones: "I see pea" (ICP)
- Phonetic spelling: "kree ate"
- Filler words: "um", "uh", "like"
- Run-on sentences from speech

### Industry-Specific Language
- Tech: "b2b saas targeting smb with arr >1m"
- Finance: "fintechs with AUM > 100M"
- Healthcare: "HIPAA-compliant telehealth"
- Business abbreviations: "F500", "ESG", "DEI"

### Compound Typos
- Multiple errors: "pls creat an IPC for my compny"
- Typos + grammar: "can u creating icp 4 me"
- Severe corruption: "hlp me mak custmer profle"

### Negation Confusion
- Double negatives: "I don't not want"
- Contradictions: "don't create... yes do it"
- Implicit negation: "doubt this will work but"

### Implicit Intent
- Implied requests: "I need to know who my ideal customers are"
- Indirect phrasing: "help me figure out who to target"
- Context-dependent: "that's not quite right"

## Running the Tests

### Run All Tests
```bash
python tests/run_all_intent_tests.py
```

### Run Individual Test Suites
```bash
# Basic comprehensive tests
python tests/test_intent_understanding_comprehensive.py

# Workflow state tests
python tests/test_intent_workflow_states.py

# Mixed intent tests
python tests/test_intent_mixed_complex.py

# Error recovery tests
python tests/test_intent_error_recovery.py

# Conversation flow tests
python tests/test_intent_conversation_flows.py
```

## Test Metrics

Each test suite tracks:
- **Accuracy**: Percentage of correct intent detections
- **Confidence**: LLM confidence scores
- **Response Time**: Performance metrics
- **Category Breakdown**: Success rates by category
- **Failure Analysis**: Common failure patterns

## Success Criteria

- **Overall Accuracy**: ≥ 80% for basic tests
- **Workflow State Tests**: ≥ 75% (context-dependent)
- **Complex Intent Tests**: ≥ 70% (ambiguous cases)
- **Error Recovery**: ≥ 90% (graceful handling)
- **Conversation Flows**: ≥ 70% (multi-turn complexity)

## Test Results

Results are saved as JSON files with timestamps:
- `intent_test_results_YYYYMMDD_HHMMSS.json`
- `workflow_state_intent_results_*.json`
- `mixed_complex_intent_results_*.json`
- `error_recovery_results_*.json`
- `conversation_flow_results_*.json`
- `intent_test_master_results_*.json` (aggregate)

## Continuous Improvement

1. **Review Failed Cases**: Analyze patterns in failed tests
2. **Update Prompts**: Improve LLM prompts based on failures
3. **Add Edge Cases**: Continuously add new test cases
4. **Monitor Performance**: Track accuracy trends over time

## Key Insights

1. **Context Matters**: Same message, different intents based on state
2. **Graceful Degradation**: System should never crash on bad input
3. **User Intent > Literal Meaning**: "fund prospects" → find prospects
4. **Confidence Thresholds**: Low confidence should trigger clarification
5. **Real Users Are Messy**: Typos, grammar errors, and unclear requests are normal