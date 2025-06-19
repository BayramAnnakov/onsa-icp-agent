import os
import requests
import requests_cache
import csv
import time
from dotenv import load_dotenv
from typing import Dict, List, Optional, Union
from datetime import datetime
import uuid
import logging
from dataclasses import dataclass

# Import data classes from the new data module
from data.hdw_base import URN, Location, Industry, Company
from data.hdw_linkedin_user import (
    CurrentCompany, LinkedInUser, LinkedinUserExperience,
    LinkedinUserEducation, LinkedinUserSkill, LinkedinUserCertificate,
    LinkedinUserLanguage, LinkedinUserHonor, LinkedinUserPatent
)
from data.hdw_linkedin_company import (
    LinkedinCompany, LinkedinOfficeLocation, LinkedinCompanyEmployee,
    CompanyEmployeeStats, LinkedinCompanyEmployeeStatsBlock
)
from data.hdw_linkedin_social import (
    LinkedinUserPost, LinkedinPostComment, LinkedinPostReaction, LinkedinGroup
)
from data.hdw_linkedin_search import (
    LinkedinSearchUser, LinkedinSearchJob, LinkedinSearchCompany
)
from data.hdw_linkedin_management import (
    LinkedinManagementMe, LinkedinManagementConversation,
    LinkedinManagementChatMessage, LinkedinManagementChatMessages
)
from data.hdw_misc import (
    LinkedinFileDownloadResponse, LinkedinEmailUser, LinkedinGoogleCompany
)

UNITED_STATES_URN = "urn:li:geo:103644278"


class HorizonDataWave:
    def __init__(self, cache_enabled: bool = True, cache_expire_after: int = 31536000):
        """
        Initialize HDW client with optional caching
        
        Args:
            cache_enabled (bool): Enable requests caching (default: True)
            cache_expire_after (int): Cache expiration in seconds (default: 31536000 = 1 year)
        """
        load_dotenv()
        self.api_token = os.getenv('HDW_API_TOKEN')
        if not self.api_token:
            raise ValueError("HDW_API_TOKEN not found in .env file")
        self.base_url = "https://api.horizondatawave.ai/api"
        self.headers = {
            "access-token": f"{self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Setup caching
        self.cache_enabled = cache_enabled
        self.use_fixed_request_ids = False  # Initialize deterministic caching flag
        if cache_enabled:
            # Create cache session - simple approach
            # Note: Each request will have a unique cache entry due to request IDs
            # but this is still valuable for repeated API calls with same parameters
            self.session = requests_cache.CachedSession(
                'hdw_api_cache',
                backend='sqlite',
                expire_after=cache_expire_after,
                allowable_codes=[200, 404],  # Cache successful responses and 404s
                cache_control=True,  # Enable cache control
                stale_if_error=True  # Return stale cache if error occurs
            )
            logging.info(f"HDW API caching enabled - cache expires after {cache_expire_after} seconds ({cache_expire_after//86400} days)")
            logging.info("Note: Due to unique request IDs, caching will work for identical request parameters only")
        else:
            self.session = requests.Session()
            logging.info("HDW API caching disabled")
    
    def _get_headers(self, request_id: Optional[str] = None, payload: Optional[Dict] = None) -> Dict[str, str]:
        """Get headers with optional request ID"""
        headers = self.headers.copy()
        if request_id:
            headers["x-request-id"] = request_id
        else:
            # Use deterministic request ID based on payload for better caching
            if hasattr(self, 'use_fixed_request_ids') and self.use_fixed_request_ids and payload:
                # Create a deterministic ID based on the request payload
                import hashlib
                payload_str = str(sorted(payload.items())) if payload else ""
                request_hash = hashlib.md5(payload_str.encode()).hexdigest()[:8]
                headers["x-request-id"] = f"cache-{request_hash}"
            else:
                headers["x-request-id"] = str(uuid.uuid4())
        return headers
    
    def clear_cache(self):
        """Clear all cached responses"""
        if self.cache_enabled and hasattr(self.session, 'cache'):
            self.session.cache.clear()
            logging.info("HDW API cache cleared")
    
    def get_cache_info(self):
        """Get cache statistics"""
        if self.cache_enabled and hasattr(self.session, 'cache'):
            try:
                # Get cache stats if available
                cached_urls = len(list(self.session.cache.urls))
                return {
                    'cache_enabled': True,
                    'cached_requests': cached_urls,
                    'backend': 'sqlite',
                    'cache_file': 'hdw_api_cache.sqlite'
                }
            except:
                return {
                    'cache_enabled': True,
                    'cached_requests': 'unknown',
                    'backend': 'sqlite',
                    'cache_file': 'hdw_api_cache.sqlite'
                }
        else:
            return {'cache_enabled': False}
    
    def delete_expired_cache(self):
        """Delete expired cache entries"""
        if self.cache_enabled and hasattr(self.session, 'cache'):
            self.session.cache.delete(expired=True)
            logging.info("Expired HDW API cache entries deleted")
    
    def enable_deterministic_caching(self, enable: bool = True):
        """
        Enable/disable deterministic caching by using fixed request IDs
        
        Args:
            enable (bool): If True, use fixed request IDs for better caching
                          If False, use unique request IDs (default behavior)
        """
        self.use_fixed_request_ids = enable
        if enable:
            logging.info("Deterministic caching enabled - using fixed request IDs")
        else:
            logging.info("Deterministic caching disabled - using unique request IDs")

    # Company Endpoints
    
    def get_linkedin_company(self, 
                           company: str,
                           timeout: Optional[int] = 300,
                           request_id: Optional[str] = None) -> List[LinkedinCompany]:
        """
        Get LinkedIn company information using Horizon Data Wave API.
        
        Args:
            company (str): Company name or URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinCompany]: List of LinkedIn company objects
        """
        endpoint = f"{self.base_url}/linkedin/company"
        
        payload = {
            "company": company,
            "timeout": timeout
        }
        
        headers = self._get_headers(request_id, payload)
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            companies = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Process the company data similar to search_company_by_name
                        urn = URN(type=item['urn']['type'], value=item['urn']['value'])
                        organizational_urn = URN(type=item['organizational_urn']['type'], value=item['organizational_urn']['value'])
                        industry = URN(type=item['industry']['type'], value=item['industry']['value'])
                        
                        locations = []
                        for loc in item.get('locations', []):
                            location = LinkedinOfficeLocation(
                                name=loc['name'],
                                is_headquarter=loc['is_headquarter'],
                                location=loc['location'],
                                description=loc['description'],
                                latitude=loc['latitude'],
                                longitude=loc['longitude']
                            )
                            locations.append(location)
                        
                        similar_orgs = []
                        for org in item.get('similar_organizations', []):
                            similar_org = URN(type=org['type'], value=org['value'])
                            similar_orgs.append(similar_org)
                        
                        company = LinkedinCompany(
                            urn=urn,
                            url=item.get('url', ''),
                            name=item.get('name', ''),
                            alias=item.get('alias', ''),
                            website=item.get('website', ''),
                            locations=locations,
                            short_description=item.get('short_description', ''),
                            description=item.get('description', ''),
                            employee_count=item.get('employee_count', 0),
                            founded_on=item.get('founded_on', 0),
                            phone=item.get('phone', ''),
                            logo_url=item.get('logo_url', ''),
                            organizational_urn=organizational_urn,
                            page_verification_status=item.get('page_verification_status', False),
                            last_modified_at=item.get('last_modified_at', 0),
                            headquarter_status=item.get('headquarter_status', False),
                            headquarter_location=item.get('headquarter_location', ''),
                            industry=industry,
                            specialities=item.get('specialities', []),
                            is_active=item.get('is_active', False),
                            employee_count_range=item.get('employee_count_range', ''),
                            similar_organizations=similar_orgs,
                            hashtags=item.get('hashtags', []),
                            crunchbase_link=item.get('crunchbase_link', '')
                        )
                        companies.append(company)
                    except Exception as e:
                        print(f"Error processing company data: {e}")
                        continue
                        
            return companies
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_company_employee_stats(self, 
                                 company_urn: str,
                                 timeout: Optional[int] = 300,
                                 request_id: Optional[str] = None) -> List[CompanyEmployeeStats]:
        """
        Get company employee statistics using Horizon Data Wave API.
        
        Args:
            company_urn (str): Company URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[CompanyEmployeeStats]: List of employee statistics
        """
        endpoint = f"{self.base_url}/linkedin/company/employee_stats"
        headers = self._get_headers(request_id)
        
        payload = {
            "urn": company_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            stats_list = []
            if isinstance(data, list):
                for item in data:
                    try:
                        stats = CompanyEmployeeStats(
                            locations=[LinkedinCompanyEmployeeStatsBlock(**loc) for loc in item.get('locations', [])],
                            educations=[LinkedinCompanyEmployeeStatsBlock(**edu) for edu in item.get('educations', [])],
                            skills=[LinkedinCompanyEmployeeStatsBlock(**skill) for skill in item.get('skills', [])],
                            functions=[LinkedinCompanyEmployeeStatsBlock(**func) for func in item.get('functions', [])],
                            majors=[LinkedinCompanyEmployeeStatsBlock(**major) for major in item.get('majors', [])]
                        )
                        stats_list.append(stats)
                    except Exception as e:
                        print(f"Error processing employee stats data: {e}")
                        continue
                        
            return stats_list
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_company_employees(self,
                            company_urn: str,
                            count: int = 100,
                            timeout: Optional[int] = 300,
                            request_id: Optional[str] = None) -> List[LinkedinCompanyEmployee]:
        """
        Get company employees list using Horizon Data Wave API.
        
        Args:
            company_urn (str): Company URN
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinCompanyEmployee]: List of company employees
        """
        endpoint = f"{self.base_url}/linkedin/company/employees"
        headers = self._get_headers(request_id)
        
        payload = {
            "urn": company_urn,
            "count": count,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            employees = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value'])
                        
                        current_companies = []
                        for company_data in item.get('current_companies', []):
                            company = None
                            if isinstance(company_data.get('company'), dict):
                                company_urn = URN(
                                    type=company_data['company']['urn']['type'],
                                    value=company_data['company']['urn']['value']
                                )
                                company = Company(
                                    urn=company_urn,
                                    url=company_data['company'].get('url'),
                                    name=company_data['company'].get('name'),
                                    image=company_data['company'].get('image'),
                                    industry=company_data['company'].get('industry')
                                )
                            else:
                                company = company_data.get('company')
                                
                            current_company = CurrentCompany(
                                company=company,
                                position=company_data.get('position', ''),
                                description=company_data.get('description', ''),
                                joined=company_data.get('joined', 0)
                            )
                            current_companies.append(current_company)
                        
                        employee = LinkedinCompanyEmployee(
                            urn=urn,
                            name=item.get('name', ''),
                            url=item.get('url', ''),
                            image=item.get('image', ''),
                            headline=item.get('headline', ''),
                            location=item.get('location', ''),
                            is_premium=item.get('is_premium', False),
                            current_companies=current_companies
                        )
                        employees.append(employee)
                    except Exception as e:
                        print(f"Error processing employee data: {e}")
                        continue
                        
            return employees
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_company_posts(self,
                        company_urn: str,
                        count: int = 100,
                        timeout: Optional[int] = 300,
                        request_id: Optional[str] = None) -> List[LinkedinUserPost]:
        """
        Get company posts using Horizon Data Wave API.
        
        Args:
            company_urn (str): Company URN
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserPost]: List of company posts
        """
        endpoint = f"{self.base_url}/linkedin/company/posts"
        headers = self._get_headers(request_id)
        
        payload = {
            "urn": company_urn,
            "count": count,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        # Author can be either a user or company
                        author = None
                        if item.get('author'):
                            # Implementation depends on the actual API response structure
                            # This is a simplified version
                            author = item.get('author')
                        
                        post = LinkedinUserPost(
                            urn=urn,
                            author=author,
                            text=item.get('text', ''),
                            posted_at=item.get('posted_at', 0),
                            like_count=item.get('like_count', 0),
                            comment_count=item.get('comment_count', 0),
                            repost_count=item.get('repost_count', 0)
                        )
                        posts.append(post)
                    except Exception as e:
                        print(f"Error processing post data: {e}")
                        continue
                        
            return posts
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    # User Profile Endpoints
    
    def get_linkedin_user(self,
                        user: str,
                        include_experience: bool = False,
                        include_education: bool = False,
                        include_certificates: bool = False,
                        include_languages: bool = False,
                        include_skills: bool = False,
                        include_honors: bool = False,
                        include_patents: bool = False,
                        timeout: Optional[int] = 300,
                        request_id: Optional[str] = None) -> List[LinkedInUser]:
        """
        Get LinkedIn user profile using Horizon Data Wave API.
        
        Args:
            user (str): User name or URN
            include_experience (bool, optional): Include experience details. Defaults to False.
            include_education (bool, optional): Include education details. Defaults to False.
            include_certificates (bool, optional): Include certificates. Defaults to False.
            include_languages (bool, optional): Include languages. Defaults to False.
            include_skills (bool, optional): Include skills. Defaults to False.
            include_honors (bool, optional): Include honors. Defaults to False.
            include_patents (bool, optional): Include patents. Defaults to False.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedInUser]: List of LinkedIn user objects
        """
        endpoint = f"{self.base_url}/linkedin/user"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user,
            "timeout": timeout,
            "include_experience": include_experience,
            "include_education": include_education,
            "include_certificates": include_certificates,
            "include_languages": include_languages,
            "include_skills": include_skills,
            "include_honors": include_honors,
            "include_patents": include_patents
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            users = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Process similar to search_nav_search_users but with more detailed data
                        internal_id = URN(type=item['internal_id']['type'], value=item['internal_id']['value'])
                        urn = URN(type=item['urn']['type'], value=item['urn']['value'])
                        
                        current_companies = []
                        for company_data in item.get('current_companies', []):
                            company = None
                            if isinstance(company_data.get('company'), dict):
                                company_urn = URN(
                                    type=company_data['company']['urn']['type'],
                                    value=company_data['company']['urn']['value']
                                )
                                company = Company(
                                    urn=company_urn,
                                    url=company_data['company'].get('url'),
                                    name=company_data['company'].get('name'),
                                    image=company_data['company'].get('image'),
                                    industry=company_data['company'].get('industry')
                                )
                            else:
                                company = company_data.get('company')
                                
                            current_company = CurrentCompany(
                                company=company,
                                position=company_data.get('position', ''),
                                description=company_data.get('description', ''),
                                joined=company_data.get('joined', 0)
                            )
                            current_companies.append(current_company)
                        
                        user = LinkedInUser(
                            internal_id=internal_id,
                            urn=urn,
                            name=item.get('name', ''),
                            url=item.get('url', ''),
                            image=item.get('image', ''),
                            headline=item.get('headline', ''),
                            location=item.get('location', ''),
                            is_premium=item.get('is_premium', False),
                            current_companies=current_companies
                        )
                        users.append(user)
                    except Exception as e:
                        print(f"Error processing user data: {e}")
                        continue
                        
            return users
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_experience(self,
                          user_urn: str,
                          timeout: Optional[int] = 300,
                          request_id: Optional[str] = None) -> List[LinkedinUserExperience]:
        """
        Get user work experience using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserExperience]: List of user experience objects
        """
        endpoint = f"{self.base_url}/linkedin/user/experience"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            experiences = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        company = None
                        if item.get('company') and isinstance(item['company'], dict):
                            company_urn = URN(type=item['company']['urn']['type'], value=item['company']['urn']['value'])
                            company = Company(
                                urn=company_urn,
                                url=item['company'].get('url'),
                                name=item['company'].get('name'),
                                image=item['company'].get('image'),
                                industry=item['company'].get('industry')
                            )
                        
                        experience = LinkedinUserExperience(
                            urn=urn,
                            company=company,
                            position=item.get('position'),
                            description=item.get('description'),
                            location=item.get('location'),
                            started_on=item.get('started_on'),
                            ended_on=item.get('ended_on')
                        )
                        experiences.append(experience)
                    except Exception as e:
                        print(f"Error processing experience data: {e}")
                        continue
                        
            return experiences
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_education(self,
                         user_urn: str,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[LinkedinUserEducation]:
        """
        Get user education history using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserEducation]: List of user education objects
        """
        endpoint = f"{self.base_url}/linkedin/user/education"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            educations = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        school = None
                        if item.get('school') and isinstance(item['school'], dict):
                            school_urn = URN(type=item['school']['urn']['type'], value=item['school']['urn']['value'])
                            school = Company(
                                urn=school_urn,
                                url=item['school'].get('url'),
                                name=item['school'].get('name'),
                                image=item['school'].get('image')
                            )
                        
                        education = LinkedinUserEducation(
                            urn=urn,
                            school=school,
                            degree=item.get('degree'),
                            field_of_study=item.get('field_of_study'),
                            description=item.get('description'),
                            started_on=item.get('started_on'),
                            ended_on=item.get('ended_on')
                        )
                        educations.append(education)
                    except Exception as e:
                        print(f"Error processing education data: {e}")
                        continue
                        
            return educations
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_skills(self,
                      user_urn: str,
                      timeout: Optional[int] = 300,
                      request_id: Optional[str] = None) -> List[LinkedinUserSkill]:
        """
        Get user skills using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserSkill]: List of user skills
        """
        endpoint = f"{self.base_url}/linkedin/user/skills"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            skills = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        skill = LinkedinUserSkill(
                            urn=urn,
                            name=item.get('name'),
                            endorsement_count=item.get('endorsement_count')
                        )
                        skills.append(skill)
                    except Exception as e:
                        print(f"Error processing skill data: {e}")
                        continue
                        
            return skills
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_certificates(self,
                            user_urn: str,
                            timeout: Optional[int] = 300,
                            request_id: Optional[str] = None) -> List[LinkedinUserCertificate]:
        """
        Get user certificates using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserCertificate]: List of user certificates
        """
        endpoint = f"{self.base_url}/linkedin/user/certificates"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            certificates = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        authority = None
                        if item.get('authority') and isinstance(item['authority'], dict):
                            auth_urn = URN(type=item['authority']['urn']['type'], value=item['authority']['urn']['value'])
                            authority = Company(
                                urn=auth_urn,
                                name=item['authority'].get('name')
                            )
                        
                        certificate = LinkedinUserCertificate(
                            urn=urn,
                            name=item.get('name'),
                            authority=authority,
                            issued_on=item.get('issued_on'),
                            expires_on=item.get('expires_on')
                        )
                        certificates.append(certificate)
                    except Exception as e:
                        print(f"Error processing certificate data: {e}")
                        continue
                        
            return certificates
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_languages(self,
                         user_urn: str,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[LinkedinUserLanguage]:
        """
        Get user languages using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserLanguage]: List of user languages
        """
        endpoint = f"{self.base_url}/linkedin/user/languages"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            languages = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        language = LinkedinUserLanguage(
                            urn=urn,
                            name=item.get('name'),
                            proficiency=item.get('proficiency')
                        )
                        languages.append(language)
                    except Exception as e:
                        print(f"Error processing language data: {e}")
                        continue
                        
            return languages
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_honors(self,
                      user_urn: str,
                      timeout: Optional[int] = 300,
                      request_id: Optional[str] = None) -> List[LinkedinUserHonor]:
        """
        Get user honors and awards using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserHonor]: List of user honors
        """
        endpoint = f"{self.base_url}/linkedin/user/honors"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            honors = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        honor = LinkedinUserHonor(
                            urn=urn,
                            title=item.get('title'),
                            issuer=item.get('issuer'),
                            issued_on=item.get('issued_on'),
                            description=item.get('description')
                        )
                        honors.append(honor)
                    except Exception as e:
                        print(f"Error processing honor data: {e}")
                        continue
                        
            return honors
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_patents(self,
                       user_urn: str,
                       timeout: Optional[int] = 300,
                       request_id: Optional[str] = None) -> List[LinkedinUserPatent]:
        """
        Get user patents using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserPatent]: List of user patents
        """
        endpoint = f"{self.base_url}/linkedin/user/patents"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            patents = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        patent = LinkedinUserPatent(
                            urn=urn,
                            title=item.get('title'),
                            patent_number=item.get('patent_number'),
                            patent_office=item.get('patent_office'),
                            inventors=item.get('inventors'),
                            issued_on=item.get('issued_on'),
                            description=item.get('description')
                        )
                        patents.append(patent)
                    except Exception as e:
                        print(f"Error processing patent data: {e}")
                        continue
                        
            return patents
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_posts(self,
                     user_urn: str,
                     count: int = 100,
                     timeout: Optional[int] = 300,
                     request_id: Optional[str] = None) -> List[LinkedinUserPost]:
        """
        Get user posts using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserPost]: List of user posts
        """
        endpoint = f"{self.base_url}/linkedin/user/posts"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "count": count,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        # Author can be either a user or company
                        author = None
                        if item.get('author'):
                            # This would need to be implemented based on actual API response structure
                            author = item.get('author')
                        
                        post = LinkedinUserPost(
                            urn=urn,
                            author=author,
                            text=item.get('text', ''),
                            posted_at=item.get('posted_at', 0),
                            like_count=item.get('like_count', 0),
                            comment_count=item.get('comment_count', 0),
                            repost_count=item.get('repost_count', 0)
                        )
                        posts.append(post)
                    except Exception as e:
                        print(f"Error processing post data: {e}")
                        continue
                        
            return posts
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_reactions(self,
                         user_urn: str,
                         count: int = 100,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[LinkedinUserPost]:
        """
        Get user reactions to posts using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinUserPost]: List of posts the user reacted to
        """
        endpoint = f"{self.base_url}/linkedin/user/reactions"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "count": count,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        # Author can be either a user or company
                        author = None
                        if item.get('author'):
                            author = item.get('author')
                        
                        post = LinkedinUserPost(
                            urn=urn,
                            author=author,
                            text=item.get('text', ''),
                            posted_at=item.get('posted_at', 0),
                            like_count=item.get('like_count', 0),
                            comment_count=item.get('comment_count', 0),
                            repost_count=item.get('repost_count', 0)
                        )
                        posts.append(post)
                    except Exception as e:
                        print(f"Error processing post data: {e}")
                        continue
                        
            return posts
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def get_user_endorsers(self,
                         user_urn: str,
                         skill_name: Optional[str] = None,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[LinkedInUser]:
        """
        Get user skill endorsers using Horizon Data Wave API.
        
        Args:
            user_urn (str): User URN
            skill_name (str, optional): Specific skill name to get endorsers for
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedInUser]: List of endorsers
        """
        endpoint = f"{self.base_url}/linkedin/user/endorsers"
        headers = self._get_headers(request_id)
        
        payload = {
            "user": user_urn,
            "timeout": timeout
        }
        
        if skill_name:
            payload["skill_name"] = skill_name
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            endorsers = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Process similar to other user data
                        internal_id = URN(type=item['internal_id']['type'], value=item['internal_id']['value'])
                        urn = URN(type=item['urn']['type'], value=item['urn']['value'])
                        
                        current_companies = []
                        for company_data in item.get('current_companies', []):
                            company = None
                            if isinstance(company_data.get('company'), dict):
                                company_urn = URN(
                                    type=company_data['company']['urn']['type'],
                                    value=company_data['company']['urn']['value']
                                )
                                company = Company(
                                    urn=company_urn,
                                    url=company_data['company'].get('url'),
                                    name=company_data['company'].get('name'),
                                    image=company_data['company'].get('image'),
                                    industry=company_data['company'].get('industry')
                                )
                            else:
                                company = company_data.get('company')
                                
                            current_company = CurrentCompany(
                                company=company,
                                position=company_data.get('position', ''),
                                description=company_data.get('description', ''),
                                joined=company_data.get('joined', 0)
                            )
                            current_companies.append(current_company)
                        
                        endorser = LinkedInUser(
                            internal_id=internal_id,
                            urn=urn,
                            name=item.get('name', ''),
                            url=item.get('url', ''),
                            image=item.get('image', ''),
                            headline=item.get('headline', ''),
                            location=item.get('location', ''),
                            is_premium=item.get('is_premium', False),
                            current_companies=current_companies
                        )
                        endorsers.append(endorser)
                    except Exception as e:
                        print(f"Error processing endorser data: {e}")
                        continue
                        
            return endorsers
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    # Enhanced Search Endpoints
    
    def search_linkedin_users(self,
                            keywords: Optional[str] = None,
                            names: Optional[str] = None,
                            current_companies: Optional[List[str]] = None,
                            past_companies: Optional[List[str]] = None,
                            locations: Optional[List[str]] = None,
                            industries: Optional[List[str]] = None,
                            educations: Optional[List[str]] = None,
                            current_titles: Optional[List[str]] = None,
                            past_titles: Optional[List[str]] = None,
                            functions: Optional[List[str]] = None,
                            levels: Optional[List[str]] = None,
                            company_sizes: Optional[List[str]] = None,
                            company_locations: Optional[List[str]] = None,
                            is_posted_on_linkedin: Optional[bool] = None,
                            count: int = 100,
                            timeout: Optional[int] = 300,
                            request_id: Optional[str] = None) -> List[LinkedinSearchUser]:
        """
        Search LinkedIn users with extensive filtering options using Horizon Data Wave API.
        
        Args:
            keywords (str, optional): Search keywords (e.g., "data scientist", "sales director")
            names (str, optional): Names to search for
            current_companies (List[str], optional): Current companies URNs or names
            past_companies (List[str], optional): Past companies URNs or names
            locations (List[str], optional): Location URNs from search_locations()
                Example: ["urn:li:geo:103644278"] for United States
            industries (List[str], optional): Industry URNs from search_industries()
                Example: ["urn:li:industry:4"] for Software Development
            educations (List[str], optional): Education institution URNs
            current_titles (List[str], optional): Current job titles
                Example: ["VP Sales", "Head of Sales", "Sales Director"]
            past_titles (List[str], optional): Past job titles
            functions (List[str], optional): Job function URNs
            levels (List[str], optional): Seniority levels for search_linkedin_users
                Valid values: ["VP", "Director", "Manager", "Senior", "Entry", "C-Level", "Head"]
                Note: For search_nav_search_users, use different values:
                ["Entry", "Director", "Owner", "CXO", "Vice President", "Experienced Manager", 
                 "Entry Manager", "Strategic", "Senior", "Trainy"]
            company_sizes (List[str], optional): Company size ranges
                MUST use these exact enum values:
                - "1-10"
                - "11-50"
                - "51-200"
                - "201-500"
                - "501-1000"
                - "1001-5000"
                - "5001-10000"
                - "10001+"
            company_locations (List[str], optional): Company location URNs
            is_posted_on_linkedin (bool, optional): Filter users who recently posted
            count (int, optional): Maximum number of results. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinSearchUser]: List of LinkedIn search user objects
            
        Example usage:
            users = hdw.search_linkedin_users(
                keywords="VP Sales",
                current_titles=["VP Sales", "Vice President Sales"],
                locations=["urn:li:geo:103644278"],  # United States
                industries=["urn:li:industry:4"],     # Software Development
                levels=["VP", "C-Level"],
                company_sizes=["51-200", "201-500"],
                count=10
            )
        """
        endpoint = f"{self.base_url}/linkedin/search/users"
        headers = self._get_headers(request_id)
        
        payload = {
            "count": count,
            "timeout": timeout
        }
        
        # Add optional parameters
        if keywords:
            payload["keywords"] = keywords
        if names:
            payload["names"] = names
        if current_companies:
            payload["current_companies"] = current_companies
        if past_companies:
            payload["past_companies"] = past_companies
        if locations:
            payload["locations"] = locations
        if industries:
            payload["industries"] = industries
        if educations:
            payload["educations"] = educations
        if current_titles:
            payload["current_titles"] = current_titles
        if past_titles:
            payload["past_titles"] = past_titles
        if functions:
            payload["functions"] = functions
        if levels:
            payload["levels"] = levels
        if company_sizes:
            payload["company_sizes"] = company_sizes
        if company_locations:
            payload["company_locations"] = company_locations
        if is_posted_on_linkedin is not None:
            payload["is_posted_on_linkedin"] = is_posted_on_linkedin
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            users = []
            if isinstance(data, list):
                for item in data:
                    try:
                        internal_id = URN(type=item['internal_id']['type'], value=item['internal_id']['value']) if item.get('internal_id') else urn
                        urn = URN(type=item['urn']['type'], value=item['urn']['value'])
                        
                        current_companies = []
                        for company_data in item.get('current_companies', []):
                            company = None
                            if isinstance(company_data.get('company'), dict):
                                company_urn = URN(
                                    type=company_data['company']['urn']['type'],
                                    value=company_data['company']['urn']['value']
                                )
                                company = Company(
                                    urn=company_urn,
                                    url=company_data['company'].get('url'),
                                    name=company_data['company'].get('name'),
                                    image=company_data['company'].get('image'),
                                    industry=company_data['company'].get('industry')
                                )
                            else:
                                company = company_data.get('company')
                                
                            current_company = CurrentCompany(
                                company=company,
                                position=company_data.get('position', ''),
                                description=company_data.get('description', ''),
                                joined=company_data.get('joined', 0)
                            )
                            current_companies.append(current_company)
                        
                        user = LinkedinSearchUser(
                            internal_id=internal_id,
                            urn=urn,
                            name=item.get('name', ''),
                            url=item.get('url', ''),
                            image=item.get('image', ''),
                            headline=item.get('headline', ''),
                            location=item.get('location', ''),
                            is_premium=item.get('is_premium', False),
                            current_companies=current_companies
                        )
                        users.append(user)
                    except Exception as e:
                        print(f"Error processing user data: {e}")
                        continue
                        
            return users
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def search_linkedin_jobs(self,
                           keywords: Optional[str] = None,
                           companies: Optional[List[str]] = None,
                           locations: Optional[List[str]] = None,
                           functions: Optional[List[str]] = None,
                           experience_levels: Optional[List[str]] = None,
                           job_types: Optional[List[str]] = None,
                           industries: Optional[List[str]] = None,
                           posted_date: Optional[str] = None,
                           count: int = 100,
                           timeout: Optional[int] = 300,
                           request_id: Optional[str] = None) -> List[LinkedinSearchJob]:
        """
        Search LinkedIn job postings using Horizon Data Wave API.
        
        Args:
            keywords (str, optional): Search keywords
            companies (List[str], optional): Company URNs or names
            locations (List[str], optional): Location URNs
            functions (List[str], optional): Job function URNs
            experience_levels (List[str], optional): Experience level URNs
            job_types (List[str], optional): Job type URNs
            industries (List[str], optional): Industry URNs
            posted_date (str, optional): Posted date filter
            count (int, optional): Maximum number of results. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinSearchJob]: List of LinkedIn job search results
        """
        endpoint = f"{self.base_url}/linkedin/search/jobs"
        headers = self._get_headers(request_id)
        
        payload = {
            "count": count,
            "timeout": timeout
        }
        
        # Add optional parameters
        if keywords:
            payload["keywords"] = keywords
        if companies:
            payload["companies"] = companies
        if locations:
            payload["locations"] = locations
        if functions:
            payload["functions"] = functions
        if experience_levels:
            payload["experience_levels"] = experience_levels
        if job_types:
            payload["job_types"] = job_types
        if industries:
            payload["industries"] = industries
        if posted_date:
            payload["posted_date"] = posted_date
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        company = None
                        if item.get('company') and isinstance(item['company'], dict):
                            company_urn = URN(type=item['company']['urn']['type'], value=item['company']['urn']['value'])
                            company = Company(
                                urn=company_urn,
                                url=item['company'].get('url'),
                                name=item['company'].get('name'),
                                image=item['company'].get('image'),
                                industry=item['company'].get('industry')
                            )
                        
                        job = LinkedinSearchJob(
                            urn=urn,
                            title=item.get('title'),
                            company=company,
                            location=item.get('location'),
                            posted_at=item.get('posted_at')
                        )
                        jobs.append(job)
                    except Exception as e:
                        print(f"Error processing job data: {e}")
                        continue
                        
            return jobs
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def search_linkedin_educations(self, 
                                 name: str,
                                 count: int = 100,
                                 timeout: Optional[int] = 300,
                                 request_id: Optional[str] = None) -> List[Company]:
        """
        Search LinkedIn educations using Horizon Data Wave API.
        
        Args:
            name (str): Education name string
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scrapping execution timeout (in seconds)
            
        Returns:
            List[Company]: List of Company objects containing education search results
        """
        endpoint = f"{self.base_url}/linkedin/search/educations"

        print(endpoint)
        
        payload = {
            "name": name,
            "count": count,
            "timeout": timeout
        }
        
        try:
            headers = self._get_headers(request_id)
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Process the response and convert to Company objects
            companies = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Create URN object
                        urn = URN(
                            type=item['urn']['type'],
                            value=item['urn']['value']
                        )
                        
                        # Create Company object
                        company = Company(
                            urn=urn,
                            name=item.get('name', ''),
                            image=item.get('image', ''),
                            headline=item.get('headline', '')
                        )
                        companies.append(company)
                    except Exception as e:
                        print(f"Error processing education data: {e}")
                        continue
                        
            return companies
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")


    def search_locations(self, 
                         name: str,
                         count: int = 100,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[Location]:
        """
        Search locations using Horizon Data Wave API.
        
        This method is used to find location URNs for use in company/people searches.
        Results are cached for 1 year to avoid repeated API calls.
        
        Args:
            name (str): Location name to search for (country, state, city, or region)
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[Location]: List of Location objects with URNs
            
        Example location URNs:
            - United States: urn:li:geo:103644278
            - San Francisco Bay Area: urn:li:geo:90000084
            - New York, United States: urn:li:geo:105080838
            - California, United States: urn:li:geo:102095887
            - United Kingdom: urn:li:geo:101165590
            
        Usage:
            locations = hdw.search_locations("United States", count=1)
            # Use the URN for company/people search:
            location_urn = f"urn:li:geo:{locations[0].urn.value}"
        """
        endpoint = f"{self.base_url}/linkedin/search/locations"

        payload = {
            "name": name,
            "count": count,
            "timeout": timeout
        }
        
        try:
            headers = self._get_headers(request_id)
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Process the response and convert to Location objects
            locations = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Create URN object
                        urn = URN(
                            type=item['urn']['type'],
                            value=item['urn']['value']
                        )
                        
                        # Create Location object
                        location = Location(
                            urn=urn,
                            name=item.get('name', ''),
                            type=item.get('type', '')
                        )
                        locations.append(location)
                    except Exception as e:
                        print(f"Error processing location data: {e}")
                        continue
                        
            return locations
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def search_industries(self, 
                         name: str,
                         count: int = 100,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[Industry]:
        """
        Search industries using Horizon Data Wave API.
        
        This method is used to find industry URNs for use in company/people searches.
        Results are cached for 1 year to avoid repeated API calls.
        
        Args:
            name (str): Industry name to search for (e.g., "Software", "Technology", "Healthcare")
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[Industry]: List of Industry objects with URNs
            
        Example industry URNs:
            - Software Development: urn:li:industry:4
            - Technology, Information and Internet: urn:li:industry:6
            - Financial Services: urn:li:industry:43
            - Healthcare: urn:li:industry:14
            
        Usage:
            industries = hdw.search_industries("Software", count=5)
            # Use the URN for company search:
            industry_urn = f"urn:li:industry:{industries[0].urn.value}"
        """
        endpoint = f"{self.base_url}/linkedin/search/industries"

        payload = {
            "name": name,
            "count": count,
            "timeout": timeout
        }

        try:
            headers = self._get_headers(request_id)
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            industries = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Create URN object
                        urn = URN(
                            type=item['urn']['type'],
                            value=item['urn']['value']
                        )
                        
                        # Create Industry object
                        industry = Industry(
                            urn=urn,
                            name=item.get('name', ''),
                            type=item.get('type', '')
                        )
                        industries.append(industry)
                    except Exception as e:  
                        print(f"Error processing industry data: {e}")
                        continue
                        
            return industries
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def search_companies(self, 
                         keywords: Optional[str] = None,
                         count: int = 100,
                         locations: Optional[List[str]] = None,
                         industry: Optional[List[str]] = None,
                         employee_count: Optional[List[str]] = None,
                         timeout: Optional[int] = 300,
                         request_id: Optional[str] = None) -> List[Company]:
        """
        Search companies using Horizon Data Wave API.
        
        This method searches for companies using various filters. All filter parameters
        use specific URN formats or enum values.
        
        Args:
            keywords (str, optional): Search keywords (e.g., "B2B SaaS", "AI startup")
            count (int, optional): Maximum number of results to return. Defaults to 100.
            locations (List[str], optional): List of location URNs from search_locations()
                Example: ["urn:li:geo:103644278"] for United States
            industry (List[str], optional): List of industry URNs from search_industries()
                Example: ["urn:li:industry:4"] for Software Development
            employee_count (List[str], optional): List of employee count ranges.
                MUST use these exact enum values:
                - "1-10"
                - "11-50"
                - "51-200"
                - "201-500"
                - "501-1000"
                - "1001-5000"
                - "5001-10000"
                - "10001+"
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[Company]: List of Company objects with LinkedIn data
            
        Example usage:
            # First get URNs
            industries = hdw.search_industries("Software", count=1)
            locations = hdw.search_locations("United States", count=1)
            
            # Then search companies
            companies = hdw.search_companies(
                keywords="B2B SaaS",
                industry=[f"urn:li:industry:{industries[0].urn.value}"],
                locations=[f"urn:li:geo:{locations[0].urn.value}"],
                employee_count=["51-200", "201-500"],
                count=10
            )
        """
        endpoint = f"{self.base_url}/linkedin/search/companies"

        payload = {
            "keywords": keywords,
            "count": count,
            "timeout": timeout
        }
        
        if locations is not None:
            payload["locations"] = locations
            
        if industry is not None:
            payload["industry"] = industry
            
        if employee_count is not None:
            payload["employee_count"] = employee_count

        try:
            headers = self._get_headers(request_id)
            response = self.session.post(endpoint, headers=headers, json=payload)
            print(response.headers)
            response.raise_for_status()
            data = response.json()
            
            # Process the response and convert to Company objects
            companies = []
            if isinstance(data, list):
                for item in data:
                    try:
                        # Create URN object
                        urn = URN(
                            type=item['urn']['type'],
                            value=item['urn']['value']
                        )
                        
                        # Create Company object
                        company = Company(
                            urn=urn,
                            url=item.get('url', ''),
                            name=item.get('name', ''),
                            image=item.get('image', ''),
                            industry=item.get('industry', ''),
                            alias=item.get('alias', '')
                        )
                        companies.append(company)
                    except Exception as e:
                        print(f"Error processing company data: {e}")
                        continue
                        
            return companies
        except requests.exceptions.RequestException as e:
            error_msg = f"Error making request to Horizon Data Wave API: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                x_error = e.response.headers.get('x-error')
                if x_error:
                    error_msg += f"\nDetailed error: {x_error}"
            raise Exception(error_msg)
            

    def search_nav_search_users(self, 
                                keywords: Optional[str] = None, 
                                current_titles: Optional[List[str]] = None, 
                                locations: Optional[List[str]] = None, 
                                educations: Optional[Union[List[str], Dict[str, Union[str, List[str]]]]] = None, 
                                functions: Optional[List[str]] = None, 
                                levels: Optional[List[str]] = None,
                                company_sizes: Optional[List[str]] = None, 
                                company_locations: Optional[List[str]] = None, 
                                current_companies: Optional[List[str]] = None, 
                                past_companies: Optional[List[str]] = None, 
                                industry: Optional[List[str]] = None, 
                                is_posted_on_linkedin: Optional[bool] = None,
                                count: int = 100, 
                                timeout: Optional[int] = 300,
                                request_id: Optional[str] = None) -> List[LinkedinSearchUser]:
        """
        Search Nav search users using Horizon Data Wave API.
        
        Args:
            keywords (str, optional): Search keywords
            current_titles (List[str], optional): Current titles
            locations (List[str], optional): Locations
            educations (Union[List[str], Dict[str, Union[str, List[str]]]], optional): 
                Either a list of education URNs or a dictionary with "by name" and/or "list" keys
                Example: {"by name": "Harvard", "list": ["urn:li:company:96"]}
            functions (List[str], optional): Functions
            levels (List[str], optional): Levels
            company_sizes (List[str], optional): Company sizes
            company_locations (List[str], optional): Company locations
            current_companies (List[str], optional): Current companies
            past_companies (List[str], optional): Past companies
            industry (List[str], optional): Industry
            is_posted_on_linkedin (bool, optional): Search only users who recently posted on LinkedIn
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Timeout in seconds. Defaults to 300.
            
        Returns:
            List[LinkedinSearchUser]: List of LinkedinSearchUser objects containing search results
        """
        endpoint = f"{self.base_url}/linkedin/sn_search/users"

        payload = {
            "count": count,
        }
        
        if keywords is not None:
            payload["keywords"] = keywords
        if current_titles is not None:
            payload["current_titles"] = current_titles
        if locations is not None:
            payload["locations"] = locations
        if educations is not None:
            # Handle both list format and dictionary format for educations
            if isinstance(educations, list):
                payload["education"] = educations
            elif isinstance(educations, dict):
                payload["education"] = educations
        if functions is not None:
            payload["functions"] = functions
        if levels is not None:
            payload["levels"] = levels
        if company_sizes is not None:
            payload["company_sizes"] = company_sizes
        if company_locations is not None:
            payload["company_locations"] = company_locations
        if current_companies is not None:
            payload["current_companies"] = current_companies
        if past_companies is not None:
            payload["past_companies"] = past_companies
        if industry is not None:
            payload["industry"] = industry
        if timeout is not None:
            payload["timeout"] = timeout
        if is_posted_on_linkedin is not None:
            payload["is_posted_on_linkedin"] = is_posted_on_linkedin

        # print(payload)

        try:
            headers = self._get_headers(request_id)
            response = self.session.post(endpoint, headers=headers, json=payload)
            print(response.content)
            
            data = response.json()

            # print(data)

            # Process the response and convert to LinkedInUser objects
            users = []
            
            for user in data:
                print(user)
                try:
                    # Check if user is a dictionary
                    if not isinstance(user, dict):
                        print(f"Skipping invalid user data: {user}")
                        continue

                    # Create URN objects
                    internal_id = URN(
                        type=user['internal_id']['type'],
                        value=user['internal_id']['value']
                    )
                    urn = URN(
                        type=user['urn']['type'],
                        value=user['urn']['value']
                    )
                    
                    # Process current companies
                    current_companies = []
                    for company_data in user.get('current_companies', []):
                        company = None
                        if isinstance(company_data.get('company'), dict):
                            company_urn = URN(
                                type=company_data['company']['urn']['type'],
                                value=company_data['company']['urn']['value']
                            )
                            company = Company(
                                urn=company_urn,
                                url=company_data['company'].get('url'),
                                name=company_data['company'].get('name'),
                                image=company_data['company'].get('image'),
                                industry=company_data['company'].get('industry')
                            )
                        else:
                            company = company_data.get('company')
                            
                        current_company = CurrentCompany(
                            company=company,
                            position=company_data.get('position', ''),
                            description=company_data.get('description', ''),
                            joined=company_data.get('joined', 0)
                        )
                        current_companies.append(current_company)
                    
                    # Create LinkedinSearchUser object
                    user = LinkedinSearchUser(
                        internal_id=internal_id,
                        urn=urn,
                        name=user.get('name', ''),
                        url=user.get('url', ''),
                        image=user.get('image', ''),
                        headline=user.get('headline', ''),
                        location=user.get('location', ''),
                        is_premium=user.get('is_premium', False),
                        current_companies=current_companies
                    )
                    users.append(user)
                except Exception as e:
                    print(f"Error processing user data: {e}")
                    continue
                        
            return users
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")
    
    
    # Miscellaneous Endpoints
    
    def get_linkedin_user_by_email(self,
                                 email: str,
                                 timeout: Optional[int] = 300,
                                 request_id: Optional[str] = None) -> List[LinkedinEmailUser]:
        """
        Get LinkedIn user by email address using Horizon Data Wave API.
        
        Args:
            email (str): Email address to search for
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinEmailUser]: List of LinkedIn users found by email
        """
        endpoint = f"{self.base_url}/linkedin/email/user"
        headers = self._get_headers(request_id)
        
        payload = {
            "email": email,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            users = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        user = LinkedinEmailUser(
                            urn=urn,
                            name=item.get('name'),
                            email=item.get('email')
                        )
                        users.append(user)
                    except Exception as e:
                        print(f"Error processing email user data: {e}")
                        continue
                        
            return users
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    def search_google_companies(self,
                              keywords: str,
                              count: int = 100,
                              timeout: Optional[int] = 300,
                              request_id: Optional[str] = None) -> List[LinkedinGoogleCompany]:
        """
        Bulk search companies by keywords using Google (first result is best match) via Horizon Data Wave API.
        
        Args:
            keywords (str): Search keywords for companies
            count (int, optional): Maximum number of results to return. Defaults to 100.
            timeout (int, optional): Max scraping execution timeout (in seconds). Defaults to 300.
            request_id (str, optional): UUID for request tracking
            
        Returns:
            List[LinkedinGoogleCompany]: List of companies found via Google search
        """
        endpoint = f"{self.base_url}/linkedin/google/company"
        headers = self._get_headers(request_id)
        
        payload = {
            "keywords": keywords,
            "count": count,
            "timeout": timeout
        }
        
        try:
            response = self.session.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            companies = []
            if isinstance(data, list):
                for item in data:
                    try:
                        urn = URN(type=item['urn']['type'], value=item['urn']['value']) if item.get('urn') else None
                        
                        company = LinkedinGoogleCompany(
                            urn=urn,
                            name=item.get('name'),
                            website=item.get('website')
                        )
                        companies.append(company)
                    except Exception as e:
                        print(f"Error processing Google company data: {e}")
                        continue
                        
            return companies
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error making request to Horizon Data Wave API: {str(e)}")

    

# Example usage:
if __name__ == "__main__":
    hdw = HorizonDataWave()

    results = hdw.search_nav_search_users(
        keywords="Phd",
        # educations=["urn:li:company:4522"],
        locations=["urn:li:geo:103644278"],
        count=10
    )
    print(results)
    

