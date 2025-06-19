"""Prospect Agent using Google ADK with external tools."""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from .adk_base_agent import ADKAgent
from models import ICP, Prospect, ProspectScore, Company, Person, Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager
from utils.scoring import ProspectScorer
from integrations import HorizonDataWave, ExaWebsetsAPI, FirecrawlClient


class ADKProspectAgent(ADKAgent):
    """
    Prospect Agent built with Google ADK that searches, scores, and ranks potential leads.
    
    Uses external tools for:
    - Company search via HorizonDataWave
    - People search via Exa 
    - Website analysis via Firecrawl
    """
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None):
        super().__init__(
            agent_name="prospect_agent",
            agent_description="Searches, scores, and ranks potential leads based on ICP criteria using multi-source data",
            config=config,
            cache_manager=cache_manager
        )
        
        # Prospect management
        object.__setattr__(self, 'active_prospects', {})
        object.__setattr__(self, 'search_sessions', {})
        
        # Initialize prospect scorer
        object.__setattr__(self, 'scorer', ProspectScorer(config.scoring.model_dump()))
        
        # Initialize external API clients
        self._setup_external_clients()
        
        # Setup tools - only add what Prospect agent needs
        self.setup_prospect_specific_tools()
        self.setup_prospect_tools()
        
        self.logger.info("ADK Prospect Agent initialized")
    
    def _setup_external_clients(self) -> None:
        """Initialize external API clients."""
        try:
            self.external_clients["horizondatawave"] = HorizonDataWave(cache_enabled=True)
        except ValueError:
            self.logger.warning("HorizonDataWave client not initialized - API key missing")
        
        try:
            self.external_clients["exa"] = ExaWebsetsAPI()
        except ValueError:
            self.logger.warning("Exa client not initialized - API key missing")
        
        try:
            self.external_clients["firecrawl"] = FirecrawlClient(cache_manager=self.cache_manager)
        except ValueError:
            self.logger.warning("Firecrawl client not initialized - API key missing")
    
    def setup_prospect_specific_tools(self) -> None:
        """Setup only the external tools that Prospect agent needs."""
        # Prospect agent needs all people search tools for finding prospects
        self.setup_people_search_tools()
        
        # Prospect agent needs company search for matching companies with people
        self.setup_company_search_tools()
        
        # Prospect agent occasionally uses web scraping for enrichment
        self.setup_web_scraping_tools()
        
        self.logger.info("Prospect-specific external tools configured", tool_count=len(self.tools))
    
    def setup_prospect_tools(self) -> None:
        """Setup prospect-specific tools."""
        
        self.add_external_tool(
            name="search_prospects_multi_source",
            description="Search for prospects using multiple data sources (HDW + Exa). Use when looking for leads that match ICP criteria.",
            func=self.search_prospects_multi_source
        )
        
        self.add_external_tool(
            name="score_prospect_against_icp",
            description="Score a prospect against ICP criteria. Use when evaluating prospect quality and fit.",
            func=self.score_prospect_against_icp
        )
        
        self.add_external_tool(
            name="rank_prospects_by_score",
            description="Rank and filter prospects by score and criteria. Use when prioritizing prospects for outreach.",
            func=self.rank_prospects_by_score
        )
        
        self.add_external_tool(
            name="generate_prospect_insights",
            description="Generate insights and recommendations for prospects. Use when analyzing prospect data or creating reports.",
            func=self.generate_prospect_insights
        )
        
        self.add_external_tool(
            name="enrich_prospect_data",
            description="Enrich prospect data with additional information from websites. Use when more context is needed about a prospect.",
            func=self.enrich_prospect_data
        )
    
    async def search_prospects_multi_source(
        self,
        icp_criteria: Dict[str, Any],
        search_limit: int = 50,
        sources: Optional[List[str]] = None,
        location_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for prospects using multiple data sources.
        
        Args:
            icp_criteria: ICP criteria to match against
            search_limit: Maximum number of prospects to find
            sources: List of sources to use (hdw, exa)
            location_filter: Optional location filter
            
        Returns:
            Dictionary with prospect search results
        """
        try:
            if sources is None:
                sources = ["hdw", "exa"]
            
            self.logger.info("Starting multi-source prospect search", limit=search_limit, sources=sources)
            
            all_prospects = []
            companies_found = []
            people_found = []
            
            # Build search queries from ICP
            industries = icp_criteria.get("industries", [])
            target_roles = icp_criteria.get("target_roles", [])
            company_sizes = icp_criteria.get("company_criteria", {}).get("company_size", {}).get("values", [])
            
            # Convert company sizes to HDW format
            hdw_employee_counts = []
            for size in company_sizes:
                # Map ICP sizes to HDW employee_count enum values
                size_map = {
                    "1-10 employees": "1-10",
                    "11-50 employees": "11-50",
                    "51-200 employees": "51-200",
                    "201-500 employees": "201-500",
                    "501-1000 employees": "501-1000",
                    "1001-5000 employees": "1001-5000",
                    "5001-10000 employees": "5001-10000",
                    "10000+ employees": "10001+"
                }
                if size in size_map:
                    hdw_employee_counts.append(size_map[size])
            
            # Search people via HorizonDataWave using search_nav_search_users
            if "hdw" in sources and "horizondatawave" in self.external_clients:
                hdw_client = self.external_clients["horizondatawave"]
                
                # First, search for industry URNs
                industry_urns = []
                for industry_name in industries[:2]:  # Limit to top 2 for cost efficiency
                    try:
                        # Use cached industry searches
                        industry_results = hdw_client.search_industries(name=industry_name, count=1)
                        if industry_results:
                            industry_urn = f"urn:li:industry:{industry_results[0].urn.value}"
                            industry_urns.append(industry_urn)
                            self.logger.info(f"Found industry URN for '{industry_name}': {industry_urn}")
                    except Exception as e:
                        self.logger.warning(f"Could not find industry URN for '{industry_name}': {e}")
                
                # Search for location URNs if location filter provided
                location_urns = []
                if location_filter:
                    try:
                        location_results = hdw_client.search_locations(name=location_filter, count=1)
                        if location_results:
                            location_urn = f"urn:li:geo:{location_results[0].urn.value}"
                            location_urns.append(location_urn)
                            self.logger.info(f"Found location URN for '{location_filter}': {location_urn}")
                    except Exception as e:
                        self.logger.warning(f"Could not find location URN for '{location_filter}': {e}")
                
                # Map seniority levels from ICP to HDW nav search format
                hdw_levels = []
                person_criteria = icp_criteria.get("person_criteria", {})
                seniority_values = person_criteria.get("seniority", {}).get("values", [])
                
                # HDW nav search expects different level values:
                # 'Entry', 'Director', 'Owner', 'CXO', 'Vice President', 'Experienced Manager', 
                # 'Entry Manager', 'Strategic', 'Senior' or 'Trainy'
                level_mapping = {
                    "VP": "Vice President",
                    "Director": "Director",
                    "Manager": "Experienced Manager",
                    "Senior": "Senior",
                    "Entry": "Entry",
                    "C-Level": "CXO",
                    "Head": "Director"  # Map Head to Director
                }
                
                for level in seniority_values:
                    if level in level_mapping:
                        hdw_levels.append(level_mapping[level])
                
                # Search people using search_nav_search_users (expensive endpoint)
                try:
                    self.logger.info("Searching for people using HDW search_nav_search_users (expensive endpoint)")
                    
                    # Build keywords from roles and industries
                    keywords = " ".join(target_roles[:2]) if target_roles else "Sales Executive"
                    
                    # Use search_nav_search_users with proper parameters
                    users = hdw_client.search_nav_search_users(
                        keywords=keywords,
                        current_titles=target_roles[:3] if target_roles else None,
                        locations=location_urns if location_urns else None,
                        industry=industry_urns if industry_urns else None,
                        levels=hdw_levels if hdw_levels else None,
                        company_sizes=hdw_employee_counts if hdw_employee_counts else None,
                        count=min(search_limit, 10),  # Limit for cost efficiency
                        timeout=300
                    )
                    
                    # Convert LinkedIn users to our format
                    for user in users:
                        person_data = {
                            "name": user.name,
                            "first_name": user.name.split()[0] if user.name else "Unknown",
                            "last_name": " ".join(user.name.split()[1:]) if user.name and len(user.name.split()) > 1 else "",
                            "title": user.current_companies[0].position if user.current_companies else user.headline,
                            "company": user.current_companies[0].company.name if user.current_companies and user.current_companies[0].company else "Unknown",
                            "linkedin_url": user.url,
                            "location": user.location,
                            "headline": user.headline
                        }
                        people_found.append(person_data)
                        
                        # Also add company if available
                        if user.current_companies and user.current_companies[0].company:
                            companies_found.append(user.current_companies[0].company)
                    
                    self.logger.info(f"Found {len(users)} people via HDW search_nav_search_users")
                    
                except Exception as e:
                    self.logger.error(f"Error searching people with HDW: {e}")
                    # Fallback to basic search
                    hdw_result = await self.search_people_hdw(
                        query=keywords,
                        limit=min(search_limit, 5),
                        current_titles=target_roles[:2] if target_roles else None
                    )
                    if hdw_result["status"] == "success":
                        people_found.extend(hdw_result["people"])
            
            # Search people via Exa using websets with enrichments
            if "exa" in sources and "exa" in self.external_clients:
                from integrations.exa_websets import ExaExtractor
                try:
                    extractor = ExaExtractor(cache_manager=self.cache_manager)
                    
                    # Build enhanced search query incorporating more ICP criteria
                    # Start with roles and industries
                    search_parts = []
                    
                    # Add role and industry combinations
                    if target_roles and industries:
                        role_industry_query = f"People who are {' OR '.join(target_roles[:2])} at {' OR '.join(industries[:2])} companies"
                        search_parts.append(role_industry_query)
                    
                    # Add buying signals as search modifiers
                    buying_signals = icp_criteria.get("buying_signals", [])
                    if buying_signals:
                        signal_keywords = []
                        for signal in buying_signals[:2]:  # Limit to top 2
                            if "budget" in signal.lower():
                                signal_keywords.extend(["budget allocated", "funding secured"])
                            elif "looking" in signal.lower() or "evaluating" in signal.lower():
                                signal_keywords.extend(["evaluating solutions", "vendor selection"])
                            elif "hiring" in signal.lower():
                                signal_keywords.extend(["hiring", "team expansion", "growing team"])
                            elif "implementing" in signal.lower():
                                signal_keywords.extend(["implementing new", "digital transformation"])
                        
                        if signal_keywords:
                            search_parts.append(f"companies {' OR '.join(signal_keywords[:2])}")
                    
                    # Add tech stack if relevant
                    tech_stack = icp_criteria.get("tech_stack", [])
                    if tech_stack:
                        search_parts.append(f"using {' OR '.join(tech_stack[:2])}")
                    
                    
                    # Combine all search parts
                    search_query = " ".join(search_parts)
                    
                    # Add location filter if provided
                    if location_filter:
                        search_query += f" in {location_filter}"
                    
                    # Limit query length for API compatibility
                    if len(search_query) > 500:
                        # Fallback to simpler query if too long
                        search_query = f"People who are {' OR '.join(target_roles[:2])} at {' OR '.join(industries[:2])} companies"
                        if location_filter:
                            search_query += f" in {location_filter}"
                    
                    self.logger.info(f"Creating enhanced Exa webset for people search: {search_query}")
                    
                    # Define enrichments for people data
                    enrichments = [
                        {
                            "description": "Person full name",
                            "format": "text"
                        },
                        {
                            "description": "Current job title or role",
                            "format": "text"
                        },
                        {
                            "description": "Current company name",
                            "format": "text"
                        },
                        {
                            "description": "LinkedIn profile URL",
                            "format": "text"
                        },
                        {
                            "description": "Email address if available",
                            "format": "text"
                        },
                        {
                            "description": "Professional background and expertise",
                            "format": "text"
                        }
                    ]
                    
                    # Extract people using Exa websets
                    exa_people = extractor.extract_people(
                        search_query=search_query,
                        enrichments=enrichments,
                        count=min(search_limit, 20)  # Exa can handle more results
                    )
                    
                    people_found.extend(exa_people)
                    self.logger.info(f"Found {len(exa_people)} people via Exa websets with enhanced search")
                    
                except Exception as e:
                    self.logger.error(f"Error searching people with Exa: {e}")
            
            # Create prospects from people found
            # No need to match companies separately since people already have company info
            prospects = []
            for person in people_found[:search_limit]:
                # If we have company info from the person, use it
                company_info = None
                if isinstance(person, dict):
                    company_name = person.get("company", "Unknown")
                    # Try to find matching company from companies_found
                    for company in companies_found:
                        if hasattr(company, 'name') and company.name.lower() in company_name.lower():
                            company_info = company
                            break
                    
                    # If no match, create basic company info
                    if not company_info:
                        company_info = {
                            "name": company_name,
                            "industry": "Unknown"
                        }
                
                prospects.append({
                    "person": person,
                    "company": company_info,
                    "source": "multi_source_search"
                })
            
            # Score prospects against ICP
            scored_prospects = []
            for prospect in prospects[:search_limit]:
                scoring_result = await self.score_prospect_against_icp(
                    prospect_data=prospect,
                    icp_criteria=icp_criteria
                )
                if scoring_result["status"] == "success":
                    scored_prospects.append(scoring_result["prospect"])
            
            # Store prospects
            for prospect_dict in scored_prospects:
                # Prospects are now always dicts from scoring
                # Create a new prospect object from the scored dict
                prospect_obj = Prospect(**prospect_dict)
                self.active_prospects[prospect_obj.id] = prospect_obj
            
            self.logger.info("Multi-source search completed", prospects_found=len(scored_prospects))
            
            return {
                "status": "success",
                "prospects": [p.model_dump() if hasattr(p, 'model_dump') else p for p in scored_prospects],
                "sources_used": sources,
                "companies_found": len(companies_found),
                "people_found": len(people_found)
            }
            
        except Exception as e:
            self.logger.error("Error in multi-source prospect search", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def score_prospect_against_icp(
        self,
        prospect_data: Dict[str, Any],
        icp_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Score a prospect against ICP criteria.
        
        Args:
            prospect_data: Prospect information
            icp_criteria: ICP criteria for scoring
            
        Returns:
            Dictionary with scored prospect
        """
        try:
            # Create prospect object if needed
            if isinstance(prospect_data, dict):
                prospect = self._dict_to_prospect(prospect_data)
            else:
                prospect = prospect_data
            
            # Use LLM-based scoring method
            score = await self._calculate_prospect_score(prospect, icp_criteria)
            
            prospect.score = score
            
            # Convert prospect to dict to avoid serialization issues
            prospect_dict = prospect.model_dump() if hasattr(prospect, 'model_dump') else prospect.__dict__
            
            return {
                "status": "success",
                "prospect": prospect_dict,
                "score_breakdown": score.model_dump() if hasattr(score, 'model_dump') else score
            }
            
        except Exception as e:
            self.logger.error("Error scoring prospect", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def rank_prospects_by_score(
        self,
        prospect_ids: List[str],
        ranking_criteria: Dict[str, Any],
        limit: int = 10
    ) -> Dict[str, Any]:
        """Rank prospects by score and apply filters.
        
        Args:
            prospect_ids: List of prospect IDs to rank
            ranking_criteria: Criteria for ranking and filtering
            limit: Maximum number of prospects to return
            
        Returns:
            Dictionary with ranked prospects
        """
        try:
            # Get prospects
            prospects = []
            for prospect_id in prospect_ids:
                if prospect_id in self.active_prospects:
                    prospects.append(self.active_prospects[prospect_id])
            
            # Apply filters
            min_score = ranking_criteria.get("min_score", 0.0)
            filtered_prospects = [
                p for p in prospects 
                if p.score and p.score.total_score >= min_score
            ]
            
            # Sort by score
            sort_by = ranking_criteria.get("sort_by", "total_score")
            if sort_by == "total_score":
                sorted_prospects = sorted(
                    filtered_prospects,
                    key=lambda p: p.score.total_score if p.score else 0,
                    reverse=True
                )
            else:
                sorted_prospects = filtered_prospects
            
            # Apply limit
            top_prospects = sorted_prospects[:limit]
            
            return {
                "status": "success",
                "prospects": [p.model_dump() for p in top_prospects],
                "total_evaluated": len(prospects),
                "total_after_filters": len(filtered_prospects),
                "ranking_criteria": ranking_criteria
            }
            
        except Exception as e:
            self.logger.error("Error ranking prospects", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def generate_prospect_insights(
        self,
        prospect_ids: List[str],
        analysis_type: str = "summary"
    ) -> Dict[str, Any]:
        """Generate insights about prospects.
        
        Args:
            prospect_ids: List of prospect IDs to analyze
            analysis_type: Type of analysis (summary, detailed, trends)
            
        Returns:
            Dictionary with prospect insights
        """
        try:
            prospects = [
                self.active_prospects[pid] for pid in prospect_ids
                if pid in self.active_prospects
            ]
            
            if not prospects:
                return {"status": "error", "error_message": "No prospects found"}
            
            # Generate insights using AI
            prospects_data = [p.model_dump() for p in prospects[:5]]  # Limit for analysis
            
            insights_prompt = f"""
            Analyze these prospects and provide insights:
            
            Prospects Data:
            {json.dumps(prospects_data, indent=2)}
            
            Analysis Type: {analysis_type}
            
            Provide insights on:
            1. Quality distribution (high/medium/low scores)
            2. Industry patterns
            3. Role patterns
            4. Geographic distribution
            5. Recommendations for outreach
            6. Potential challenges or concerns
            
            Return as structured JSON with insights and recommendations.
            """
            
            insights = await self.process_message(insights_prompt)
            
            return {
                "status": "success",
                "analysis_type": analysis_type,
                "prospects_analyzed": len(prospects),
                "insights": insights
            }
            
        except Exception as e:
            self.logger.error("Error generating prospect insights", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def enrich_prospect_data(
        self,
        prospect_id: str,
        enrichment_sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Enrich prospect data with additional information.
        
        Args:
            prospect_id: ID of prospect to enrich
            enrichment_sources: Sources to use for enrichment
            
        Returns:
            Dictionary with enriched prospect data
        """
        try:
            prospect = self.active_prospects.get(prospect_id)
            if not prospect:
                return {"status": "error", "error_message": "Prospect not found"}
            
            if enrichment_sources is None:
                enrichment_sources = ["website", "linkedin"]
            
            enrichment_data = {}
            
            # Enrich with website data
            if "website" in enrichment_sources and prospect.company.domain:
                website_result = await self.scrape_website_firecrawl(prospect.company.domain)
                if website_result["status"] == "success":
                    enrichment_data["website_analysis"] = website_result["content"][:1000]
            
            # Enrich with LinkedIn data (via HDW)
            if "linkedin" in enrichment_sources and prospect.company.name:
                linkedin_result = self.search_companies_hdw(
                    query=prospect.company.name,
                    limit=1
                )
                if linkedin_result["status"] == "success" and linkedin_result["companies"]:
                    enrichment_data["linkedin_data"] = linkedin_result["companies"][0]
            
            # Update prospect with enrichment data
            if enrichment_data:
                prospect.metadata.update(enrichment_data)
                self.active_prospects[prospect_id] = prospect
            
            return {
                "status": "success",
                "prospect_id": prospect_id,
                "enrichment_data": enrichment_data,
                "sources_used": enrichment_sources
            }
            
        except Exception as e:
            self.logger.error("Error enriching prospect data", prospect_id=prospect_id, error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    def _match_companies_and_people(
        self,
        companies: List[Dict[str, Any]],
        people: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Match companies with people to create prospects."""
        prospects = []
        
        # Simple matching strategy - pair companies with people
        for i, company in enumerate(companies):
            # Try to find a person from the same company or similar
            matched_person = None
            # Handle both dict and LinkedinCompany objects
            if hasattr(company, 'name'):
                company_name = company.name.lower()
                company_dict = company.__dict__()
            else:
                company_name = company.get("name", "").lower()
                company_dict = company
            
            for person in people:
                person_company = person.get("company", "").lower()
                if company_name in person_company or person_company in company_name:
                    matched_person = person
                    break
            
            # If no direct match, use person by index
            if not matched_person and i < len(people):
                matched_person = people[i]
            
            if matched_person:
                prospects.append({
                    "company": company_dict,
                    "person": matched_person,
                    "match_type": "name_match" if company_name in matched_person.get("company", "").lower() else "index_match"
                })
        
        return prospects
    
    def _dict_to_prospect(self, prospect_data: Dict[str, Any]) -> Prospect:
        """Convert dictionary to Prospect object."""
        
        # Extract company data
        company_data = prospect_data.get("company", {})
        
        # Handle HDW Company objects vs dictionaries
        if hasattr(company_data, '__class__') and company_data.__class__.__name__ in ['Company', 'LinkedinCompany']:
            # It's an HDW Company or LinkedinCompany object, extract its attributes
            company = Company(
                name=getattr(company_data, 'name', 'Unknown'),
                industry=getattr(company_data, 'industry', 'Unknown'),
                employee_range=str(getattr(company_data, 'employee_count', '')) if hasattr(company_data, 'employee_count') else None,
                revenue=getattr(company_data, 'revenue', None),
                headquarters=getattr(company_data, 'headquarters', None),
                domain=getattr(company_data, 'website', None),
                linkedin_url=getattr(company_data, 'url', None)
            )
        else:
            # It's a dictionary
            # Handle industry field which might be a dict
            industry = company_data.get("industry") if isinstance(company_data, dict) else "Unknown"
            if isinstance(industry, dict):
                industry = industry.get("value", "Unknown")
            
            company = Company(
                name=company_data.get("name", "Unknown") if isinstance(company_data, dict) else "Unknown",
                industry=industry,
                employee_range=company_data.get("size") or company_data.get("employee_range") or company_data.get("employee_count_range") if isinstance(company_data, dict) else None,
                revenue=company_data.get("revenue") if isinstance(company_data, dict) else None,
                headquarters=company_data.get("location") or company_data.get("headquarters") or company_data.get("headquarter_location") if isinstance(company_data, dict) else None,
                domain=company_data.get("website") or company_data.get("domain") if isinstance(company_data, dict) else None,
                linkedin_url=company_data.get("linkedin_url") or company_data.get("url") if isinstance(company_data, dict) else None
            )
        
        # Extract person data
        person_data = prospect_data.get("person", {})
        person = Person(
            first_name=person_data.get("first_name", person_data.get("name", "Unknown").split()[0]),
            last_name=person_data.get("last_name", " ".join(person_data.get("name", "Unknown").split()[1:])),
            title=person_data.get("title") or person_data.get("role") or person_data.get("job_title"),
            email=person_data.get("email"),
            linkedin_url=person_data.get("linkedin_url"),
            department=person_data.get("department"),
            seniority_level=person_data.get("seniority_level")
        )
        
        # Create prospect with default score
        default_score = ProspectScore(
            total_score=0.5,
            company_match_score=0.5,
            person_match_score=0.5,
            criteria_scores={}
        )
        
        prospect = Prospect(
            id=f"prospect_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}",
            company=company,
            person=person,
            score=default_score,
            source="multi_source_search"
        )
        
        return prospect
    
    async def _calculate_prospect_score(
        self,
        prospect: Prospect,
        icp_criteria: Dict[str, Any]
    ) -> ProspectScore:
        """Calculate prospect score using LLM-based evaluation."""
        
        # For now, use the fallback scoring to ensure the workflow works
        # TODO: Fix LLM scoring integration later
        return self._fallback_scoring(prospect, icp_criteria)
    
    def _fallback_scoring(self, prospect: Prospect, icp_criteria: Dict[str, Any]) -> ProspectScore:
        """Simple fallback scoring if LLM fails."""
        company_score = 0.5
        person_score = 0.5
        criteria_scores = {}
        
        # Basic industry matching
        prospect_industry = prospect.company.industry or ""
        target_industries = icp_criteria.get("industries", [])
        if any(industry.lower() in prospect_industry.lower() for industry in target_industries):
            company_score += 0.2
            criteria_scores["industry"] = 0.8
        
        # Basic role matching
        prospect_title = prospect.person.title or ""
        target_roles = icp_criteria.get("target_roles", [])
        if any(role.lower() in prospect_title.lower() for role in target_roles):
            person_score += 0.3
            criteria_scores["job_title"] = 0.9
        
        total_score = (company_score + person_score) / 2
        
        return ProspectScore(
            total_score=min(total_score, 1.0),
            company_match_score=min(company_score, 1.0),
            person_match_score=min(person_score, 1.0),
            criteria_scores=criteria_scores
        )
    
    # Required abstract method implementations
    
    def get_capabilities(self) -> List[str]:
        """Return list of Prospect agent capabilities."""
        return [
            "search_prospects_multi_source",
            "score_prospect_against_icp",
            "rank_prospects_by_score",
            "generate_prospect_insights",
            "enrich_prospect_data",
            "search_companies_hdw",
            "search_industries_hdw",
            "search_locations_hdw",
            "search_people_hdw",
            "search_people_exa",
            "search_people_nav_hdw",
            "scrape_website_firecrawl"
        ]
    
    async def execute_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute prospect-related tasks."""
        
        task_handlers = {
            "search_prospects": self._handle_search_prospects_task,
            "score_prospects": self._handle_score_prospects_task,
            "rank_prospects": self._handle_rank_prospects_task,
            "generate_report": self._handle_generate_report_task
        }
        
        handler = task_handlers.get(task_type)
        if handler:
            return await handler(task_data, conversation_id)
        else:
            return {"status": "error", "error_message": f"Unknown task type: {task_type}"}
    
    async def process_query(
        self,
        query: str,
        context: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> str:
        """Process prospect-related queries."""
        
        # Use Google ADK to process the query with tools
        return await self.process_message(query, conversation_id, context)
    
    # Task handlers
    
    async def _handle_search_prospects_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle prospect search task."""
        
        icp_id = task_data.get("icp_id")
        search_limit = task_data.get("limit", 50)
        sources = task_data.get("sources", ["hdw", "exa"])
        
        # Get ICP criteria (this would normally come from ICP Agent)
        icp_criteria = task_data.get("icp_criteria", {})
        
        return await self.search_prospects_multi_source(
            icp_criteria=icp_criteria,
            search_limit=search_limit,
            sources=sources
        )
    
    async def _handle_score_prospects_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle prospect scoring task."""
        
        prospect_ids = task_data.get("prospect_ids", [])
        icp_criteria = task_data.get("icp_criteria", {})
        
        scored_prospects = []
        for prospect_id in prospect_ids:
            if prospect_id in self.active_prospects:
                prospect = self.active_prospects[prospect_id]
                score_result = await self.score_prospect_against_icp(
                    prospect_data=prospect.model_dump(),
                    icp_criteria=icp_criteria
                )
                if score_result["status"] == "success":
                    scored_prospects.append(score_result["prospect"])
        
        return {
            "status": "success",
            "scored_prospects": [p.model_dump() if hasattr(p, 'model_dump') else p for p in scored_prospects]
        }
    
    async def _handle_rank_prospects_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle prospect ranking task."""
        
        prospect_ids = task_data.get("prospect_ids", [])
        ranking_criteria = task_data.get("ranking_criteria", {})
        limit = task_data.get("limit", 10)
        
        return await self.rank_prospects_by_score(
            prospect_ids=prospect_ids,
            ranking_criteria=ranking_criteria,
            limit=limit
        )
    
    async def _handle_generate_report_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle report generation task."""
        
        prospect_ids = task_data.get("prospect_ids", [])
        report_type = task_data.get("type", "summary")
        
        return await self.generate_prospect_insights(
            prospect_ids=prospect_ids,
            analysis_type=report_type
        )