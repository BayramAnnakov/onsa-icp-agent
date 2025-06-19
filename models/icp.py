"""Ideal Customer Profile data models."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ICPCriteria(BaseModel):
    """Individual criteria for the ICP."""
    
    name: str = Field(..., description="Name of the criteria")
    description: str = Field(..., description="Detailed description of the criteria")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Weight of this criteria in scoring")
    required: bool = Field(default=False, description="Whether this criteria is mandatory")
    values: List[str] = Field(default_factory=list, description="Possible values for this criteria")


class ICP(BaseModel):
    """Ideal Customer Profile model."""
    
    id: str = Field(..., description="Unique identifier for the ICP")
    name: str = Field(..., description="Name of the ICP")
    description: str = Field(..., description="Overall description of the ideal customer")
    
    # Company characteristics
    company_criteria: Dict[str, ICPCriteria] = Field(
        default_factory=dict,
        description="Company-level criteria"
    )
    
    # Person characteristics  
    person_criteria: Dict[str, ICPCriteria] = Field(
        default_factory=dict,
        description="Person-level criteria"
    )
    
    # Industry and market
    industries: List[str] = Field(default_factory=list, description="Target industries")
    company_size: Dict[str, Any] = Field(
        default_factory=dict,
        description="Company size criteria (employees, revenue, etc.)"
    )
    geographic_regions: List[str] = Field(
        default_factory=list,
        description="Target geographic regions"
    )
    
    # Role and seniority
    target_roles: List[str] = Field(default_factory=list, description="Target job roles")
    seniority_levels: List[str] = Field(default_factory=list, description="Target seniority levels")
    departments: List[str] = Field(default_factory=list, description="Target departments")
    
    # Technology and tools
    tech_stack: List[str] = Field(default_factory=list, description="Technologies used by target companies")
    tools_used: List[str] = Field(default_factory=list, description="Tools used by target personas")
    
    # Behavioral characteristics
    pain_points: List[str] = Field(default_factory=list, description="Common pain points")
    goals: List[str] = Field(default_factory=list, description="Common goals and objectives")
    buying_signals: List[str] = Field(default_factory=list, description="Signals indicating buying intent")
    
    # Exclusion criteria
    exclusions: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Criteria to exclude prospects"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: int = Field(default=1, description="Version number for tracking changes")
    
    # User feedback and refinements
    feedback_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of user feedback and refinements"
    )
    
    # Source information
    source_materials: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Source materials used to create this ICP"
    )
    
    def add_feedback(self, feedback: str, changes: Dict[str, Any]) -> None:
        """Add user feedback and track changes."""
        self.feedback_history.append({
            "timestamp": datetime.now(),
            "feedback": feedback,
            "changes": changes,
            "version": self.version
        })
        self.version += 1
        self.updated_at = datetime.now()
    
    def get_all_criteria(self) -> Dict[str, ICPCriteria]:
        """Get all criteria (company + person) in a single dict."""
        return {**self.company_criteria, **self.person_criteria}
    
    def calculate_total_weight(self) -> float:
        """Calculate total weight of all criteria."""
        return sum(criteria.weight for criteria in self.get_all_criteria().values())
    
    def normalize_weights(self) -> None:
        """Normalize all criteria weights to sum to 1.0."""
        total_weight = self.calculate_total_weight()
        if total_weight > 0:
            for criteria in self.get_all_criteria().values():
                criteria.weight = criteria.weight / total_weight