"""Multi-agent system for sales lead generation."""

# Original agents (if they exist)
try:
    from .base_agent import BaseAgent
    from .icp_agent import ICPAgent
    from .research_agent import ResearchAgent
    from .prospect_agent import ProspectAgent
except ImportError:
    # Original agents not available
    BaseAgent = None
    ICPAgent = None
    ResearchAgent = None
    ProspectAgent = None

# Google ADK agents
from .adk_base_agent import ADKAgent, AgentMessage, AgentResponse
from .adk_icp_agent import ADKICPAgent
from .adk_research_agent import ADKResearchAgent
from .adk_prospect_agent import ADKProspectAgent

__all__ = [
    # Original agents
    "BaseAgent",
    "ICPAgent", 
    "ResearchAgent",
    "ProspectAgent",
    
    # Google ADK agents
    "ADKAgent",
    "AgentMessage",
    "AgentResponse", 
    "ADKICPAgent",
    "ADKResearchAgent",
    "ADKProspectAgent"
]