# A2A Protocol Implementation

## Overview

This document describes the Google A2A (Agent-to-Agent) protocol implementation for the ADK Multi-Agent Sales Lead Generation System. The A2A protocol enables standardized communication between AI agents, allowing external systems to discover and interact with our agents.

## Architecture

### Components

1. **Protocol Layer** (`protocols/a2a_protocol.py`)
   - Message definitions and schemas
   - Protocol handlers
   - Request/response formats

2. **Agent Registry** (`services/agent_registry.py`)
   - Central registry for all agents
   - Health monitoring
   - Metrics collection
   - Agent discovery

3. **A2A Server** (`a2a_server.py`)
   - FastAPI-based REST API
   - WebSocket support
   - Auto-generated OpenAPI documentation

4. **Base Agent Extensions** (`agents/adk_base_agent.py`)
   - A2A protocol support methods
   - Capability exposure
   - Message handling

## API Endpoints

### REST API

#### Discovery
- `POST /a2a/discovery` - Discover available agents
  ```json
  // Request (optional filters)
  {
    "status": "active",
    "capability": "create_icp"
  }
  
  // Response
  {
    "agents": [...],
    "count": 3,
    "timestamp": "2024-01-01T12:00:00Z"
  }
  ```

#### Agent Information
- `GET /a2a/agents/{agent_id}` - Get specific agent info
  ```json
  {
    "agent": {
      "agent_id": "...",
      "name": "ICP Agent",
      "capabilities": [...]
    },
    "health": {
      "status": "healthy",
      "last_check": "..."
    },
    "metrics": {
      "requests": 100,
      "successes": 95,
      "failures": 5
    }
  }
  ```

#### Capabilities
- `GET /a2a/capabilities` - List all available capabilities
  ```json
  {
    "capabilities": {
      "create_icp": [
        {
          "agent_id": "...",
          "agent_name": "ICP Agent",
          "description": "...",
          "async": true
        }
      ]
    },
    "total_capabilities": 25,
    "total_agents": 3
  }
  ```

#### Task Execution
- `POST /a2a/task` - Execute task on any available agent
- `POST /a2a/agents/{agent_id}/task` - Execute task on specific agent
  ```json
  // Request
  {
    "capability_name": "create_icp_from_description",
    "parameters": {
      "business_description": "...",
      "target_market": "..."
    },
    "async_execution": false
  }
  
  // Response
  {
    "task": {
      "task_id": "...",
      "status": "completed",
      "result": {...},
      "started_at": "...",
      "completed_at": "..."
    },
    "agent": {
      "id": "...",
      "name": "ICP Agent"
    },
    "duration_ms": 1234
  }
  ```

#### Health & Metrics
- `GET /health` - Server health check
- `GET /metrics` - Performance metrics

### WebSocket API

Connect to `ws://localhost:8080/a2a/ws/{client_id}` for real-time communication.

Message types:
- `PING`/`PONG` - Connection health check
- `EXECUTE_TASK` - Execute task asynchronously
- `TASK_STATUS` - Task status updates
- `TASK_RESPONSE` - Task completion notification

## Agent Capabilities

### ICP Agent
- `create_icp_from_description` - Create ICP from business description
- `create_icp_from_research` - Create ICP from company research
- `refine_icp` - Refine existing ICP
- `validate_icp` - Validate ICP completeness

### Research Agent
- `analyze_company_comprehensive` - Deep company analysis
- `competitive_analysis` - Analyze competitors
- `industry_research` - Research industry trends
- `website_content_analysis` - Analyze website content
- `linkedin_company_research` - Research LinkedIn presence

### Prospect Agent
- `search_prospects` - Search prospects by ICP
- `search_prospects_by_criteria` - Search by specific criteria
- `score_prospects` - Score prospects against ICP
- `enrich_prospect` - Enrich prospect data

## Usage Examples

### Python Client

```python
from examples.a2a_client_example import A2AClient

async with A2AClient() as client:
    # Discover agents
    agents = await client.discover_agents()
    
    # Execute task
    result = await client.execute_task(
        capability="create_icp_from_description",
        parameters={
            "business_description": "AI-powered sales tool",
            "target_market": "B2B SaaS companies"
        }
    )
```

### cURL Examples

```bash
# Discover agents
curl -X POST http://localhost:8080/a2a/discovery

# Get capabilities
curl http://localhost:8080/a2a/capabilities

# Execute task
curl -X POST http://localhost:8080/a2a/task \
  -H "Content-Type: application/json" \
  -d '{
    "capability_name": "search_prospects_by_criteria",
    "parameters": {
      "industries": ["Software"],
      "company_sizes": ["51-200"],
      "limit": 10
    }
  }'
```

## Running the A2A Server

1. **Set environment variables**:
   ```bash
   export GOOGLE_API_KEY=your_key_here
   export HDW_API_TOKEN=your_token  # Optional
   export EXA_API_KEY=your_key      # Optional
   export FIRECRAWL_API_KEY=your_key # Optional
   ```

2. **Start the server**:
   ```bash
   python start_a2a_server.py
   ```

3. **Access the API**:
   - REST API: `http://localhost:8080`
   - API Documentation: `http://localhost:8080/docs`
   - WebSocket: `ws://localhost:8080/a2a/ws/{client_id}`

## Testing

Run the test suite:
```bash
python test_a2a_protocol.py
```

This will test:
- Agent discovery
- Capability listing
- Task execution
- Health checks
- Performance metrics

## Security Considerations

1. **Authentication**: Currently uses API keys. In production, implement proper OAuth2/JWT authentication.
2. **Rate Limiting**: Add rate limiting to prevent abuse.
3. **Input Validation**: All inputs are validated using Pydantic schemas.
4. **CORS**: Configure CORS appropriately for your deployment.

## Integration with Other Systems

The A2A protocol enables integration with:
- Other A2A-compliant agents
- Workflow orchestration systems
- Agent marketplaces
- Multi-agent collaboration platforms

## Future Enhancements

1. **Authentication & Authorization**: Implement OAuth2 flow
2. **Agent Federation**: Support for discovering agents across networks
3. **Streaming Responses**: Support for streaming task results
4. **Event Subscriptions**: Subscribe to agent events
5. **Agent Composition**: Create composite agents from multiple capabilities