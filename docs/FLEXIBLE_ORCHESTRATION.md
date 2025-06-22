# Flexible LLM-Driven Orchestration

## Overview

The system now uses flexible, LLM-driven orchestration that allows natural conversation flow instead of rigid workflow steps. This follows Google ADK's best practices for multi-agent systems.

## Key Changes

### 1. Intent-Based Routing

Instead of forcing users through predefined steps, the system now:
- Analyzes each message to understand user intent
- Routes to appropriate handlers based on intent
- Allows jumping between workflow steps
- Supports casual conversation

### 2. Intent Categories

The system recognizes these intent types:

1. **casual_greeting** - "Hi", "Hello", "Hey there"
   - Returns friendly response with suggestions
   - Doesn't force workflow progression

2. **provide_business_info** - Describing business/products
   - Stores information
   - Offers choices for next steps

3. **request_icp_creation** - "Create an ICP"
   - Jumps to ICP creation if info available
   - Asks for info if missing

4. **find_prospects** - "Find prospects/leads"
   - Creates basic ICP if needed
   - Searches for prospects

5. **ask_question** - General questions
   - Answers without forcing workflow

6. **provide_feedback** - Refinement requests
   - Routes to appropriate refinement

7. **navigate_workflow** - "Skip", "Go back", "Start over"
   - Allows workflow navigation

8. **memory_query** - Previous work references
   - Uses memory tools

9. **analyze_resource** - Website/document analysis
   - Analyzes without forcing next step

10. **unclear** - Ambiguous messages
    - Asks for clarification

### 3. Natural Conversation Flow

Example conversation:
```
User: Hey there!
Bot: Hello! How can I help you today? [offers options based on context]

User: What can you do?
Bot: I help businesses find ideal customers... [explains capabilities]

User: I run a SaaS company
Bot: Thanks for sharing! What would you like to do next?
1. Create an ICP
2. Find prospects
3. Analyze a website
[doesn't auto-create ICP]

User: Actually, just find me some prospects
Bot: [Creates basic ICP if needed, then searches]
```

### 4. User Control

Users can now:
- Have casual conversations
- Ask questions without triggering workflows
- Jump to any step ("skip to prospects")
- Go back or start over
- Provide information at their own pace

## Implementation Details

### Intent Analysis

```python
async def _analyze_user_intent(self, message: str, conversation: Conversation, attachments: Optional[List[Dict[str, str]]]) -> Dict[str, Any]:
    """Use LLM to analyze user intent and determine appropriate action."""
```

The LLM considers:
- Message content
- Conversation context
- Current workflow state
- Attachments
- Previous messages

### Flexible Routing

```python
async def _route_message_by_intent(self, conversation: Conversation, message: str, intent: Dict[str, Any], attachments: Optional[List[Dict[str, str]]]) -> str:
    """Route message to appropriate handler based on intent."""
```

Routes to different handlers based on intent type, not workflow step.

### Handler Updates

- **Business Description**: No longer auto-advances to ICP creation
- **Casual Conversation**: New handler for greetings and chat
- **Question Handler**: Answers questions without workflow
- **Navigation Handler**: Allows workflow control

## Benefits

1. **Natural Experience**: Conversations feel more human
2. **User Control**: Users decide when to progress
3. **Flexibility**: Can handle various conversation patterns
4. **Context Awareness**: Understands user needs better
5. **Error Recovery**: Gracefully handles unclear inputs

## Testing

Use `test_flexible_routing.py` to verify:
- Casual greetings don't trigger workflows
- Questions are answered appropriately
- Navigation commands work
- Ambiguous messages get clarification
- Flexible workflow progression

## Migration Notes

If upgrading from rigid workflow:
1. Existing conversations continue to work
2. New conversations use flexible routing
3. Users can "start over" to reset
4. All features remain available

## Future Enhancements

1. **Multi-turn Intent**: Track intent across messages
2. **Proactive Suggestions**: Smarter next-step recommendations
3. **Conversation Styles**: Formal vs casual modes
4. **Custom Intents**: Domain-specific intent categories
5. **Learning**: Improve routing based on usage patterns