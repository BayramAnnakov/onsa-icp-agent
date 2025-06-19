"""Conversation and session management models."""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    AGENT = "agent"


class ConversationMessage(BaseModel):
    """Individual message in a conversation."""
    
    id: str = Field(..., description="Unique message identifier")
    role: MessageRole = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Agent-specific fields
    agent_name: Optional[str] = Field(None, description="Name of the agent if role is 'agent'")
    agent_action: Optional[str] = Field(None, description="Action performed by agent")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    
    # File attachments or links
    attachments: List[Dict[str, str]] = Field(
        default_factory=list,
        description="File attachments or links referenced in message"
    )


class WorkflowStep(str, Enum):
    """Steps in the lead generation workflow."""
    BUSINESS_DESCRIPTION = "business_description"
    ICP_CREATION = "icp_creation"
    ICP_REFINEMENT = "icp_refinement"
    PROSPECT_SEARCH = "prospect_search"
    PROSPECT_REVIEW = "prospect_review"
    FINAL_APPROVAL = "final_approval"
    AUTOMATION_SETUP = "automation_setup"
    COMPLETED = "completed"


class Conversation(BaseModel):
    """Complete conversation session model."""
    
    id: str = Field(..., description="Unique conversation identifier")
    user_id: str = Field(..., description="User identifier")
    
    # Conversation metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active", description="Conversation status")
    
    # Workflow tracking
    current_step: WorkflowStep = Field(default=WorkflowStep.BUSINESS_DESCRIPTION)
    completed_steps: List[WorkflowStep] = Field(default_factory=list)
    
    # Messages
    messages: List[ConversationMessage] = Field(
        default_factory=list,
        description="All messages in the conversation"
    )
    
    # Business information collected
    business_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Business information provided by user"
    )
    
    # Source materials
    source_materials: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Links, documents, and other source materials"
    )
    
    # Current ICP being developed
    current_icp_id: Optional[str] = Field(None, description="ID of current ICP being worked on")
    icp_versions: List[str] = Field(default_factory=list, description="History of ICP versions")
    
    # Prospect search results
    current_prospects: List[str] = Field(
        default_factory=list,
        description="IDs of current prospect candidates"
    )
    approved_prospects: List[str] = Field(
        default_factory=list,
        description="IDs of user-approved prospects"
    )
    
    # User preferences and feedback
    user_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences and settings"
    )
    
    # Automation settings
    automation_enabled: bool = Field(default=False)
    automation_frequency: Optional[str] = Field(None, description="How often to run automated searches")
    notification_preferences: Dict[str, bool] = Field(
        default_factory=dict,
        description="User notification preferences"
    )
    
    def add_message(
        self, 
        role: MessageRole, 
        content: str, 
        agent_name: Optional[str] = None,
        agent_action: Optional[str] = None,
        attachments: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Add a new message to the conversation."""
        message_id = f"msg_{len(self.messages) + 1}_{int(datetime.now().timestamp())}"
        
        message = ConversationMessage(
            id=message_id,
            role=role,
            content=content,
            agent_name=agent_name,
            agent_action=agent_action,
            attachments=attachments or []
        )
        
        self.messages.append(message)
        self.updated_at = datetime.now()
        
        return message_id
    
    def advance_step(self, next_step: WorkflowStep) -> None:
        """Advance to the next workflow step."""
        if self.current_step not in self.completed_steps:
            self.completed_steps.append(self.current_step)
        
        self.current_step = next_step
        self.updated_at = datetime.now()
    
    def get_latest_messages(self, count: int = 10) -> List[ConversationMessage]:
        """Get the latest N messages."""
        return self.messages[-count:] if len(self.messages) >= count else self.messages
    
    def get_messages_by_role(self, role: MessageRole) -> List[ConversationMessage]:
        """Get all messages from a specific role."""
        return [msg for msg in self.messages if msg.role == role]
    
    def get_conversation_summary(self) -> str:
        """Generate a summary of the conversation."""
        return f"Conversation {self.id} - Step: {self.current_step.value} - Messages: {len(self.messages)}"
    
    def is_step_completed(self, step: WorkflowStep) -> bool:
        """Check if a workflow step has been completed."""
        return step in self.completed_steps
    
    def add_source_material(self, material_type: str, url: str, description: str = "") -> None:
        """Add source material to the conversation."""
        self.source_materials.append({
            "type": material_type,
            "url": url,
            "description": description,
            "added_at": datetime.now().isoformat()
        })
        self.updated_at = datetime.now()