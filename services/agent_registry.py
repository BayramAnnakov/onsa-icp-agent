"""Agent Registry Service for A2A Protocol.

This service manages agent registration, discovery, and health monitoring.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
from collections import defaultdict

from protocols.a2a_protocol import A2AAgentInfo, A2ACapability
from utils.logging_config import get_logger


class AgentRegistryService:
    """Central registry for all A2A-enabled agents."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._agents: Dict[str, A2AAgentInfo] = {}
        self._agent_instances: Dict[str, Any] = {}  # Store actual agent instances
        self._health_status: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "total_duration_ms": 0
        })
        
        # Start health monitoring
        self._health_check_task = None
        
    async def start(self):
        """Start the registry service."""
        self.logger.info("Starting Agent Registry Service")
        self._health_check_task = asyncio.create_task(self._health_monitor())
        
    async def stop(self):
        """Stop the registry service."""
        self.logger.info("Stopping Agent Registry Service")
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
    
    def register_agent(self, agent_info: A2AAgentInfo, agent_instance: Any = None) -> str:
        """Register an agent with the registry.
        
        Args:
            agent_info: A2A agent information
            agent_instance: Optional actual agent instance
            
        Returns:
            Agent ID
        """
        agent_id = agent_info.agent_id
        self._agents[agent_id] = agent_info
        
        if agent_instance:
            self._agent_instances[agent_id] = agent_instance
        
        # Initialize health status
        self._health_status[agent_id] = {
            "status": "healthy",
            "last_check": datetime.utcnow(),
            "consecutive_failures": 0
        }
        
        self.logger.info(f"Registered agent: {agent_info.name} ({agent_id})")
        return agent_id
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent from the registry.
        
        Args:
            agent_id: Agent ID to unregister
            
        Returns:
            True if successful, False if agent not found
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            if agent_id in self._agent_instances:
                del self._agent_instances[agent_id]
            if agent_id in self._health_status:
                del self._health_status[agent_id]
            if agent_id in self._metrics:
                del self._metrics[agent_id]
            
            self.logger.info(f"Unregistered agent: {agent_id}")
            return True
        
        return False
    
    def get_agent(self, agent_id: str) -> Optional[A2AAgentInfo]:
        """Get agent information by ID.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent info or None if not found
        """
        return self._agents.get(agent_id)
    
    def get_agent_instance(self, agent_id: str) -> Optional[Any]:
        """Get actual agent instance by ID.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent instance or None if not found
        """
        return self._agent_instances.get(agent_id)
    
    def list_agents(
        self,
        status: Optional[str] = None,
        capability: Optional[str] = None
    ) -> List[A2AAgentInfo]:
        """List all registered agents with optional filtering.
        
        Args:
            status: Filter by agent status
            capability: Filter by capability name
            
        Returns:
            List of agent information
        """
        agents = list(self._agents.values())
        
        # Filter by status
        if status:
            agents = [
                agent for agent in agents
                if agent.status == status
            ]
        
        # Filter by capability
        if capability:
            agents = [
                agent for agent in agents
                if any(cap.name == capability for cap in agent.capabilities)
            ]
        
        return agents
    
    def find_agents_by_capability(self, capability_name: str) -> List[A2AAgentInfo]:
        """Find all agents that have a specific capability.
        
        Args:
            capability_name: Name of the capability
            
        Returns:
            List of agents with the capability
        """
        return [
            agent for agent in self._agents.values()
            if any(cap.name == capability_name for cap in agent.capabilities)
        ]
    
    def get_agent_health(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get health status for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Health status dictionary or None
        """
        return self._health_status.get(agent_id)
    
    def get_agent_metrics(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get performance metrics for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Metrics dictionary or None
        """
        return dict(self._metrics.get(agent_id, {}))
    
    def record_request(
        self,
        agent_id: str,
        success: bool,
        duration_ms: int
    ):
        """Record a request to an agent for metrics.
        
        Args:
            agent_id: Agent ID
            success: Whether the request was successful
            duration_ms: Request duration in milliseconds
        """
        if agent_id in self._metrics:
            self._metrics[agent_id]["requests"] += 1
            if success:
                self._metrics[agent_id]["successes"] += 1
            else:
                self._metrics[agent_id]["failures"] += 1
            self._metrics[agent_id]["total_duration_ms"] += duration_ms
    
    async def _health_monitor(self):
        """Background task to monitor agent health."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for agent_id, agent_instance in self._agent_instances.items():
                    try:
                        # Check if agent has a health check method
                        if hasattr(agent_instance, 'health_check'):
                            is_healthy = await agent_instance.health_check()
                        else:
                            # Default: consider healthy if instance exists
                            is_healthy = True
                        
                        # Update health status
                        if is_healthy:
                            self._health_status[agent_id]["status"] = "healthy"
                            self._health_status[agent_id]["consecutive_failures"] = 0
                        else:
                            self._health_status[agent_id]["consecutive_failures"] += 1
                            if self._health_status[agent_id]["consecutive_failures"] >= 3:
                                self._health_status[agent_id]["status"] = "unhealthy"
                        
                        self._health_status[agent_id]["last_check"] = datetime.utcnow()
                        
                    except Exception as e:
                        self.logger.error(f"Health check failed for agent {agent_id}: {str(e)}")
                        self._health_status[agent_id]["status"] = "error"
                        self._health_status[agent_id]["consecutive_failures"] += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitor: {str(e)}")
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get overall registry statistics.
        
        Returns:
            Statistics dictionary
        """
        total_requests = sum(m["requests"] for m in self._metrics.values())
        total_successes = sum(m["successes"] for m in self._metrics.values())
        total_failures = sum(m["failures"] for m in self._metrics.values())
        
        healthy_agents = sum(
            1 for status in self._health_status.values()
            if status["status"] == "healthy"
        )
        
        return {
            "total_agents": len(self._agents),
            "healthy_agents": healthy_agents,
            "unhealthy_agents": len(self._agents) - healthy_agents,
            "total_requests": total_requests,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": (total_successes / total_requests * 100) if total_requests > 0 else 0
        }


# Global registry instance
_registry_instance = None


def get_agent_registry() -> AgentRegistryService:
    """Get the global agent registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistryService()
    return _registry_instance