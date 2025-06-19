"""LinkedIn Social/Post data models for HorizonDataWave integration."""

from dataclasses import dataclass
from typing import List, Optional
from .hdw_base import URN


@dataclass
class LinkedinUserPost:
    urn: URN
    url: str
    author: str
    content: str
    reaction_count: int
    comment_count: int
    repost_count: int
    posted_at: int
    reposted: bool
    
    def __dict__(self):
        return {
            "@type": "LinkedinUserPost",
            "urn": self.urn.__dict__(),
            "url": self.url,
            "author": self.author,
            "content": self.content,
            "reaction_count": self.reaction_count,
            "comment_count": self.comment_count,
            "repost_count": self.repost_count,
            "posted_at": self.posted_at,
            "reposted": self.reposted
        }


@dataclass
class LinkedinPostComment:
    urn: URN
    author_name: str
    author_headline: str
    author_url: str
    author_image: str
    content: str
    posted_at: int
    
    def __dict__(self):
        return {
            "@type": "LinkedinPostComment",
            "urn": self.urn.__dict__(),
            "author_name": self.author_name,
            "author_headline": self.author_headline,
            "author_url": self.author_url,
            "author_image": self.author_image,
            "content": self.content,
            "posted_at": self.posted_at
        }


@dataclass
class LinkedinPostReaction:
    urn: URN
    name: str
    headline: str
    url: str
    image: str
    reaction_type: str
    
    def __dict__(self):
        return {
            "@type": "LinkedinPostReaction",
            "urn": self.urn.__dict__(),
            "name": self.name,
            "headline": self.headline,
            "url": self.url,
            "image": self.image,
            "reaction_type": self.reaction_type
        }


@dataclass  
class LinkedinGroup:
    urn: URN
    name: str
    url: str
    description: str
    member_count: int
    rules: str
    is_member: bool
    
    def __dict__(self):
        return {
            "@type": "LinkedinGroup",
            "urn": self.urn.__dict__(),
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "member_count": self.member_count,
            "rules": self.rules,
            "is_member": self.is_member
        }