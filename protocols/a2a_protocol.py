"""A2A Protocol definitions and handlers for the multi-agent system.

This module implements the Google A2A (Agent-to-Agent) protocol for standardized
communication between AI agents.
"""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class A2AMessageType(str, Enum):
    """Types of A2A protocol messages."""
    
    # Discovery messages
    DISCOVER_AGENTS = "discover_agents"
    AGENT_INFO = "agent_info"
    
    # Capability messages
    GET_CAPABILITIES = "get_capabilities"
    CAPABILITIES_RESPONSE = "capabilities_response"
    
    # Task execution messages
    EXECUTE_TASK = "execute_task"
    TASK_RESPONSE = "task_response"
    TASK_STATUS = "task_status"
    
    # Communication messages
    MESSAGE = "message"
    QUERY = "query"
    RESPONSE = "response"
    
    # Control messages
    PING = "ping"
    PONG = "pong"
    ERROR = "error"


class A2ACapability(BaseModel):
    """Represents a single capability of an agent."""
    
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Human-readable description")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for input parameters")
    output_schema: Dict[str, Any] = Field(..., description="JSON schema for output")
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Example inputs/outputs")
    async_execution: bool = Field(False, description="Whether this capability runs asynchronously")
    estimated_duration_ms: Optional[int] = Field(None, description="Estimated execution time in milliseconds")


class A2AAgentInfo(BaseModel):
    """Information about an A2A-compliant agent."""
    
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    capabilities: List[A2ACapability] = Field(..., description="List of agent capabilities")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional agent metadata")
    status: str = Field("active", description="Agent status")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class A2AMessage(BaseModel):
    """Standard A2A protocol message format."""
    
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message_type: A2AMessageType = Field(..., description="Type of message")
    sender_id: str = Field(..., description="ID of sending agent/system")
    recipient_id: Optional[str] = Field(None, description="ID of recipient agent (None for broadcast)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(..., description="Message payload")
    correlation_id: Optional[str] = Field(None, description="ID for correlating request/response")
    requires_response: bool = Field(False, description="Whether a response is expected")
    
    @validator('payload')
    def validate_payload(cls, v, values):
        """Validate payload based on message type."""
        message_type = values.get('message_type')
        
        if message_type == A2AMessageType.EXECUTE_TASK:
            required_fields = ['capability_name', 'parameters']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Missing required field '{field}' for EXECUTE_TASK")
        
        return v


class A2ATaskRequest(BaseModel):
    """Request to execute a task via A2A protocol."""
    
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    capability_name: str = Field(..., description="Name of capability to execute")
    parameters: Dict[str, Any] = Field(..., description="Parameters for the capability")
    async_execution: bool = Field(False, description="Whether to execute asynchronously")
    callback_url: Optional[str] = Field(None, description="URL for async callbacks")
    timeout_ms: Optional[int] = Field(None, description="Timeout in milliseconds")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class A2ATaskResponse(BaseModel):
    """Response from a task execution."""
    
    task_id: str = Field(..., description="ID of the executed task")
    status: str = Field(..., description="Task status: pending, running, completed, failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result (if completed)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    metadata: Optional[Dict[str, Any]] = Field(None)


class A2AProtocolHandler:
    """Handler for A2A protocol messages."""
    
    def __init__(self, agent_info: A2AAgentInfo):
        self.agent_info = agent_info
        self._message_handlers = {
            A2AMessageType.PING: self._handle_ping,
            A2AMessageType.GET_CAPABILITIES: self._handle_get_capabilities,
            A2AMessageType.DISCOVER_AGENTS: self._handle_discover_agents,
        }
    
    async def handle_message(self, message: A2AMessage) -> Optional[A2AMessage]:
        """Handle an incoming A2A message and return a response if needed."""
        
        handler = self._message_handlers.get(message.message_type)
        if handler:
            return await handler(message)
        
        # Default error response for unknown message types
        return self._create_error_response(
            message,
            f"Unknown message type: {message.message_type}"
        )
    
    async def _handle_ping(self, message: A2AMessage) -> A2AMessage:
        """Handle ping message."""
        return A2AMessage(
            message_type=A2AMessageType.PONG,
            sender_id=self.agent_info.agent_id,
            recipient_id=message.sender_id,
            correlation_id=message.message_id,
            payload={
                "agent_id": self.agent_info.agent_id,
                "status": self.agent_info.status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _handle_get_capabilities(self, message: A2AMessage) -> A2AMessage:
        """Handle get capabilities request."""
        capabilities_data = [cap.dict() for cap in self.agent_info.capabilities]
        
        return A2AMessage(
            message_type=A2AMessageType.CAPABILITIES_RESPONSE,
            sender_id=self.agent_info.agent_id,
            recipient_id=message.sender_id,
            correlation_id=message.message_id,
            payload={
                "agent_id": self.agent_info.agent_id,
                "capabilities": capabilities_data,
                "version": self.agent_info.version
            }
        )
    
    async def _handle_discover_agents(self, message: A2AMessage) -> A2AMessage:
        """Handle agent discovery request."""
        return A2AMessage(
            message_type=A2AMessageType.AGENT_INFO,
            sender_id=self.agent_info.agent_id,
            recipient_id=message.sender_id,
            correlation_id=message.message_id,
            payload=self.agent_info.dict()
        )
    
    def _create_error_response(self, original_message: A2AMessage, error_msg: str) -> A2AMessage:
        """Create an error response message."""
        return A2AMessage(
            message_type=A2AMessageType.ERROR,
            sender_id=self.agent_info.agent_id,
            recipient_id=original_message.sender_id,
            correlation_id=original_message.message_id,
            payload={
                "error": error_msg,
                "original_message_type": original_message.message_type.value,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


def create_task_request(
    capability_name: str,
    parameters: Dict[str, Any],
    async_execution: bool = False,
    **kwargs
) -> A2ATaskRequest:
    """Helper function to create a task request."""
    return A2ATaskRequest(
        capability_name=capability_name,
        parameters=parameters,
        async_execution=async_execution,
        **kwargs
    )


def create_a2a_message(
    message_type: A2AMessageType,
    sender_id: str,
    payload: Dict[str, Any],
    recipient_id: Optional[str] = None,
    **kwargs
) -> A2AMessage:
    """Helper function to create an A2A message."""
    return A2AMessage(
        message_type=message_type,
        sender_id=sender_id,
        recipient_id=recipient_id,
        payload=payload,
        **kwargs
    )