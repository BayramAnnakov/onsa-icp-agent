"""LinkedIn Search data models for HorizonDataWave integration."""

from dataclasses import dataclass
from typing import List, Optional
from .hdw_base import URN, Company, Location, Industry
from .hdw_linkedin_user import CurrentCompany


@dataclass
class LinkedinSearchUser:
    """LinkedIn Search User result."""
    internal_id: URN
    urn: URN
    name: str
    url: str
    image: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    is_premium: bool = False
    current_companies: List['CurrentCompany'] = None
    
    def __post_init__(self):
        if self.current_companies is None:
            self.current_companies = []
    
    @property
    def first_name(self):
        """Extract first name from full name."""
        parts = self.name.split()
        return parts[0] if parts else ""
    
    @property
    def last_name(self):
        """Extract last name from full name."""
        parts = self.name.split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""
    
    @property
    def current_position_title(self):
        """Get current position title from headline or current companies."""
        if self.headline:
            # Headline often contains title
            return self.headline.split(" at ")[0] if " at " in self.headline else self.headline
        elif self.current_companies:
            return self.current_companies[0].position
        return ""
    
    @property
    def current_company_name(self):
        """Get current company name."""
        if self.current_companies and self.current_companies[0].company:
            if hasattr(self.current_companies[0].company, 'name'):
                return self.current_companies[0].company.name
            elif isinstance(self.current_companies[0].company, str):
                return self.current_companies[0].company
        # Try to extract from headline
        if self.headline and " at " in self.headline:
            return self.headline.split(" at ")[1]
        return ""


@dataclass
class LinkedinSearchJob:
    pass  # TODO: Implement


@dataclass
class LinkedinSearchCompany:
    pass  # TODO: Implement