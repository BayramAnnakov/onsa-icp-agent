"""Prospect Agent using Google ADK with external tools."""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.json_encoder import DateTimeEncoder
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
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None, memory_manager=None):
        super().__init__(
            agent_name="prospect_agent",
            agent_description="Searches, scores, and ranks potential leads based on ICP criteria using multi-source data",
            config=config,
            cache_manager=cache_manager,
            memory_manager=memory_manager
        )
        
        # Prospect management
        object.__setattr__(self, 'active_prospects', {})
        object.__setattr__(self, 'search_sessions', {})
        
        # Initialize prospect scorer
        object.__setattr__(self, 'scorer', ProspectScorer(config.scoring.model_dump()))
        
        # Initialize external API clients
        self._setup_external_clients()
        
        # Setup tools - only add what Prospect agent needs
        self.setup_external_tools()  # This sets up memory tools from parent
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
        
        self.logger.info(f"Prospect-specific external tools configured - Tool_Count: {len(self.tools)}")
    
    def setup_prospect_tools(self) -> None:
        """Setup prospect-specific tools."""
        
        self.add_external_tool(
            name="search_prospects_multi_source",
            description="Search for prospects using multiple data sources (HDW + Exa). Use when looking for leads that match ICP criteria.",
            func=self.search_prospects_multi_source
        )
        
        # Individual scoring tool removed - only batch scoring is used
        
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
    
    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response that may contain explanatory text."""
        import re
        
        # First try to find JSON markdown blocks
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_blocks:
            return json_blocks[0].strip()
        
        # Try to find any markdown code blocks
        code_blocks = re.findall(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if code_blocks:
            for block in code_blocks:
                block = block.strip()
                # Check if this looks like JSON (starts with [ or {)
                if block.startswith('[') or block.startswith('{'):
                    return block
        
        # Try to find JSON array or object in the response
        # Look for content between [ ] or { }
        json_array_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if json_array_match:
            return json_array_match.group(0)
        
        json_object_match = re.search(r'\{.*?\}', response, re.DOTALL)
        if json_object_match:
            return json_object_match.group(0)
        
        # If no structured JSON found, return the response as-is and let json.loads handle the error
        return response.strip()
    
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
            
            self.logger.info(f"Starting multi-source prospect search - Limit: {search_limit}, Sources: {sources}")
            
            # Extract key criteria from ICP
            industries = icp_criteria.get("industries", [])
            target_roles = icp_criteria.get("target_roles", [])
            
            # Extract company sizes from company_criteria
            company_sizes = []
            if "company_criteria" in icp_criteria:
                company_size_criteria = icp_criteria["company_criteria"].get("company_size", {})
                if isinstance(company_size_criteria, dict):
                    company_sizes = company_size_criteria.get("values", [])
                elif isinstance(company_size_criteria, list):
                    company_sizes = company_size_criteria
            
            # Prepare tasks for parallel execution
            search_tasks = []
            
            # Create HDW search task if enabled
            if "hdw" in sources and "horizondatawave" in self.external_clients:
                hdw_task = self._search_hdw_prospects(
                    industries=industries,
                    target_roles=target_roles,
                    company_sizes=company_sizes,
                    location_filter=location_filter,
                    search_limit=search_limit
                )
                search_tasks.append(("hdw", hdw_task))
            
            # Create Exa search task if enabled
            if "exa" in sources and "exa" in self.external_clients:
                exa_task = self._search_exa_prospects(
                    industries=industries,
                    target_roles=target_roles,
                    icp_criteria=icp_criteria,
                    location_filter=location_filter,
                    search_limit=search_limit
                )
                search_tasks.append(("exa", exa_task))
            
            # Execute all search tasks in parallel
            if search_tasks:
                self.logger.info(f"Executing {len(search_tasks)} search tasks in parallel")
                task_results = await asyncio.gather(
                    *[task for _, task in search_tasks],
                    return_exceptions=True
                )
                
                # Process results
                all_prospects = []
                companies_found = []
                people_found = []
                
                for i, (source_name, _) in enumerate(search_tasks):
                    result = task_results[i]
                    if isinstance(result, Exception):
                        self.logger.error(f"Error in {source_name} search: {str(result)}")
                    elif isinstance(result, dict) and result.get("status") == "success":
                        people_found.extend(result.get("people", []))
                        companies_found.extend(result.get("companies", []))
                        self.logger.info(f"{source_name} found {len(result.get('people', []))} people")
            else:
                self.logger.warning("No search tasks to execute")
                all_prospects = []
                companies_found = []
                people_found = []
            
            # Create prospects from people found
            # No need to match companies separately since people already have company info
            prospects = []
            self.logger.info(f"Creating prospects from {len(people_found)} people found")
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
            
            # Batch score prospects against ICP for efficiency
            prospects_to_score = prospects[:search_limit]
            scored_prospects = []
            
            self.logger.info(f"Scoring {len(prospects_to_score)} prospects")
            if prospects_to_score:
                # Use batch scoring for better performance
                batch_result = await self.batch_score_prospects(
                    prospects_data=prospects_to_score,
                    icp_criteria=icp_criteria
                )
                if batch_result["status"] == "success":
                    scored_prospects = batch_result["scored_prospects"]
                else:
                    self.logger.error("Batch scoring failed, skipping prospect scoring")
                    scored_prospects = []
            
            # Store prospects
            for prospect_dict in scored_prospects:
                # Prospects are now always dicts from scoring
                # Check if it's already a Prospect object
                if hasattr(prospect_dict, 'id'):
                    prospect_obj = prospect_dict
                else:
                    # It's a dict, but we need to ensure it has the right structure
                    # The dict from model_dump() already has the right structure
                    try:
                        # First try direct creation
                        prospect_obj = Prospect(**prospect_dict)
                    except Exception as e:
                        self.logger.warning(f"Failed to create Prospect from dict: {e}")
                        # Fallback: recreate from components
                        prospect_obj = self._dict_to_prospect(prospect_dict)
                        if "score" in prospect_dict:
                            # Apply the score if it exists
                            score_data = prospect_dict["score"]
                            if isinstance(score_data, dict):
                                prospect_obj.score = ProspectScore(**score_data)
                            else:
                                prospect_obj.score = score_data
                
                # Debug logging to understand company data
                if prospect_obj.company:
                    self.logger.debug(f"Storing prospect {prospect_obj.id} with company: {prospect_obj.company.name}")
                else:
                    self.logger.warning(f"Prospect {prospect_obj.id} has no company data")
                    
                self.active_prospects[prospect_obj.id] = prospect_obj
            
            self.logger.info(f"Multi-source search completed - Prospects_Found: {len(scored_prospects)}")
            
            return {
                "status": "success",
                "prospects": [p.model_dump() if hasattr(p, 'model_dump') else p for p in scored_prospects],
                "sources_used": sources,
                "companies_found": len(companies_found),
                "people_found": len(people_found)
            }
            
        except Exception as e:
            self.logger.error(f"Error in multi-source prospect search - Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    # Individual scoring removed - only batch scoring is used now
    
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
                    prospect = self.active_prospects[prospect_id]
                    # Debug logging
                    if prospect.company:
                        self.logger.debug(f"Retrieved prospect {prospect_id} with company: {prospect.company.name}")
                    else:
                        self.logger.warning(f"Retrieved prospect {prospect_id} has no company data")
                    prospects.append(prospect)
            
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
            self.logger.error(f"Error ranking prospects - Error: {str(e)}")
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
            {json.dumps(prospects_data, indent=2, cls=DateTimeEncoder)}
            
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
            
            # Use process_json_request to prevent recursive tool calls
            insights_raw = await self.process_json_request(insights_prompt)
            
            # Parse the JSON string to maintain dict structure
            try:
                insights = json.loads(insights_raw) if isinstance(insights_raw, str) else insights_raw
            except (json.JSONDecodeError, TypeError):
                self.logger.warning("Failed to parse prospect insights JSON, using raw string")
                insights = {"raw_insights": insights_raw}
            
            return {
                "status": "success",
                "analysis_type": analysis_type,
                "prospects_analyzed": len(prospects),
                "insights": insights
            }
            
        except Exception as e:
            self.logger.error(f"Error generating prospect insights - Error: {str(e)}")
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
                linkedin_result = await self.search_companies_hdw(
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
            self.logger.error(f"Error enriching prospect data - Prospect_Id: {prospect_id}, Error: {str(e)}")
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
    
    def _get_employee_range(self, employee_count: int) -> str:
        """Convert numeric employee count to range string."""
        if employee_count <= 10:
            return "1-10"
        elif employee_count <= 50:
            return "11-50"
        elif employee_count <= 200:
            return "51-200"
        elif employee_count <= 500:
            return "201-500"
        elif employee_count <= 1000:
            return "501-1000"
        elif employee_count <= 5000:
            return "1001-5000"
        elif employee_count <= 10000:
            return "5001-10000"
        else:
            return "10000+"
    
    def _dict_to_prospect(self, prospect_data: Dict[str, Any]) -> Prospect:
        """Convert dictionary to Prospect object."""
        
        # Extract company data
        company_data = prospect_data.get("company", {})
        
        # Handle HDW Company objects vs dictionaries
        if hasattr(company_data, '__class__') and company_data.__class__.__name__ in ['Company', 'LinkedinCompany']:
            # It's an HDW Company or LinkedinCompany object, extract its attributes
            # Extract employee count if available
            employee_count = getattr(company_data, 'employee_count', None)
            employee_range = None
            if employee_count:
                # Set both employee_count (numeric) and employee_range (string)
                if isinstance(employee_count, (int, float)):
                    employee_range = self._get_employee_range(int(employee_count))
                else:
                    employee_range = str(employee_count)
            
            company = Company(
                name=getattr(company_data, 'name', 'Unknown'),
                industry=getattr(company_data, 'industry', 'Unknown'),
                employee_count=int(employee_count) if employee_count and str(employee_count).isdigit() else None,
                employee_range=employee_range,
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
            
            # Extract employee count from various possible fields
            employee_count = None
            employee_range = None
            
            if isinstance(company_data, dict):
                # Try different field names for employee count
                for field in ['employee_count', 'employees', 'size', 'company_size']:
                    if field in company_data and company_data[field]:
                        value = company_data[field]
                        if isinstance(value, (int, float)):
                            employee_count = int(value)
                            employee_range = self._get_employee_range(employee_count)
                            break
                        elif isinstance(value, str) and value.isdigit():
                            employee_count = int(value)
                            employee_range = self._get_employee_range(employee_count)
                            break
                        elif isinstance(value, str):
                            employee_range = value
                            # Try to extract numeric value from ranges like "50-200"
                            if '-' in value:
                                try:
                                    parts = value.split('-')
                                    employee_count = int(parts[0])
                                except:
                                    pass
            
            company = Company(
                name=company_data.get("name", "Unknown") if isinstance(company_data, dict) else "Unknown",
                industry=industry,
                employee_count=employee_count,
                employee_range=employee_range or company_data.get("employee_range") or company_data.get("employee_count_range") if isinstance(company_data, dict) else None,
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
    
    # Legacy individual scoring methods removed - using only batch scoring now
    
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
    
    async def batch_score_prospects(
        self,
        prospects_data: List[Dict[str, Any]],
        icp_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Batch score multiple prospects in a single LLM call for efficiency.
        
        WARNING: This method uses process_json_request() to prevent infinite recursion.
        If this method is registered as a tool, the agent might call it recursively
        when asked to generate JSON scores.
        
        Args:
            prospects_data: List of prospect information dicts
            icp_criteria: ICP criteria for scoring
            
        Returns:
            Dictionary with list of scored prospects
        """
        try:
            # Convert prospect data to Prospect objects if needed
            prospects = []
            for data in prospects_data:
                if isinstance(data, dict):
                    prospects.append(self._dict_to_prospect(data))
                else:
                    prospects.append(data)
            
            # Create batch scoring prompt
            prospects_info = []
            for i, prospect in enumerate(prospects):
                company_name = prospect.company.name if prospect.company.name else "Unknown"
                industry = prospect.company.industry if prospect.company.industry else "Not specified"
                size = prospect.company.employee_range if prospect.company.employee_range else "Not specified"
                person_name = f"{prospect.person.first_name or 'Unknown'} {prospect.person.last_name or ''}".strip()
                title = prospect.person.title if prospect.person.title else "Not specified"
                seniority = prospect.person.seniority_level if prospect.person.seniority_level else "Not specified"
                
                prospects_info.append(f"""
Prospect {i+1}:
- Company: {company_name}
- Industry: {industry}
- Size: {size}
- Person: {person_name}
- Title: {title}
- Seniority: {seniority}""")
            
            batch_prompt = f"""
Score these {len(prospects)} prospects against the ICP criteria.

IMPORTANT: Return ONLY a JSON array. No explanatory text before or after the JSON.
If data is missing, use these defaults:
- Company size: If unknown, assume it doesn't match size criteria (score 0.3)
- Industry: If unknown, assume partial match (score 0.4)
- Location: If not specified, assume it matches
- Seniority: If not specified, check job title for clues

ICP Criteria:
{json.dumps(icp_criteria, indent=2, cls=DateTimeEncoder)}

Prospects to Score:
{"".join(prospects_info)}

Return ONLY this JSON array structure:
[
    {{
        "prospect_index": 1,
        "company_match_score": 0.0-1.0,
        "person_match_score": 0.0-1.0,
        "total_score": 0.0-1.0,
        "criteria_scores": {{"industry": 0.0-1.0, "company_size": 0.0-1.0, "job_title": 0.0-1.0, "seniority": 0.0-1.0}},
        "reasoning": "brief explanation"
    }},
    ...
]

Scoring guide: Perfect matches 0.9-1.0, good matches 0.7-0.8, okay matches 0.5-0.6, poor matches below 0.5.
"""
            
            # Use process_json_request to prevent recursive tool calls
            try:
                batch_response = await self.process_json_request(batch_prompt)
                
                # Extract JSON from response (handle explanatory text before JSON)
                json_str = self._extract_json_from_response(batch_response)
                scores_data = json.loads(json_str)
                
                # Apply scores to prospects
                scored_prospects = []
                for i, prospect in enumerate(prospects):
                    if i < len(scores_data):
                        score_info = scores_data[i]
                        prospect.score = ProspectScore(
                            total_score=score_info.get("total_score", 0.5),
                            company_match_score=score_info.get("company_match_score", 0.5),
                            person_match_score=score_info.get("person_match_score", 0.5),
                            criteria_scores=score_info.get("criteria_scores", {}),
                            score_explanation=score_info.get("reasoning", "")
                        )
                    else:
                        # Fallback if not enough scores returned
                        prospect.score = ProspectScore(
                            total_score=0.5,
                            company_match_score=0.5,
                            person_match_score=0.5,
                            criteria_scores={}
                        )
                    
                    # Convert to dict for serialization
                    prospect_dict = prospect.model_dump() if hasattr(prospect, 'model_dump') else prospect.__dict__
                    # Debug log to check company data
                    if "company" in prospect_dict and prospect_dict["company"]:
                        self.logger.debug(f"Scored prospect has company: {prospect_dict['company'].get('name', 'NO NAME KEY')}")
                    else:
                        self.logger.warning(f"Scored prospect missing company data")
                    scored_prospects.append(prospect_dict)
                
                self.logger.info(f"Batch scored {len(scored_prospects)} prospects in one LLM call")
                return {
                    "status": "success",
                    "scored_prospects": scored_prospects
                }
                
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON parsing failed in batch scoring - Error: {str(e)} - Raw_Response: {batch_response[:500]} - Extracted_JSON: {json_str[:200]}")
                return {"status": "error", "error_message": f"JSON parsing failed: {str(e)}"}
            except Exception as e:
                self.logger.error(f"Unexpected error in batch scoring - Error: {str(e)}")
                return {"status": "error", "error_message": str(e)}
                
        except Exception as e:
            self.logger.error(f"Error in batch scoring - Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def _search_hdw_prospects(
        self,
        industries: List[str],
        target_roles: List[str],
        company_sizes: List[str],
        location_filter: Optional[str],
        search_limit: int
    ) -> Dict[str, Any]:
        """Search for prospects using HorizonDataWave API."""
        try:
            hdw_client = self.external_clients["horizondatawave"]
            people_found = []
            companies_found = []
            
            self.logger.info(f"HDW search starting - Industries: {industries}, Target roles: {target_roles}, Company sizes: {company_sizes}, Location: {location_filter}")
            
            # Convert company sizes to HDW format
            hdw_employee_counts = []
            for size in company_sizes:
                size_map = {
                    "1-10 employees": "1-10",
                    "11-50 employees": "11-50",
                    "51-200 employees": "51-200",
                    "201-500 employees": "201-500",
                    "501-1000 employees": "501-1,000",
                    "1001-5000 employees": "1,001-5,000",
                    "5001-10000 employees": "5,001-10,000",
                    "10000+ employees": "10,001+"
                }
                if size in size_map:
                    hdw_employee_counts.append(size_map[size])
            
            # Search for industry URNs in parallel
            industry_tasks = []
            for industry_name in industries[:2]:  # Limit to top 2
                task = asyncio.create_task(
                    asyncio.to_thread(hdw_client.search_industries, name=industry_name, count=1)
                )
                industry_tasks.append((industry_name, task))
            
            industry_urns = []
            if industry_tasks:
                industry_results = await asyncio.gather(*[task for _, task in industry_tasks], return_exceptions=True)
                for i, (industry_name, _) in enumerate(industry_tasks):
                    result = industry_results[i]
                    if not isinstance(result, Exception) and result:
                        industry_urn = f"urn:li:industry:{result[0].urn.value}"
                        industry_urns.append(industry_urn)
                        self.logger.info(f"Found industry URN for '{industry_name}': {industry_urn}")
                    else:
                        self.logger.warning(f"Could not find industry URN for '{industry_name}'")
            
            # If no AI/ML specific URNs found, use broader tech search
            if not industry_urns and any(ind in ["Artificial Intelligence", "Machine Learning", "AI", "ML"] for ind in industries):
                self.logger.info("No AI/ML industry URNs found, falling back to technology/software search")
                # Try broader technology categories
                fallback_industries = ["Technology", "Software", "Computer Software", "Information Technology"]
                for industry_name in fallback_industries[:2]:
                    try:
                        result = await asyncio.to_thread(hdw_client.search_industries, name=industry_name, count=1)
                        if result:
                            industry_urn = f"urn:li:industry:{result[0].urn.value}"
                            industry_urns.append(industry_urn)
                            self.logger.info(f"Found fallback industry URN for '{industry_name}': {industry_urn}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Failed to find fallback industry '{industry_name}': {e}")
            
            # Search for location URNs if needed
            location_urns = None
            if location_filter:
                try:
                    locations = await asyncio.to_thread(hdw_client.search_locations, name=location_filter, count=1)
                    if locations:
                        location_urns = [f"urn:li:geo:{locations[0].urn.value}"]
                except Exception as e:
                    self.logger.warning(f"Could not find location URN for '{location_filter}': {e}")
            
            # Map seniority levels
            seniority_values = []
            for criteria in ["person_criteria"]:
                if criteria in {"person_criteria"}:
                    seniority_values.extend({"person_criteria": {}}.get(criteria, {}).get("seniority", {}).get("values", []))
            
            hdw_levels = []
            level_mapping = {
                "VP": "Vice President",
                "Director": "Director",
                "Manager": "Experienced Manager",
                "Senior": "Senior",
                "Entry": "Entry",
                "C-Level": "CXO",
                "Head": "Director"
            }
            
            for level in seniority_values:
                if level in level_mapping:
                    hdw_levels.append(level_mapping[level])
            
            # Search people using HDW
            keywords = " ".join(target_roles[:2]) if target_roles else "Sales Executive"
            
            # Enhance keywords for AI/ML search if relevant
            if any(ind in ["Artificial Intelligence", "Machine Learning", "AI", "ML", "LLM", "GenAI"] for ind in industries):
                keywords = f"{keywords} AI ML artificial intelligence machine learning"
                self.logger.info(f"Enhanced search keywords for AI/ML: {keywords}")
            
            try:
                users = await asyncio.to_thread(
                    hdw_client.search_nav_search_users,
                    keywords=keywords,
                    current_titles=target_roles[:3] if target_roles else None,
                    locations=location_urns if location_urns else None,
                    industry=industry_urns if industry_urns else None,
                    levels=hdw_levels if hdw_levels else None,
                    company_sizes=hdw_employee_counts if hdw_employee_counts else None,
                    count=min(search_limit, 10),
                    timeout=30  # Reduced from 300
                )
                
                for user in users:
                    # Handle both LinkedInUser objects and potential dict/string responses
                    if isinstance(user, str):
                        self.logger.warning(f"Unexpected string user data: {user}")
                        continue
                    
                    # Extract name safely
                    user_name = getattr(user, 'name', None) or str(user)
                    
                    person_data = {
                        "name": user_name,
                        "first_name": user_name.split()[0] if user_name else "Unknown",
                        "last_name": " ".join(user_name.split()[1:]) if user_name and len(user_name.split()) > 1 else "",
                        "title": user.current_companies[0].position if hasattr(user, 'current_companies') and user.current_companies else getattr(user, 'headline', ''),
                        "company": user.current_companies[0].company.name if hasattr(user, 'current_companies') and user.current_companies and hasattr(user.current_companies[0].company, 'name') else "Unknown",
                        "linkedin_url": getattr(user, 'url', ''),
                        "location": str(getattr(user, 'location', '')),
                        "headline": getattr(user, 'headline', '')
                    }
                    people_found.append(person_data)
                    
                    if user.current_companies and user.current_companies[0].company:
                        companies_found.append(user.current_companies[0].company)
                
                self.logger.info(f"Found {len(users)} people via HDW")
                
            except Exception as e:
                self.logger.error(f"Error searching people with HDW: {e}")
                # Fallback to basic search
                result = await self.search_people_hdw(
                    query=keywords,
                    limit=min(search_limit, 5),
                    current_titles=target_roles[:2] if target_roles else None
                )
                if result["status"] == "success":
                    people_found.extend(result["people"])
            
            return {
                "status": "success",
                "people": people_found,
                "companies": companies_found
            }
            
        except Exception as e:
            self.logger.error(f"Error in HDW search: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def _search_exa_prospects(
        self,
        industries: List[str],
        target_roles: List[str],
        icp_criteria: Dict[str, Any],
        location_filter: Optional[str],
        search_limit: int
    ) -> Dict[str, Any]:
        """Search for prospects using Exa API."""
        try:
            from integrations.exa_websets import ExaExtractor
            extractor = ExaExtractor(cache_manager=self.cache_manager)
            
            self.logger.info(f"Exa search starting - Industries: {industries}, Target roles: {target_roles}, Location: {location_filter}")
            
            # Build enhanced search query
            search_parts = []
            
            if target_roles and industries:
                # Make the query more specific for AI/ML companies
                if any(ind in ["Artificial Intelligence", "Machine Learning", "AI", "ML", "LLM", "GenAI"] for ind in industries):
                    # Use specific AI/ML keywords
                    role_industry_query = f"People who are {' OR '.join(target_roles[:2])} at AI artificial intelligence machine learning LLM companies"
                else:
                    role_industry_query = f"People who are {' OR '.join(target_roles[:2])} at {' OR '.join(industries[:2])} companies"
                search_parts.append(role_industry_query)
            
            # Add buying signals
            buying_signals = icp_criteria.get("buying_signals", [])
            if buying_signals:
                signal_keywords = []
                for signal in buying_signals[:2]:
                    if "budget" in signal.lower():
                        signal_keywords.extend(["budget allocated", "funding secured"])
                    elif "looking" in signal.lower() or "evaluating" in signal.lower():
                        signal_keywords.extend(["evaluating solutions", "vendor selection"])
                    elif "hiring" in signal.lower():
                        signal_keywords.extend(["hiring", "team expansion"])
                
                if signal_keywords:
                    search_parts.append(f"companies {' OR '.join(signal_keywords[:2])}")
            
            search_query = " ".join(search_parts)
            if location_filter:
                search_query += f" in {location_filter}"
            
            # Limit query length
            if len(search_query) > 500:
                search_query = f"People who are {' OR '.join(target_roles[:2])} at {' OR '.join(industries[:2])} companies"
                if location_filter:
                    search_query += f" in {location_filter}"
            
            self.logger.info(f"Exa search query: {search_query}")
            
            # Define enrichments
            enrichments = [
                {"description": "Person full name", "format": "text"},
                {"description": "Current job title or role", "format": "text"},
                {"description": "Current company name", "format": "text"},
                {"description": "LinkedIn profile URL", "format": "text"},
                {"description": "Email address if available", "format": "text"},
                {"description": "Professional background and expertise", "format": "text"}
            ]
            
            # Extract people using Exa
            exa_people = await asyncio.to_thread(
                extractor.extract_people,
                search_query=search_query,
                enrichments=enrichments,
                count=min(search_limit, 20)
            )
            
            self.logger.info(f"Found {len(exa_people)} people via Exa")
            
            return {
                "status": "success",
                "people": exa_people,
                "companies": []
            }
            
        except Exception as e:
            self.logger.error(f"Error in Exa search: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    # Required abstract method implementations
    
    def get_capabilities(self) -> List[str]:
        """Return list of Prospect agent capabilities."""
        return [
            "search_prospects_multi_source",
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
        """Handle prospect scoring task using batch scoring."""
        
        prospect_ids = task_data.get("prospect_ids", [])
        icp_criteria = task_data.get("icp_criteria", {})
        
        # Get prospect data
        prospects_data = []
        for prospect_id in prospect_ids:
            if prospect_id in self.active_prospects:
                prospect = self.active_prospects[prospect_id]
                prospects_data.append(prospect.model_dump())
        
        if not prospects_data:
            return {"status": "error", "error_message": "No prospects found"}
        
        # Use batch scoring
        batch_result = await self.batch_score_prospects(
            prospects_data=prospects_data,
            icp_criteria=icp_criteria
        )
        
        return batch_result
    
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
    
    async def refine_prospect_search(
        self,
        current_prospects: List[str],
        feedback: str,
        good_prospect_ids: Optional[List[str]] = None,
        bad_prospect_ids: Optional[List[str]] = None,
        icp_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refine prospect search based on user feedback.
        
        WARNING: This method uses process_json_request() to prevent infinite recursion.
        If this method is registered as a tool, the agent might call it recursively
        when asked to generate JSON refinements.
        
        Args:
            current_prospects: List of current prospect IDs
            feedback: User's feedback on the prospects
            good_prospect_ids: IDs of prospects user liked
            bad_prospect_ids: IDs of prospects user didn't like
            icp_criteria: Current ICP criteria to refine
            
        Returns:
            Dictionary with refined search results
        """
        try:
            self.logger.info(f"Refining prospect search based on feedback - Feedback_Length: {len(feedback)}, Good_Prospects: {len(good_prospect_ids or [])}, Bad_Prospects: {len(bad_prospect_ids or [])}")
            
            # Analyze good and bad prospects to understand patterns
            good_prospects = []
            bad_prospects = []
            
            if good_prospect_ids:
                for pid in good_prospect_ids:
                    if pid in self.active_prospects:
                        good_prospects.append(self.active_prospects[pid])
            
            if bad_prospect_ids:
                for pid in bad_prospect_ids:
                    if pid in self.active_prospects:
                        bad_prospects.append(self.active_prospects[pid])
            
            # Use LLM to analyze feedback and suggest search refinements
            refinement_prompt = f"""
            Analyze the user's feedback on prospects and suggest how to refine the search criteria.
            
            User Feedback: {feedback}
            
            Good Prospects (user liked these):
            {json.dumps([{
                "company": p.company.name,
                "industry": p.company.industry,
                "size": p.company.employee_range,
                "person": f"{p.person.first_name} {p.person.last_name}",
                "title": p.person.title
            } for p in good_prospects[:3]], indent=2, cls=DateTimeEncoder) if good_prospects else "None specified"}
            
            Bad Prospects (user didn't like these):
            {json.dumps([{
                "company": p.company.name,
                "industry": p.company.industry,
                "size": p.company.employee_range,
                "person": f"{p.person.first_name} {p.person.last_name}",
                "title": p.person.title
            } for p in bad_prospects[:3]], indent=2, cls=DateTimeEncoder) if bad_prospects else "None specified"}
            
            Current ICP Criteria:
            {json.dumps(icp_criteria, indent=2, cls=DateTimeEncoder) if icp_criteria else "Not provided"}
            
            Based on the feedback and examples, suggest specific refinements:
            1. Which criteria should be adjusted (company size, industry, job titles, etc.)?
            2. What specific values should be added or removed?
            3. How should scoring weights be adjusted?
            
            Return a JSON object with:
            {{
                "refined_criteria": {{
                    "company_size": ["values to search"],
                    "industries": ["refined industries"],
                    "job_titles": ["refined titles"],
                    "exclude_industries": ["industries to exclude"],
                    "exclude_titles": ["titles to exclude"]
                }},
                "scoring_adjustments": {{
                    "prioritize": ["factors to weight higher"],
                    "deprioritize": ["factors to weight lower"]
                }},
                "search_modifications": {{
                    "expand_search": true/false,
                    "location_focus": "specific location if mentioned",
                    "additional_keywords": ["keywords from feedback"]
                }}
            }}
            """
            
            # Use process_json_request to prevent recursive tool calls
            response = await self.process_json_request(refinement_prompt)
            
            try:
                refinements = json.loads(response)
            except json.JSONDecodeError:
                # Fallback refinements based on LLM extraction
                refinements = await self._extract_refinements_from_feedback(feedback)
            
            # Apply refinements and perform new search
            refined_icp = icp_criteria.copy() if icp_criteria else {}
            
            # Update ICP with refinements
            if "refined_criteria" in refinements:
                criteria = refinements["refined_criteria"]
                if "company_size" in criteria:
                    refined_icp.setdefault("company_criteria", {}).setdefault("company_size", {})["values"] = criteria["company_size"]
                if "industries" in criteria:
                    refined_icp["industries"] = criteria["industries"]
                if "job_titles" in criteria:
                    refined_icp["target_roles"] = criteria["job_titles"]
            
            # Perform new search with refined criteria
            search_result = await self.search_prospects_multi_source(
                icp_criteria=refined_icp,
                search_limit=50,
                sources=["hdw", "exa"],
                location_filter=refinements.get("search_modifications", {}).get("location_focus", "United States, Canada, United Kingdom")
            )
            
            if search_result["status"] != "success":
                return search_result
            
            # Apply custom scoring based on feedback patterns
            new_prospects = search_result["prospects"]
            
            # Re-score with adjustments using LLM-based similarity analysis
            if refinements.get("scoring_adjustments") or good_prospects or bad_prospects:
                for prospect in new_prospects:
                    # Use LLM to calculate similarity-based adjustments
                    adjustment = await self._calculate_llm_similarity_adjustment(
                        prospect, good_prospects, bad_prospects, feedback
                    )
                    
                    if hasattr(prospect, 'score') and prospect.score:
                        prospect.score.total_score = min(1.0, max(0.0, 
                            prospect.score.total_score + adjustment
                        ))
            
            return {
                "status": "success",
                "prospects": new_prospects,
                "refinements_applied": refinements,
                "feedback_processed": True,
                "total_found": len(new_prospects)
            }
            
        except Exception as e:
            self.logger.error(f"Error refining prospect search - Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def _extract_refinements_from_feedback(self, feedback: str) -> Dict[str, Any]:
        """Extract refinements from feedback using LLM analysis.
        
        Uses process_json_request() to ensure JSON generation without tool calls.
        """
        
        extraction_prompt = f"""
        Analyze this user feedback and extract specific search refinements.
        The user is giving feedback about prospect search results.
        
        User feedback: {feedback}
        
        Extract and return a JSON object with search refinements:
        {{
            "refined_criteria": {{
                "company_size": ["specific employee ranges like '51-200 employees'"] or null,
                "industries": ["specific industries mentioned"] or null,
                "job_titles": ["specific job titles or seniority levels"] or null,
                "exclude_industries": ["industries to exclude"] or null,
                "exclude_titles": ["titles to exclude"] or null
            }},
            "scoring_adjustments": {{
                "prioritize": ["factors to weight higher"],
                "deprioritize": ["factors to weight lower"]
            }},
            "search_modifications": {{
                "expand_search": true/false,
                "location_focus": "specific location if mentioned",
                "additional_keywords": ["keywords from feedback"]
            }}
        }}
        
        Valid company sizes: "1-10 employees", "11-50 employees", "51-200 employees", "201-500 employees", "501-1000 employees", "1001-5000 employees", "5001-10000 employees", "10000+ employees"
        
        Note: The feedback might be in any language. Extract the intent regardless of language.
        """
        
        try:
            # Use process_json_request to extract refinements without tool calls
            response = await self.process_json_request(extraction_prompt)
            refinements = json.loads(response)
            
            # Clean up null values
            if "refined_criteria" in refinements:
                refinements["refined_criteria"] = {
                    k: v for k, v in refinements["refined_criteria"].items() 
                    if v is not None and v != []
                }
            
            return refinements
            
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"LLM extraction failed, returning empty refinements: {str(e)}")
            # Return empty refinements if LLM fails
            return {"refined_criteria": {}, "scoring_adjustments": {}, "search_modifications": {}}
    
    async def _calculate_llm_similarity_adjustment(
        self,
        prospect: Prospect,
        good_prospects: List[Prospect],
        bad_prospects: List[Prospect],
        feedback: str
    ) -> float:
        """Use LLM to calculate score adjustment based on similarity to good/bad examples.
        
        Uses process_json_request() to ensure JSON generation without tool calls.
        """
        
        if not good_prospects and not bad_prospects:
            return 0.0
        
        similarity_prompt = f"""
        Analyze how similar this prospect is to the examples the user liked/disliked.
        
        Current Prospect:
        - Company: {prospect.company.name} ({prospect.company.industry}, {prospect.company.employee_range})
        - Person: {prospect.person.first_name} {prospect.person.last_name}, {prospect.person.title}
        
        Good Examples (user liked these):
        {json.dumps([{
            "company": f"{p.company.name} ({p.company.industry}, {p.company.employee_range})",
            "person": f"{p.person.first_name} {p.person.last_name}, {p.person.title}"
        } for p in good_prospects[:3]], indent=2, cls=DateTimeEncoder) if good_prospects else "None"}
        
        Bad Examples (user disliked these):
        {json.dumps([{
            "company": f"{p.company.name} ({p.company.industry}, {p.company.employee_range})",
            "person": f"{p.person.first_name} {p.person.last_name}, {p.person.title}"
        } for p in bad_prospects[:3]], indent=2, cls=DateTimeEncoder) if bad_prospects else "None"}
        
        User Feedback: {feedback[:200]}...
        
        Return a JSON object with:
        {{
            "similarity_to_good": 0.0-1.0 (how similar to good examples),
            "similarity_to_bad": 0.0-1.0 (how similar to bad examples),
            "adjustment": -0.3 to +0.3 (score adjustment),
            "reasoning": "brief explanation"
        }}
        
        Positive adjustment if similar to good examples, negative if similar to bad examples.
        """
        
        try:
            # Use process_json_request to get JSON without tool calls
            response = await self.process_json_request(similarity_prompt)
            similarity_data = json.loads(response)
            
            return similarity_data.get("adjustment", 0.0)
            
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"LLM similarity adjustment failed: {str(e)}")
            # Fallback to simple calculation
            boost = self._calculate_similarity_boost(prospect, good_prospects)
            penalty = self._calculate_similarity_penalty(prospect, bad_prospects)
            return boost - penalty
    
    def _calculate_similarity_boost(self, prospect: Prospect, good_prospects: List[Prospect]) -> float:
        """Calculate score boost based on similarity to good prospects."""
        if not good_prospects:
            return 0.0
        
        boost = 0.0
        for good_prospect in good_prospects:
            # Industry match
            if prospect.company.industry == good_prospect.company.industry:
                boost += 0.05
            # Title similarity
            if prospect.person.title and good_prospect.person.title:
                if any(word in prospect.person.title.lower() for word in good_prospect.person.title.lower().split()):
                    boost += 0.05
            # Company size match
            if prospect.company.employee_range == good_prospect.company.employee_range:
                boost += 0.03
        
        return min(boost, 0.2)  # Cap at 0.2
    
    def _calculate_similarity_penalty(self, prospect: Prospect, bad_prospects: List[Prospect]) -> float:
        """Calculate score penalty based on similarity to bad prospects."""
        if not bad_prospects:
            return 0.0
        
        penalty = 0.0
        for bad_prospect in bad_prospects:
            # Industry match
            if prospect.company.industry == bad_prospect.company.industry:
                penalty += 0.05
            # Title similarity
            if prospect.person.title and bad_prospect.person.title:
                if any(word in prospect.person.title.lower() for word in bad_prospect.person.title.lower().split()):
                    penalty += 0.05
            # Company size match
            if prospect.company.employee_range == bad_prospect.company.employee_range:
                penalty += 0.03
        
        return min(penalty, 0.2)  # Cap at 0.2