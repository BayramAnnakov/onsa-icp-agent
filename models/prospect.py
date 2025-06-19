"""Prospect and related data models."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class Company(BaseModel):
    """Company information model."""
    
    name: str = Field(..., description="Company name")
    domain: Optional[str] = Field(None, description="Company domain/website")
    linkedin_url: Optional[HttpUrl] = Field(None, description="LinkedIn company page URL")
    
    # Basic info
    industry: Optional[str] = Field(None, description="Primary industry")
    description: Optional[str] = Field(None, description="Company description")
    founded_year: Optional[int] = Field(None, description="Year company was founded")
    
    # Size and scale
    employee_count: Optional[int] = Field(None, description="Number of employees")
    employee_range: Optional[str] = Field(None, description="Employee count range (e.g., '50-200')")
    revenue: Optional[str] = Field(None, description="Annual revenue")
    funding_stage: Optional[str] = Field(None, description="Funding stage")
    
    # Location
    headquarters: Optional[str] = Field(None, description="Headquarters location")
    locations: List[str] = Field(default_factory=list, description="All office locations")
    
    # Technology and tools
    tech_stack: List[str] = Field(default_factory=list, description="Technologies used")
    tools: List[str] = Field(default_factory=list, description="Tools and software used")
    
    # Social and web presence
    website_traffic: Optional[Dict[str, Any]] = Field(None, description="Website traffic data")
    social_media: Dict[str, str] = Field(default_factory=dict, description="Social media profiles")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional company data")


class Person(BaseModel):
    """Person/contact information model."""
    
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    email: Optional[str] = Field(None, description="Email address")
    linkedin_url: Optional[HttpUrl] = Field(None, description="LinkedIn profile URL")
    
    # Role information
    title: str = Field(..., description="Job title")
    department: Optional[str] = Field(None, description="Department")
    seniority_level: Optional[str] = Field(None, description="Seniority level")
    
    # Experience
    years_experience: Optional[int] = Field(None, description="Years of experience")
    years_at_company: Optional[int] = Field(None, description="Years at current company")
    previous_companies: List[str] = Field(default_factory=list, description="Previous companies")
    
    # Education and skills
    education: List[Dict[str, str]] = Field(default_factory=list, description="Education background")
    skills: List[str] = Field(default_factory=list, description="Professional skills")
    certifications: List[str] = Field(default_factory=list, description="Professional certifications")
    
    # Activity and engagement
    recent_posts: List[Dict[str, Any]] = Field(default_factory=list, description="Recent social media posts")
    activity_level: Optional[str] = Field(None, description="Social media activity level")
    last_post_date: Optional[datetime] = Field(None, description="Date of last social media post")
    
    # Contact preferences
    preferred_contact_method: Optional[str] = Field(None, description="Preferred contact method")
    timezone: Optional[str] = Field(None, description="Timezone")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional person data")


class ProspectScore(BaseModel):
    """Prospect scoring model."""
    
    total_score: float = Field(..., ge=0.0, le=1.0, description="Total prospect score")
    
    # Individual scores
    company_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    person_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    intent_score: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Detailed scoring breakdown
    criteria_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Scores for individual ICP criteria"
    )
    
    # Scoring metadata
    scoring_method: str = Field(default="weighted", description="Method used for scoring")
    scoring_version: str = Field(default="1.0", description="Version of scoring algorithm")
    scored_at: datetime = Field(default_factory=datetime.now)
    
    # Explanations and reasoning
    score_explanation: str = Field(default="", description="Explanation of why prospect received this score")
    strengths: List[str] = Field(default_factory=list, description="Prospect strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Areas where prospect doesn't match ICP")
    
    def get_priority_level(self) -> str:
        """Get priority level based on total score."""
        if self.total_score >= 0.8:
            return "high"
        elif self.total_score >= 0.6:
            return "medium"
        else:
            return "low"


class Prospect(BaseModel):
    """Complete prospect model combining company, person, and scoring."""
    
    id: str = Field(..., description="Unique identifier for the prospect")
    
    # Core data
    company: Company = Field(..., description="Company information")
    person: Person = Field(..., description="Person information")
    score: ProspectScore = Field(..., description="Prospect scoring")
    
    # Source and discovery
    source: str = Field(..., description="Source where prospect was found")
    discovered_at: datetime = Field(default_factory=datetime.now)
    
    # User interactions
    user_feedback: Optional[str] = Field(None, description="User feedback on this prospect")
    user_score_adjustment: Optional[float] = Field(None, description="User's score adjustment")
    user_priority: Optional[str] = Field(None, description="User-assigned priority")
    
    # Status tracking
    status: str = Field(default="new", description="Prospect status")
    last_contacted: Optional[datetime] = Field(None, description="Last contact date")
    next_follow_up: Optional[datetime] = Field(None, description="Next follow-up date")
    
    # Notes and tags
    notes: List[str] = Field(default_factory=list, description="Notes about this prospect")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional prospect data")
    
    def get_effective_score(self) -> float:
        """Get effective score considering user adjustments."""
        if self.user_score_adjustment is not None:
            return max(0.0, min(1.0, self.score.total_score + self.user_score_adjustment))
        return self.score.total_score
    
    def get_effective_priority(self) -> str:
        """Get effective priority considering user overrides."""
        if self.user_priority:
            return self.user_priority
        return self.score.get_priority_level()
    
    def add_note(self, note: str) -> None:
        """Add a note to the prospect."""
        self.notes.append(f"{datetime.now().isoformat()}: {note}")
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the prospect."""
        if tag not in self.tags:
            self.tags.append(tag)