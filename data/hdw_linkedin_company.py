"""LinkedIn Company data models for HorizonDataWave integration."""

from dataclasses import dataclass
from typing import List, Optional
from .hdw_base import URN
from .hdw_linkedin_user import CurrentCompany


@dataclass
class LinkedinOfficeLocation:
    name: str
    is_headquarter: bool
    location: str
    description: str
    latitude: float
    longitude: float
    
    def __dict__(self):
        return {
            "@type": "LinkedinOfficeLocation",
            "name": self.name,
            "is_headquarter": self.is_headquarter,
            "location": self.location,
            "description": self.description,
            "latitude": self.latitude,
            "longitude": self.longitude
        }


@dataclass
class LinkedinCompanyEmployeeStatsBlock:
    type: str
    name: str
    count: int


@dataclass
class CompanyEmployeeStats:
    locations: List[LinkedinCompanyEmployeeStatsBlock]
    educations: List[LinkedinCompanyEmployeeStatsBlock]
    skills: List[LinkedinCompanyEmployeeStatsBlock]
    functions: List[LinkedinCompanyEmployeeStatsBlock]
    majors: List[LinkedinCompanyEmployeeStatsBlock]


@dataclass
class LinkedinCompanyEmployee:
    urn: URN
    name: str
    url: str
    image: str
    headline: str
    location: str
    is_premium: bool
    current_companies: List[CurrentCompany]
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__(),
            "name": self.name,
            "url": self.url,
            "image": self.image,
            "headline": self.headline,
            "location": self.location,
            "is_premium": self.is_premium,
            "current_companies": [cc.__dict__() for cc in self.current_companies]
        }


@dataclass
class LinkedinCompany:
    urn: URN
    url: str
    name: str
    alias: str
    website: str
    locations: List[LinkedinOfficeLocation]
    short_description: str
    description: str
    employee_count: int
    founded_on: int
    phone: str
    logo_url: str
    organizational_urn: URN
    page_verification_status: bool
    last_modified_at: int
    headquarter_status: bool
    headquarter_location: str
    industry: URN
    specialities: List[str]
    is_active: bool
    employee_count_range: str
    similar_organizations: List[URN]
    hashtags: List[str]
    crunchbase_link: str
    
    def __dict__(self):
        return {
            "@type": "LinkedinCompany",
            "urn": self.urn.__dict__(),
            "url": self.url,
            "name": self.name,
            "alias": self.alias,
            "website": self.website,
            "locations": [loc.__dict__() for loc in self.locations],
            "short_description": self.short_description,
            "description": self.description,
            "employee_count": self.employee_count,
            "founded_on": self.founded_on,
            "phone": self.phone,
            "logo_url": self.logo_url,
            "organizational_urn": self.organizational_urn.__dict__(),
            "page_verification_status": self.page_verification_status,
            "last_modified_at": self.last_modified_at,
            "headquarter_status": self.headquarter_status,
            "headquarter_location": self.headquarter_location,
            "industry": self.industry.__dict__(),
            "specialities": self.specialities,
            "is_active": self.is_active,
            "employee_count_range": self.employee_count_range,
            "similar_organizations": [org.__dict__() for org in self.similar_organizations],
            "hashtags": self.hashtags,
            "crunchbase_link": self.crunchbase_link
        }