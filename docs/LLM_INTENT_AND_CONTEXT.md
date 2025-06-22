# LLM-Based Intent Detection and Context Extraction

## Overview

The system now uses Large Language Models (LLMs) for intelligent intent detection and context extraction, replacing deterministic pattern matching with AI-powered understanding.

## Key Features

### 1. Memory Query Detection

Instead of keyword matching, the system uses LLM to understand if a user is asking about previous work:

```python
async def _is_memory_query(self, message: str) -> bool:
    """Use LLM to intelligently detect if the user is asking about previous work or memory."""
```

**Advantages:**
- Understands context and nuance
- Handles variations in phrasing
- Detects implicit memory references
- Provides confidence scores

**Examples detected as memory queries:**
- "What was my last ICP?" (direct)
- "Continue from where we left off" (continuation)
- "I mentioned my company name earlier" (indirect reference)
- "Let's use the same criteria as before" (partial reference)

**Examples NOT detected as memory queries:**
- "I need an ICP for B2B SaaS" (new request)
- "Help me find prospects" (new task)
- "Forget the past, start fresh" (explicit rejection)

### 2. Context Extraction from Memories

The system intelligently extracts user information from conversation history:

```python
async def _extract_user_context_with_llm(self, memories: List[Any]) -> Dict[str, Any]:
    """Use LLM to intelligently extract user context from memories."""
```

**Extracted Information:**
- User's name
- Company name
- Role/position
- Industry
- Previous ICPs created
- Business context and goals
- Confidence scores for each field

### 3. Personalized Greetings

Based on extracted context, the system generates intelligent greetings:

**Examples:**
- "Welcome back, John! I remember you're the CEO at TechFlow."
- "Welcome back! We previously created an ICP for B2B SaaS companies."
- "Great to see you again! I recall you mentioned: expanding into European markets"

## Implementation Details

### Intent Detection Process

1. **LLM Analysis**: Message is sent to LLM with structured prompt
2. **JSON Response**: LLM returns structured analysis with confidence
3. **Threshold Check**: Only considers memory query if confidence ≥ 0.7
4. **Fallback**: If LLM fails, falls back to simple keyword detection

### Context Extraction Process

1. **Memory Aggregation**: Combines up to 5 most relevant memories
2. **LLM Extraction**: Sends memories to LLM for information extraction
3. **Structured Output**: Returns JSON with all extracted fields
4. **Confidence Tracking**: Each field has associated confidence score

## Testing

### Test Scripts

1. **test_llm_intent_detection.py**: Tests intent detection accuracy
   - Various test cases for memory and non-memory queries
   - Edge cases and ambiguous messages
   - Accuracy reporting

2. **test_memory_query.py**: Tests full memory query workflow
   - End-to-end memory retrieval
   - Context loading at startup

### Expected Behavior

When a user asks about previous work:
1. System detects it's a memory query (via LLM)
2. Routes to ICP agent with memory context
3. Agent uses `load_memory` tool
4. Returns relevant historical information

## Configuration

No special configuration needed. The system automatically:
- Uses available LLM (through research agent)
- Falls back gracefully if LLM is unavailable
- Caches intent detection results when possible

## Best Practices

1. **Prompt Engineering**: The prompts are carefully crafted with examples
2. **Confidence Thresholds**: Set to 0.7 to balance precision/recall
3. **Fallback Mechanisms**: Always have non-LLM fallbacks
4. **Context Limits**: Extract only most relevant information
5. **Privacy**: Don't store sensitive extracted information

## Future Enhancements

1. **Multi-turn Context**: Track context across multiple exchanges
2. **Sentiment Analysis**: Detect user satisfaction/frustration
3. **Language Detection**: Support multiple languages
4. **Custom Entities**: Extract domain-specific information
5. **Active Learning**: Improve detection based on user feedback