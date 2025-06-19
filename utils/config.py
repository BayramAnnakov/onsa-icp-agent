"""Configuration management for the multi-agent system."""

import os
import yaml
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pathlib import Path


class GeminiConfig(BaseModel):
    """Gemini LLM configuration."""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 30


class A2AConfig(BaseModel):
    """A2A protocol configuration."""
    port: int = 8080
    host: str = "0.0.0.0"
    protocol_version: str = "1.0"


class AgentConfig(BaseModel):
    """Individual agent configuration."""
    name: str
    description: str
    endpoint: str


class ExternalAPIConfig(BaseModel):
    """External API configuration."""
    base_url: str
    rate_limit: int = 100


class CacheConfig(BaseModel):
    """Cache configuration."""
    directory: str = "./cache"
    ttl: int = 3600
    max_size: str = "1GB"


class ScoringConfig(BaseModel):
    """Scoring configuration."""
    weights: Dict[str, float] = Field(default_factory=dict)
    thresholds: Dict[str, float] = Field(default_factory=dict)


class StorageConfig(BaseModel):
    """Storage configuration."""
    icps_file: str = "./data/icps.json"
    prospects_file: str = "./data/prospects.json"
    conversations_file: str = "./data/conversations.json"


class Config(BaseModel):
    """Main configuration class."""
    
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    a2a: A2AConfig = Field(default_factory=A2AConfig)
    agents: Dict[str, AgentConfig] = Field(default_factory=dict)
    external_apis: Dict[str, ExternalAPIConfig] = Field(default_factory=dict)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    
    @classmethod
    def load_from_file(cls, config_path: str = "config.yaml") -> "Config":
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            # Return default configuration if file doesn't exist
            return cls()
        
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return cls.model_validate(config_data)
    
    def save_to_file(self, config_path: str = "config.yaml") -> None:
        """Save configuration to YAML file."""
        config_data = self.model_dump()
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service from environment variables."""
        key_mapping = {
            "google": "GOOGLE_API_KEY",
            "horizondatawave": "HORIZONDATAWAVE_API_KEY",
            "exa": "EXA_API_KEY",
            "firecrawl": "FIRECRAWL_API_KEY"
        }
        
        env_var = key_mapping.get(service.lower())
        if env_var:
            return os.getenv(env_var)
        
        return None
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent."""
        return self.agents.get(agent_name)
    
    def get_external_api_config(self, api_name: str) -> Optional[ExternalAPIConfig]:
        """Get configuration for an external API."""
        return self.external_apis.get(api_name)
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.cache.directory,
            Path(self.storage.icps_file).parent,
            Path(self.storage.prospects_file).parent,
            Path(self.storage.conversations_file).parent
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)