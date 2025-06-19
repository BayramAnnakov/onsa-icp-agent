"""ICP Agent using Google ADK with external tools."""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.json_storage import save_large_json, load_large_json

from .adk_base_agent import ADKAgent
from models import ICP, ICPCriteria, Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager
from integrations import HorizonDataWave, ExaWebsetsAPI, FirecrawlClient


class ADKICPAgent(ADKAgent):
    """
    ICP Agent built with Google ADK that creates and refines Ideal Customer Profiles.
    
    Uses external tools for:
    - Company research via HorizonDataWave
    - People research via Exa 
    - Website analysis via Firecrawl
    """
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None):
        super().__init__(
            agent_name="icp_agent",
            agent_description="Creates and refines Ideal Customer Profiles using multi-source research and AI analysis",
            config=config,
            cache_manager=cache_manager
        )
        
        # ICP management
        object.__setattr__(self, 'active_icps', {})
        
        # Initialize external API clients
        self._setup_external_clients()
        
        # Setup tools - only add what ICP agent needs
        self.setup_icp_specific_tools()
        self.setup_icp_tools()
        
        self.logger.info("ADK ICP Agent initialized")
    
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
    
    def setup_icp_specific_tools(self) -> None:
        """Setup only the external tools that ICP agent needs."""
        # ICP agent needs company search for researching example companies
        self.setup_company_search_tools()
        
        # ICP agent needs web scraping for analyzing company websites
        self.setup_web_scraping_tools()
        
        # ICP agent occasionally uses people search for understanding target roles
        # But only the basic search, not the expensive nav search
        self.add_external_tool(
            name="search_people_exa",
            description="Search for people using Exa Websets API. Use when looking for contact information, people profiles, or decision makers.",
            func=self.search_people_exa
        )
        
        self.logger.info("ICP-specific external tools configured", tool_count=len(self.tools))
    
    def setup_icp_tools(self) -> None:
        """Setup ICP-specific tools."""
        
        self.add_external_tool(
            name="create_icp_from_research",
            description="Create an ICP by researching provided companies and analyzing patterns. Use when user provides example companies or wants data-driven ICP creation.",
            func=self.create_icp_from_research
        )
        
        self.add_external_tool(
            name="analyze_company_website",
            description="Analyze a company website to extract business information for ICP creation. Use when provided with company URLs.",
            func=self.analyze_company_website
        )
        
        self.add_external_tool(
            name="refine_icp_criteria",
            description="Refine existing ICP criteria based on user feedback. Use when user wants to modify or improve an existing ICP.",
            func=self.refine_icp_criteria
        )
        
        self.add_external_tool(
            name="export_icp",
            description="Export ICP in various formats (JSON, structured text). Use when user requests ICP data or other agents need ICP information.",
            func=self.export_icp
        )
    
    async def create_icp_from_research(
        self,
        business_info: Dict[str, Any],
        example_companies: Optional[List[str]] = None,
        research_depth: str = "standard"
    ) -> Dict[str, Any]:
        """Create ICP by researching companies and analyzing patterns.
        
        Args:
            business_info: Basic business information provided by user
            example_companies: List of example company names or URLs
            research_depth: How deep to research (basic, standard, comprehensive)
            
        Returns:
            Dictionary with created ICP data
        """
        try:
            self.logger.info("Creating ICP from research", companies=len(example_companies or []))
            
            # Research example companies if provided
            researched_companies = []
            detailed_company_data = []
            
            if example_companies:
                hdw_client = self.external_clients.get("horizondatawave")
                
                for company in example_companies[:5]:  # Limit to 5 companies
                    # Try to get company data from HDW
                    if hdw_client:
                        # First search for the company
                        hdw_result = await self.search_companies_hdw(company, limit=1)
                        if hdw_result["status"] == "success" and hdw_result["companies"]:
                            researched_companies.extend(hdw_result["companies"])
                            
                            # Get detailed LinkedIn data if in comprehensive mode
                            if research_depth in ["standard", "comprehensive"]:
                                try:
                                    # Use the alias from search results, not the company name!
                                    company_alias = hdw_result["companies"][0].alias
                                    company_urn = hdw_result["companies"][0].urn.value
                                    
                                    # Try with alias first (correct way)
                                    try:
                                        detailed_data = hdw_client.get_linkedin_company(company_alias, timeout=300)
                                    except:
                                        # Fallback to URN if alias fails
                                        detailed_data = hdw_client.get_linkedin_company(company_urn, timeout=300)
                                    
                                    if detailed_data:
                                        detailed_company_data.append({
                                            "name": detailed_data[0].name,
                                            "industry": detailed_data[0].industry.value if detailed_data[0].industry else "Unknown",
                                            "employee_count": detailed_data[0].employee_count,
                                            "employee_count_range": detailed_data[0].employee_count_range,
                                            "description": detailed_data[0].description or "",
                                            "specialities": detailed_data[0].specialities or [],
                                            "locations": [loc.location for loc in detailed_data[0].locations] if detailed_data[0].locations else []
                                        })
                                except Exception as e:
                                    self.logger.warning(f"Could not get detailed LinkedIn data for {company}: {e}")
                    
                    # If it's a URL, scrape the website
                    if company.startswith("http"):
                        firecrawl_result = await self.scrape_website_firecrawl(company)
                        if firecrawl_result["status"] == "success":
                            researched_companies.append({
                                "name": "Unknown",
                                "website_content": firecrawl_result["content"],
                                "url": company
                            })
            
            # Save large research data if needed
            if researched_companies or detailed_company_data:
                # Convert companies to serializable format
                serializable_companies = []
                for company in researched_companies:
                    if hasattr(company, '__dict__') and callable(company.__dict__):
                        serializable_companies.append(company.__dict__())
                    elif hasattr(company, 'model_dump'):
                        serializable_companies.append(company.model_dump())
                    else:
                        serializable_companies.append(str(company))
                
                # Add detailed data
                if detailed_company_data:
                    serializable_companies.extend(detailed_company_data)
                
                # Save to storage if data is large
                research_key = save_large_json(
                    serializable_companies,
                    metadata={"type": "company_research", "count": len(serializable_companies)}
                )
                self.logger.info("Saved research data", key=research_key, companies=len(serializable_companies))
                
                # Use summary for prompt
                companies_summary = f"Found {len(serializable_companies)} companies with detailed data. Examples: {json.dumps(serializable_companies[:3], indent=2)}"
            else:
                companies_summary = "None provided"
            
            # Generate ICP using AI analysis with HDW/Exa compatible criteria
            icp_prompt = f"""
            You are generating an ICP JSON structure. DO NOT call any functions.
            Simply analyze the information and return the JSON structure as requested.
            
            IMPORTANT: Return ONLY the JSON, no function calls, no additional text.
            Create an Ideal Customer Profile based on the following information:
            
            Business Information:
            {json.dumps(business_info, indent=2)}
            
            Researched Companies:
            {companies_summary}
            
            Create a comprehensive ICP with criteria that match HDW and Exa search capabilities:
            
            IMPORTANT: Use these specific values for compatibility with our search APIs:
            
            Company Size Values (HDW compatible):
            - "1-10 employees"
            - "11-50 employees" 
            - "51-200 employees"
            - "201-500 employees"
            - "501-1000 employees"
            - "1001-5000 employees"
            - "5001-10000 employees"
            - "10000+ employees"
            
            Seniority Level Values (HDW compatible):
            - "VP"
            - "Director"
            - "Manager"
            - "Senior"
            - "Entry"
            - "C-Level"
            - "Head"
            
            Industries should be standard names like:
            - "Software Development"
            - "Information Technology"
            - "Financial Services"
            - "Healthcare"
            - "E-commerce"
            - "SaaS"
            - "B2B Software"
            
            Job Titles should be searchable titles like:
            - "VP Sales"
            - "Head of Sales"
            - "Sales Director"
            - "Chief Revenue Officer"
            - "VP Marketing"
            - "Head of Engineering"
            - "CTO"
            - "CEO"
            
            Return as JSON with the following structure:
            {{
                "icp_name": "descriptive name",
                "description": "detailed description",
                "company_criteria": {{
                    "company_size": {{"name": "company_size", "description": "Target company size", "weight": 0.9, "values": ["51-200 employees", "201-500 employees"]}},
                    "industry": {{"name": "industry", "description": "Target industries", "weight": 0.8, "values": ["Software Development", "SaaS"]}},
                    "revenue": {{"name": "revenue", "description": "Annual revenue range", "weight": 0.7, "values": ["$1M-$10M", "$10M-$50M"]}}
                }},
                "person_criteria": {{
                    "job_title": {{"name": "job_title", "description": "Target job titles", "weight": 0.9, "values": ["VP Sales", "Head of Sales"]}},
                    "seniority": {{"name": "seniority", "description": "Seniority levels", "weight": 0.8, "values": ["VP", "Director", "C-Level"]}}
                }},
                "industries": ["Software Development", "SaaS"],
                "target_roles": ["VP Sales", "Head of Sales", "Sales Director"],
                "pain_points": ["pain1", "pain2"],
                "buying_signals": ["signal1", "signal2"]
            }}
            """
            
            # Use direct message processing without function calling
            # Save current tools and temporarily disable them
            saved_tools = self.tools
            self.tools = []
            try:
                response = await self.process_message(icp_prompt)
            finally:
                # Restore tools
                self.tools = saved_tools
            
            # Parse the JSON response
            try:
                icp_data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                icp_data = self._create_fallback_icp(business_info)
            
            # Create ICP object
            icp = self._create_icp_from_data(icp_data)
            
            # Store the ICP
            self.active_icps[icp.id] = icp
            
            self.logger.info("ICP created from research", icp_id=icp.id, name=icp.name)
            
            return {
                "status": "success",
                "icp_id": icp.id,
                "icp": icp.model_dump(),
                "research_used": len(researched_companies),
                "detailed_research": len(detailed_company_data)
            }
            
        except Exception as e:
            self.logger.error("Error creating ICP from research", error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def analyze_company_website(
        self,
        url: str,
        analysis_focus: str = "business_model"
    ) -> Dict[str, Any]:
        """Analyze company website for ICP insights.
        
        Args:
            url: Company website URL
            analysis_focus: What to focus on (business_model, customers, technology)
            
        Returns:
            Dictionary with website analysis results
        """
        try:
            # Scrape the website
            scrape_result = await self.scrape_website_firecrawl(url, include_links=True)
            
            if scrape_result["status"] != "success":
                return scrape_result
            
            # Analyze the content
            analysis_prompt = f"""
            Analyze this company website content and extract insights for creating an Ideal Customer Profile:
            
            Website URL: {url}
            Content: {scrape_result["content"][:3000]}...
            
            Focus on: {analysis_focus}
            
            Extract:
            1. Business model and offerings
            2. Target market indicators
            3. Company size and industry
            4. Technology stack mentions
            5. Customer types mentioned
            6. Pain points they solve
            
            Return as structured JSON with insights for ICP creation.
            """
            
            analysis = await self.process_message(analysis_prompt)
            
            return {
                "status": "success",
                "url": url,
                "analysis": analysis,
                "raw_content": scrape_result["content"][:1000]
            }
            
        except Exception as e:
            self.logger.error("Error analyzing website", url=url, error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def refine_icp_criteria(
        self,
        icp_id: str,
        feedback: str,
        specific_changes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refine ICP criteria based on feedback.
        
        Args:
            icp_id: ID of the ICP to refine
            feedback: User feedback on the ICP
            specific_changes: Specific changes to make
            
        Returns:
            Dictionary with refined ICP data
        """
        try:
            # Get existing ICP
            existing_icp = self.active_icps.get(icp_id)
            if not existing_icp:
                return {"status": "error", "error_message": "ICP not found"}
            
            # Generate refinement prompt
            refinement_prompt = f"""
            Refine this Ideal Customer Profile based on user feedback:
            
            Current ICP:
            {json.dumps(existing_icp.model_dump(), indent=2)}
            
            User Feedback:
            {feedback}
            
            Specific Changes Requested:
            {json.dumps(specific_changes, indent=2) if specific_changes else "None"}
            
            Update the ICP while maintaining the same structure. Focus on:
            1. Incorporating the feedback
            2. Adjusting weights and criteria
            3. Adding/removing values as needed
            4. Updating description to reflect changes
            
            Return the complete updated ICP as JSON with the same structure.
            """
            
            response = await self.process_message(refinement_prompt)
            
            # Parse the response
            try:
                refined_data = json.loads(response)
            except json.JSONDecodeError:
                refined_data = existing_icp.model_dump()
                # Apply specific changes manually if JSON parsing fails
                if specific_changes:
                    refined_data.update(specific_changes)
            
            # Create refined ICP
            refined_icp = self._create_icp_from_data(refined_data)
            refined_icp.add_feedback(feedback, specific_changes or {})
            
            # Store the refined ICP
            self.active_icps[refined_icp.id] = refined_icp
            
            self.logger.info("ICP refined", original_id=icp_id, refined_id=refined_icp.id)
            
            return {
                "status": "success",
                "icp_id": refined_icp.id,
                "icp": refined_icp.model_dump(),
                "changes_applied": True
            }
            
        except Exception as e:
            self.logger.error("Error refining ICP", icp_id=icp_id, error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    async def export_icp(
        self,
        icp_id: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export ICP in specified format.
        
        Args:
            icp_id: ID of the ICP to export
            format: Export format (json, text, summary)
            
        Returns:
            Dictionary with exported ICP data
        """
        try:
            icp = self.active_icps.get(icp_id)
            if not icp:
                return {"status": "error", "error_message": "ICP not found"}
            
            if format == "json":
                return {
                    "status": "success",
                    "format": "json",
                    "icp": icp.model_dump()
                }
            elif format == "text":
                text_format = self._format_icp_as_text(icp)
                return {
                    "status": "success",
                    "format": "text",
                    "icp": text_format
                }
            elif format == "summary":
                summary = self._create_icp_summary(icp)
                return {
                    "status": "success",
                    "format": "summary",
                    "icp": summary
                }
            else:
                return {"status": "error", "error_message": f"Unsupported format: {format}"}
                
        except Exception as e:
            self.logger.error("Error exporting ICP", icp_id=icp_id, error=str(e))
            return {"status": "error", "error_message": str(e)}
    
    def _create_icp_from_data(self, icp_data: Dict[str, Any]) -> ICP:
        """Create ICP object from data dictionary."""
        
        # Convert criteria dictionaries to ICPCriteria objects
        company_criteria = {}
        for key, criteria_data in icp_data.get("company_criteria", {}).items():
            company_criteria[key] = ICPCriteria(**criteria_data)
        
        person_criteria = {}
        for key, criteria_data in icp_data.get("person_criteria", {}).items():
            person_criteria[key] = ICPCriteria(**criteria_data)
        
        # Create ICP
        icp = ICP(
            id=f"icp_{int(datetime.now().timestamp())}",
            name=icp_data.get("icp_name", "Unnamed ICP"),
            description=icp_data.get("description", ""),
            company_criteria=company_criteria,
            person_criteria=person_criteria,
            industries=icp_data.get("industries", []),
            target_roles=icp_data.get("target_roles", []),
            pain_points=icp_data.get("pain_points", []),
            buying_signals=icp_data.get("buying_signals", [])
        )
        
        return icp
    
    def _create_fallback_icp(self, business_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback ICP when AI generation fails."""
        return {
            "icp_name": f"{business_info.get('business_name', 'Business')} ICP",
            "description": f"ICP for {business_info.get('business_description', 'the business')}",
            "company_criteria": {
                "company_size": {
                    "name": "company_size",
                    "description": "Target company size",
                    "weight": 0.8,
                    "values": ["51-200 employees", "201-500 employees"]
                },
                "industry": {
                    "name": "industry",
                    "description": "Target industries",
                    "weight": 0.8,
                    "values": ["Software Development", "Information Technology", "SaaS"]
                }
            },
            "person_criteria": {
                "job_title": {
                    "name": "job_title", 
                    "description": "Target job titles",
                    "weight": 0.9,
                    "values": ["VP Sales", "Sales Director", "Head of Sales"]
                },
                "seniority": {
                    "name": "seniority",
                    "description": "Seniority levels",
                    "weight": 0.8,
                    "values": ["VP", "Director", "C-Level"]
                }
            },
            "industries": [business_info.get("target_market", "Software Development")],
            "target_roles": ["VP Sales", "Head of Sales", "Sales Director"],
            "pain_points": ["Efficiency", "Growth", "Sales Productivity"],
            "buying_signals": ["Budget Available", "Actively Looking", "Hiring Sales Team"]
        }
    
    def _format_icp_as_text(self, icp: ICP) -> str:
        """Format ICP as human-readable text."""
        text_lines = [
            f"# {icp.name}",
            f"\n{icp.description}\n",
            "## Company Criteria:",
        ]
        
        for name, criteria in icp.company_criteria.items():
            text_lines.append(f"- {criteria.description} (Weight: {criteria.weight})")
            text_lines.append(f"  Values: {', '.join(criteria.values)}")
        
        text_lines.append("\n## Person Criteria:")
        for name, criteria in icp.person_criteria.items():
            text_lines.append(f"- {criteria.description} (Weight: {criteria.weight})")
            text_lines.append(f"  Values: {', '.join(criteria.values)}")
        
        text_lines.append(f"\n## Target Industries:\n{', '.join(icp.industries)}")
        text_lines.append(f"\n## Target Roles:\n{', '.join(icp.target_roles)}")
        
        return "\n".join(text_lines)
    
    def _create_icp_summary(self, icp: ICP) -> str:
        """Create brief ICP summary."""
        return f"{icp.name}: Targeting {', '.join(icp.industries)} companies with {', '.join(icp.target_roles)} decision makers."
    
    # Required abstract method implementations
    
    def get_capabilities(self) -> List[str]:
        """Return list of ICP agent capabilities."""
        return [
            "create_icp_from_research",
            "analyze_company_website", 
            "refine_icp_criteria",
            "export_icp",
            "search_companies_hdw",
            "search_industries_hdw",
            "search_locations_hdw",
            "search_people_exa",
            "scrape_website_firecrawl"
        ]
    
    async def execute_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute ICP-related tasks."""
        
        task_handlers = {
            "create_icp": self._handle_create_icp_task,
            "refine_icp": self._handle_refine_icp_task,
            "export_icp": self._handle_export_icp_task,
            "analyze_sources": self._handle_analyze_sources_task
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
        """Process ICP-related queries."""
        
        # Use Google ADK to process the query with tools
        return await self.process_message(query, conversation_id, context)
    
    # Task handlers
    
    async def _handle_create_icp_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle ICP creation task."""
        
        business_info = task_data.get("business_info", {})
        source_materials = task_data.get("source_materials", [])
        
        # Extract company URLs from source materials
        company_urls = [
            material["url"] for material in source_materials
            if material.get("type") == "url" and "http" in material.get("url", "")
        ]
        
        return await self.create_icp_from_research(
            business_info=business_info,
            example_companies=company_urls
        )
    
    async def _handle_refine_icp_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle ICP refinement task."""
        
        return await self.refine_icp_criteria(
            icp_id=task_data.get("icp_id"),
            feedback=task_data.get("feedback", ""),
            specific_changes=task_data.get("suggested_changes")
        )
    
    async def _handle_export_icp_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle ICP export task."""
        
        return await self.export_icp(
            icp_id=task_data.get("icp_id"),
            format=task_data.get("format", "json")
        )
    
    async def _handle_analyze_sources_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle source analysis task."""
        
        sources = task_data.get("sources", [])
        findings = {}
        
        for source in sources:
            if source.get("type") == "url":
                url = source.get("url")
                if url:
                    analysis = await self.analyze_company_website(url)
                    findings[url] = analysis
        
        return {"status": "success", "findings": findings}