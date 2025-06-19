"""Data models for HorizonDataWave integration."""

from .hdw_base import URN, Location, Industry, Company
from .hdw_linkedin_user import (
    LinkedInUser, LinkedinUserExperience, LinkedinUserEducation,
    LinkedinUserSkill, LinkedinUserCertificate, LinkedinUserLanguage,
    LinkedinUserHonor, LinkedinUserPatent, CurrentCompany
)
from .hdw_linkedin_company import (
    LinkedinCompany, LinkedinOfficeLocation, LinkedinCompanyEmployee,
    CompanyEmployeeStats, LinkedinCompanyEmployeeStatsBlock
)
from .hdw_linkedin_social import (
    LinkedinUserPost, LinkedinPostComment, LinkedinPostReaction, LinkedinGroup
)
from .hdw_linkedin_search import (
    LinkedinSearchUser, LinkedinSearchJob, LinkedinSearchCompany
)
from .hdw_linkedin_management import (
    LinkedinManagementMe, LinkedinManagementConversation,
    LinkedinManagementChatMessage, LinkedinManagementChatMessages
)
from .hdw_misc import (
    LinkedinFileDownloadResponse, LinkedinEmailUser,
    LinkedinGoogleCompany
)

__all__ = [
    # Base
    "URN", "Location", "Industry", "Company",
    
    # User
    "LinkedInUser", "LinkedinUserExperience", "LinkedinUserEducation",
    "LinkedinUserSkill", "LinkedinUserCertificate", "LinkedinUserLanguage",
    "LinkedinUserHonor", "LinkedinUserPatent", "CurrentCompany",
    
    # Company
    "LinkedinCompany", "LinkedinOfficeLocation", "LinkedinCompanyEmployee",
    "CompanyEmployeeStats", "LinkedinCompanyEmployeeStatsBlock",
    
    # Social
    "LinkedinUserPost", "LinkedinPostComment", "LinkedinPostReaction",
    
    # Search
    "LinkedinSearchUser", "LinkedinSearchJob", "LinkedinSearchCompany",
    
    # Management
    "LinkedinManagementMe", "LinkedinManagementConversation",
    "LinkedinManagementChatMessage", "LinkedinManagementChatMessages",
    
    # Misc
    "LinkedinFileDownloadResponse", "LinkedinEmailUser",
    "LinkedinGoogleCompany", "LinkedinGroup"
]