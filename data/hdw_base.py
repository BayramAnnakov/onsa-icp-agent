"""Base data models for HorizonDataWave integration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class URN:
    type: str
    value: str
    
    def __dict__(self):
        return {
            "type": self.type,
            "value": self.value
        }


@dataclass
class Location:
    urn: Optional[URN] = None
    name: Optional[str] = None
    type: Optional[str] = None
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__() if self.urn else None,
            "name": self.name,
            "type": self.type
        }


@dataclass
class Industry:
    urn: Optional[URN] = None
    name: Optional[str] = None
    type: Optional[str] = None
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__() if self.urn else None,
            "name": self.name,
            "type": self.type
        }


@dataclass
class Company:
    urn: Optional[URN] = None
    url: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = None
    industry: Optional[str] = None
    headline: Optional[str] = None
    alias: Optional[str] = None
    
    def __dict__(self):
        return {
            "urn": self.urn.__dict__() if self.urn else None,
            "url": self.url,
            "name": self.name,
            "image": self.image,
            "industry": self.industry,
            "headline": self.headline,
            "alias": self.alias
        }