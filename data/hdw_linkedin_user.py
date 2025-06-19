"""LinkedIn User data models for HorizonDataWave integration."""

from dataclasses import dataclass
from typing import List, Optional, Union
from .hdw_base import URN, Location, Industry, Company


@dataclass
class CurrentCompany:
    company: Union[Company, str]
    position: str
    description: str
    joined: int
    
    def __dict__(self):
        return {
            "company": self.company.__dict__() if isinstance(self.company, Company) else self.company,
            "position": self.position,
            "description": self.description,
            "joined": self.joined
        }


@dataclass
class LinkedinUserExperience:
    urn: Optional[URN] = None
    company: Optional[Company] = None
    position: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    joined: Optional[int] = None
    left: Optional[int] = None
    duration: Optional[str] = None
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__() if self.urn else None,
            "company": self.company.__dict__() if self.company else None,
            "position": self.position,
            "description": self.description,
            "location": self.location,
            "joined": self.joined,
            "left": self.left,
            "duration": self.duration
        }


@dataclass
class LinkedinUserEducation:
    institution: str
    degree: str
    field_of_study: str
    description: str
    logo_url: str
    start_date: int
    end_date: int
    
    def __dict__(self):
        return {
            "institution": self.institution,
            "degree": self.degree,
            "field_of_study": self.field_of_study,
            "description": self.description,
            "logo_url": self.logo_url,
            "start_date": self.start_date,
            "end_date": self.end_date
        }


@dataclass
class LinkedinUserSkill:
    urn: URN
    name: str
    endorsements: int
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__(),
            "name": self.name,
            "endorsements": self.endorsements
        }


@dataclass
class LinkedinUserCertificate:
    urn: URN
    name: str
    authority: str
    issued_on: int
    expires_on: int
    license_number: str
    display_source: str
    company: Company
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__(),
            "name": self.name,
            "authority": self.authority,
            "issued_on": self.issued_on,
            "expires_on": self.expires_on,
            "license_number": self.license_number,
            "display_source": self.display_source,
            "company": self.company.__dict__()
        }


@dataclass
class LinkedinUserLanguage:
    name: str
    proficiency: str
    
    def __dict__(self):
        return {
            "name": self.name,
            "proficiency": self.proficiency
        }


@dataclass
class LinkedinUserHonor:
    title: str
    description: str
    issued_on: int
    issuer: str
    
    def __dict__(self):
        return {
            "title": self.title,
            "description": self.description,
            "issued_on": self.issued_on,
            "issuer": self.issuer
        }


@dataclass
class LinkedinUserPatent:
    urn: URN
    title: str
    description: str
    application_number: str
    patent_number: str
    url: str
    issued_on: int
    filed_on: int
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__(),
            "title": self.title,
            "description": self.description,
            "application_number": self.application_number,
            "patent_number": self.patent_number,
            "url": self.url,
            "issued_on": self.issued_on,
            "filed_on": self.filed_on
        }


@dataclass
class LinkedInUser:
    urn: URN
    url: str
    name: str
    image: str
    headline: str
    summary: str
    location: Location
    industry: Industry
    educations: List[LinkedinUserEducation]
    languages: List[LinkedinUserLanguage]
    honors: List[LinkedinUserHonor]
    patents: List[LinkedinUserPatent]
    certificates: List[LinkedinUserCertificate]
    skills: List[LinkedinUserSkill]
    experiences: List[LinkedinUserExperience]
    current_companies: List[CurrentCompany]
    website: str
    birthdate: str
    is_student: bool
    is_influencer: bool
    
    def __dict__(self):
        return {
            "@type": "LinkedInUser",
            "urn": self.urn.__dict__(),
            "url": self.url,
            "name": self.name,
            "image": self.image,
            "headline": self.headline,
            "summary": self.summary,
            "location": self.location.__dict__(),
            "industry": self.industry.__dict__(),
            "educations": [edu.__dict__() for edu in self.educations],
            "languages": [lang.__dict__() for lang in self.languages],
            "honors": [honor.__dict__() for honor in self.honors],
            "patents": [patent.__dict__() for patent in self.patents],
            "certificates": [cert.__dict__() for cert in self.certificates],
            "skills": [skill.__dict__() for skill in self.skills],
            "experiences": [exp.__dict__() for exp in self.experiences],
            "current_companies": [cc.__dict__() for cc in self.current_companies],
            "website": self.website,
            "birthdate": self.birthdate,
            "is_student": self.is_student,
            "is_influencer": self.is_influencer
        }