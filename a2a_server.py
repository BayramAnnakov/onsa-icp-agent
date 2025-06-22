"""A2A Protocol Server for Multi-Agent System.

This module implements a FastAPI server that exposes agents via the A2A protocol.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from protocols.a2a_protocol import (
    A2AMessage,
    A2AMessageType,
    A2ATaskRequest,
    A2ATaskResponse,
    A2AAgentInfo,
    create_a2a_message
)
from services.agent_registry import get_agent_registry
from utils.logging_config import get_logger

logger = get_logger(__name__)


# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

# Store task status for async execution
task_status: Dict[str, A2ATaskResponse] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting A2A Protocol Server")
    registry = get_agent_registry()
    await registry.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down A2A Protocol Server")
    await registry.stop()


# Create FastAPI app
app = FastAPI(
    title="A2A Protocol Server",
    description="Agent-to-Agent communication protocol server for ADK multi-agent system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "A2A Protocol Server",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "discovery": "/a2a/discovery",
            "capabilities": "/a2a/capabilities",
            "execute": "/a2a/task",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    registry = get_agent_registry()
    stats = registry.get_registry_stats()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "registry": stats
    }


@app.get("/metrics")
async def get_metrics():
    """Get server metrics."""
    registry = get_agent_registry()
    stats = registry.get_registry_stats()
    
    # Get per-agent metrics
    agent_metrics = {}
    for agent_info in registry.list_agents():
        agent_id = agent_info.agent_id
        metrics = registry.get_agent_metrics(agent_id)
        if metrics:
            agent_metrics[agent_info.name] = metrics
    
    return {
        "overall": stats,
        "agents": agent_metrics,
        "connections": {
            "websocket": len(active_connections)
        }
    }


# A2A Protocol Endpoints

@app.post("/a2a/discovery")
async def discover_agents(
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Discover available agents."""
    registry = get_agent_registry()
    
    # Apply filters if provided
    status = filters.get("status") if filters else None
    capability = filters.get("capability") if filters else None
    
    agents = registry.list_agents(status=status, capability=capability)
    
    return {
        "agents": [agent.dict() for agent in agents],
        "count": len(agents),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/a2a/agents/{agent_id}")
async def get_agent_info(agent_id: str) -> Dict[str, Any]:
    """Get information about a specific agent."""
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Get health and metrics
    health = registry.get_agent_health(agent_id)
    metrics = registry.get_agent_metrics(agent_id)
    
    return {
        "agent": agent.dict(),
        "health": health,
        "metrics": metrics
    }


@app.get("/a2a/capabilities")
async def get_all_capabilities() -> Dict[str, Any]:
    """Get all available capabilities across all agents."""
    registry = get_agent_registry()
    agents = registry.list_agents()
    
    capabilities_map = {}
    for agent in agents:
        for capability in agent.capabilities:
            if capability.name not in capabilities_map:
                capabilities_map[capability.name] = []
            capabilities_map[capability.name].append({
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "description": capability.description,
                "async": capability.async_execution
            })
    
    return {
        "capabilities": capabilities_map,
        "total_capabilities": len(capabilities_map),
        "total_agents": len(agents)
    }


@app.post("/a2a/task")
async def execute_task(request: A2ATaskRequest) -> Dict[str, Any]:
    """Execute a task on any available agent with the capability."""
    registry = get_agent_registry()
    
    # Find agents with the capability
    agents = registry.find_agents_by_capability(request.capability_name)
    if not agents:
        raise HTTPException(
            status_code=404,
            detail=f"No agents found with capability '{request.capability_name}'"
        )
    
    # Select first available healthy agent
    selected_agent = None
    for agent in agents:
        health = registry.get_agent_health(agent.agent_id)
        if health and health["status"] == "healthy":
            selected_agent = agent
            break
    
    if not selected_agent:
        raise HTTPException(
            status_code=503,
            detail="No healthy agents available for this capability"
        )
    
    # Get agent instance
    agent_instance = registry.get_agent_instance(selected_agent.agent_id)
    if not agent_instance:
        raise HTTPException(
            status_code=500,
            detail=f"Agent instance not found for {selected_agent.agent_id}"
        )
    
    # Record start time
    start_time = time.time()
    
    try:
        # Execute via A2A protocol
        if hasattr(agent_instance, 'handle_a2a_request'):
            result = await agent_instance.handle_a2a_request(
                request.capability_name,
                request.parameters
            )
        else:
            # Fallback to direct method call
            method = getattr(agent_instance, request.capability_name, None)
            if not method:
                raise HTTPException(
                    status_code=501,
                    detail=f"Capability '{request.capability_name}' not implemented"
                )
            result = await method(**request.parameters)
        
        # Record metrics
        duration_ms = int((time.time() - start_time) * 1000)
        registry.record_request(selected_agent.agent_id, True, duration_ms)
        
        # Create response
        response = A2ATaskResponse(
            task_id=request.task_id,
            status="completed",
            result=result,
            started_at=datetime.fromtimestamp(start_time),
            completed_at=datetime.utcnow()
        )
        
        return {
            "task": response.dict(),
            "agent": {
                "id": selected_agent.agent_id,
                "name": selected_agent.name
            },
            "duration_ms": duration_ms
        }
        
    except Exception as e:
        # Record failure
        duration_ms = int((time.time() - start_time) * 1000)
        registry.record_request(selected_agent.agent_id, False, duration_ms)
        
        logger.error(f"Task execution failed: {str(e)}")
        
        response = A2ATaskResponse(
            task_id=request.task_id,
            status="failed",
            error=str(e),
            started_at=datetime.fromtimestamp(start_time),
            completed_at=datetime.utcnow()
        )
        
        return {
            "task": response.dict(),
            "agent": {
                "id": selected_agent.agent_id,
                "name": selected_agent.name
            },
            "duration_ms": duration_ms
        }


@app.post("/a2a/agents/{agent_id}/task")
async def execute_agent_task(
    agent_id: str,
    request: A2ATaskRequest
) -> Dict[str, Any]:
    """Execute a task on a specific agent."""
    registry = get_agent_registry()
    
    # Get agent
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Check if agent has the capability
    if not any(cap.name == request.capability_name for cap in agent.capabilities):
        raise HTTPException(
            status_code=400,
            detail=f"Agent does not have capability '{request.capability_name}'"
        )
    
    # Get agent instance
    agent_instance = registry.get_agent_instance(agent_id)
    if not agent_instance:
        raise HTTPException(
            status_code=500,
            detail="Agent instance not available"
        )
    
    # Execute task (similar to above)
    start_time = time.time()
    
    try:
        if hasattr(agent_instance, 'handle_a2a_request'):
            result = await agent_instance.handle_a2a_request(
                request.capability_name,
                request.parameters
            )
        else:
            method = getattr(agent_instance, request.capability_name, None)
            if not method:
                raise HTTPException(
                    status_code=501,
                    detail=f"Capability '{request.capability_name}' not implemented"
                )
            result = await method(**request.parameters)
        
        duration_ms = int((time.time() - start_time) * 1000)
        registry.record_request(agent_id, True, duration_ms)
        
        response = A2ATaskResponse(
            task_id=request.task_id,
            status="completed",
            result=result,
            started_at=datetime.fromtimestamp(start_time),
            completed_at=datetime.utcnow()
        )
        
        return response.dict()
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        registry.record_request(agent_id, False, duration_ms)
        
        logger.error(f"Task execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint for real-time communication
@app.websocket("/a2a/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time A2A communication."""
    await websocket.accept()
    active_connections[client_id] = websocket
    
    logger.info(f"WebSocket connection established: {client_id}")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            message = A2AMessage(**data)
            
            # Process message based on type
            if message.message_type == A2AMessageType.PING:
                # Simple ping/pong
                pong = create_a2a_message(
                    A2AMessageType.PONG,
                    sender_id="a2a-server",
                    recipient_id=client_id,
                    payload={"timestamp": datetime.utcnow().isoformat()}
                )
                await websocket.send_json(pong.dict())
                
            elif message.message_type == A2AMessageType.EXECUTE_TASK:
                # Execute task asynchronously
                task_request = A2ATaskRequest(**message.payload)
                
                # Send acknowledgment
                ack = create_a2a_message(
                    A2AMessageType.TASK_STATUS,
                    sender_id="a2a-server",
                    recipient_id=client_id,
                    correlation_id=message.message_id,
                    payload={
                        "task_id": task_request.task_id,
                        "status": "accepted"
                    }
                )
                await websocket.send_json(ack.dict())
                
                # Execute task in background
                asyncio.create_task(
                    execute_websocket_task(
                        websocket,
                        client_id,
                        message,
                        task_request
                    )
                )
                
            else:
                # Unknown message type
                error = create_a2a_message(
                    A2AMessageType.ERROR,
                    sender_id="a2a-server",
                    recipient_id=client_id,
                    correlation_id=message.message_id,
                    payload={
                        "error": f"Unknown message type: {message.message_type}"
                    }
                )
                await websocket.send_json(error.dict())
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {str(e)}")
    finally:
        if client_id in active_connections:
            del active_connections[client_id]


async def execute_websocket_task(
    websocket: WebSocket,
    client_id: str,
    original_message: A2AMessage,
    task_request: A2ATaskRequest
):
    """Execute a task requested via WebSocket."""
    try:
        # Execute the task
        response = await execute_task(task_request)
        
        # Send response
        task_response = create_a2a_message(
            A2AMessageType.TASK_RESPONSE,
            sender_id="a2a-server",
            recipient_id=client_id,
            correlation_id=original_message.message_id,
            payload=response["task"]
        )
        await websocket.send_json(task_response.dict())
        
    except Exception as e:
        # Send error
        error = create_a2a_message(
            A2AMessageType.ERROR,
            sender_id="a2a-server",
            recipient_id=client_id,
            correlation_id=original_message.message_id,
            payload={
                "task_id": task_request.task_id,
                "error": str(e)
            }
        )
        await websocket.send_json(error.dict())


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the A2A server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()