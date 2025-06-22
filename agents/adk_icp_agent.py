"""ICP Agent using Google ADK with external tools."""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.json_storage import save_large_json, load_large_json
from utils.json_encoder import DateTimeEncoder

from .adk_base_agent import ADKAgent
from models import ICP, ICPCriteria, Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager
from integrations import HorizonDataWave, FirecrawlClient


class ADKICPAgent(ADKAgent):
    """
    ICP Agent built with Google ADK that creates and refines Ideal Customer Profiles.
    
    Uses external tools for:
    - Company research via HorizonDataWave
    - People research via Exa 
    - Website analysis via Firecrawl
    """
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None, memory_manager=None):
        super().__init__(
            agent_name="icp_agent",
            agent_description="Creates and refines Ideal Customer Profiles using multi-source research and AI analysis. Can retrieve and work with previously created ICPs from memory.",
            config=config,
            cache_manager=cache_manager,
            memory_manager=memory_manager
        )
        
        # ICP management
        object.__setattr__(self, 'active_icps', {})
        
        # Initialize external API clients
        self._setup_external_clients()
        
        # Setup tools - only add what ICP agent needs
        self.setup_external_tools()  # This sets up memory tools from parent
        self.setup_icp_specific_tools()
        self.setup_icp_tools()
        
        self.logger.info("ADK ICP Agent initialized")
    
    def _setup_external_clients(self) -> None:
        """Initialize external API clients."""
        try:
            self.external_clients["horizondatawave"] = HorizonDataWave(cache_enabled=True)
        except ValueError:
            self.logger.warning("HorizonDataWave client not initialized - API key missing")
        
        # Exa is not needed for ICP creation - only for prospect finding
        
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
        
        # Note: People search (Exa) is not needed for ICP creation
        # ICP focuses on company criteria and business analysis
        
        self.logger.info(f"ICP-specific external tools configured - Tool_Count: {len(self.tools)}")
    
    def setup_icp_tools(self) -> None:
        """Setup ICP-specific tools."""
        
        self.add_external_tool(
            name="create_icp_from_research",
            description="Create an ICP by researching provided companies and analyzing patterns. Use when user provides example companies or wants data-driven ICP creation.",
            func=self.create_icp_from_research
        )
        
        # Note: analyze_company_website is an internal method, not exposed as a tool
        # to prevent recursive calls when the agent is analyzing websites
        
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
        
        self.add_external_tool(
            name="retrieve_past_icps",
            description="Search for and retrieve previously created ICPs from memory. Use when user asks about 'last ICP', 'previous ICP', or references past work.",
            func=self.retrieve_past_icps
        )
    
    async def create_icp_from_research(
        self,
        business_info: Dict[str, Any],
        example_companies: Optional[List[str]] = None,
        research_depth: str = "standard"
    ) -> Dict[str, Any]:
        """Create ICP by researching companies and analyzing patterns.
        
        WARNING: This method uses process_json_request() to generate ICP JSON.
        This prevents infinite recursion that could occur if the agent tries to
        call this method while generating the ICP structure.
        
        Args:
            business_info: Basic business information provided by user
            example_companies: List of example company names or URLs
            research_depth: How deep to research (basic, standard, comprehensive)
            
        Returns:
            Dictionary with created ICP data
        """
        try:
            self.logger.info(f"Creating ICP from research - Companies: {len(example_companies or [])}")
            
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
                        
                        # Handle case where hdw_result might be a string or not properly structured
                        if not isinstance(hdw_result, dict):
                            self.logger.warning(f"HDW result is not a dictionary: {type(hdw_result)}")
                            if isinstance(hdw_result, str):
                                try:
                                    hdw_result = json.loads(hdw_result)
                                except:
                                    hdw_result = {"status": "error", "error_message": "Invalid HDW result format"}
                            else:
                                hdw_result = {"status": "error", "error_message": f"Unexpected HDW result type: {type(hdw_result)}"}
                        
                        if hdw_result.get("status") == "success" and hdw_result.get("companies"):
                            researched_companies.extend(hdw_result["companies"])
                            
                            # Get detailed LinkedIn data if in comprehensive mode
                            if research_depth in ["standard", "comprehensive"]:
                                try:
                                    # Use the alias from search results, not the company name!
                                    company_alias = hdw_result["companies"][0].alias
                                    company_urn = hdw_result["companies"][0].urn.value
                                    
                                    # Try with alias first (correct way)
                                    try:
                                        detailed_data = hdw_client.get_linkedin_company(company_alias, timeout=30)
                                    except:
                                        # Fallback to URN if alias fails
                                        detailed_data = hdw_client.get_linkedin_company(company_urn, timeout=30)
                                    
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
                    
                    # If it's a URL, analyze the website with customer enrichment
                    if company.startswith("http"):
                        # Validate URL has proper TLD
                        import re
                        url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*\.[a-zA-Z]{2,}')
                        if not url_pattern.match(company):
                            self.logger.warning(f"Invalid URL format: {company} - skipping website analysis")
                            continue
                        
                        website_result = await self.analyze_company_website(company, "customers")
                        
                        # Handle case where website_result might be a string or not properly structured
                        if not isinstance(website_result, dict):
                            self.logger.warning(f"Website analysis result is not a dictionary: {type(website_result)}")
                            if isinstance(website_result, str):
                                try:
                                    website_result = json.loads(website_result)
                                except:
                                    website_result = {"status": "error", "error_message": "Invalid website result format"}
                            else:
                                website_result = {"status": "error", "error_message": f"Unexpected website result type: {type(website_result)}"}
                        
                        if website_result.get("status") == "success":
                            # Try to extract company name from website analysis
                            company_name = "Unknown"
                            try:
                                if isinstance(website_result["analysis"], str):
                                    # Parse JSON if it's a string
                                    if "business_model_and_offerings" in website_result["analysis"]:
                                        analysis_data = json.loads(website_result["analysis"])
                                        # Extract company name from offerings/descriptions
                                        offerings = analysis_data.get("business_model_and_offerings", "")
                                        # Look for patterns like "Ons.ai" or "Onsa.ai" 
                                        import re
                                        name_match = re.search(r'([\w]+\.ai|[\w]+\s+(?:Inc|Corp|LLC|Ltd))', offerings, re.IGNORECASE)
                                        if name_match:
                                            company_name = name_match.group(1).replace(".ai", "")
                            except Exception as e:
                                self.logger.debug(f"Could not extract company name from website: {e}")
                            
                            researched_companies.append({
                                "name": company_name,
                                "website_analysis": website_result["analysis"],
                                "enriched_customers": website_result.get("enriched_customers", []),
                                "url": company
                            })
                            
                            # Now try to search HDW with the extracted company name
                            if hdw_client and company_name != "Unknown":
                                self.logger.info(f"Searching HDW for company: {company_name}")
                                hdw_result = await self.search_companies_hdw(company_name, limit=1)
                                
                                # Handle case where hdw_result might be a string or not properly structured
                                if not isinstance(hdw_result, dict):
                                    self.logger.warning(f"HDW result is not a dictionary: {type(hdw_result)}")
                                    if isinstance(hdw_result, str):
                                        try:
                                            hdw_result = json.loads(hdw_result)
                                        except:
                                            hdw_result = {"status": "error", "error_message": "Invalid HDW result format"}
                                    else:
                                        hdw_result = {"status": "error", "error_message": f"Unexpected HDW result type: {type(hdw_result)}"}
                                
                                if hdw_result.get("status") == "success" and hdw_result.get("companies"):
                                    # Add HDW data to the researched company
                                    researched_companies[-1]["hdw_data"] = hdw_result["companies"][0]
                                    
                                    # Get detailed LinkedIn data if in standard/comprehensive mode
                                    if research_depth in ["standard", "comprehensive"]:
                                        try:
                                            company_alias = hdw_result["companies"][0].alias
                                            company_urn = hdw_result["companies"][0].urn.value
                                            
                                            try:
                                                detailed_data = hdw_client.get_linkedin_company(company_alias, timeout=30)
                                            except:
                                                detailed_data = hdw_client.get_linkedin_company(company_urn, timeout=30)
                                            
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
                                            self.logger.warning(f"Could not get detailed LinkedIn data for {company_name}: {e}")
            
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
                self.logger.info(f"Saved research data - Key: {research_key}, Companies: {len(serializable_companies)}")
                
                # Use summary for prompt - safely serialize to avoid circular references
                try:
                    companies_json = json.dumps(serializable_companies[:3], indent=2, cls=DateTimeEncoder)
                    companies_summary = f"Found {len(serializable_companies)} companies with detailed data. Examples: {companies_json}"
                except (TypeError, ValueError) as e:
                    self.logger.warning(f"Could not serialize companies data, using basic summary: {e}")
                    companies_summary = f"Found {len(serializable_companies)} companies with detailed data (serialization error: {str(e)})"
            else:
                companies_summary = "None provided"
            
            # Generate ICP using AI analysis with HDW compatible criteria
            # Safely serialize business_info to avoid circular references
            safe_business_info = self._safe_serialize_business_info(business_info)
            
            icp_prompt = f"""
            You are generating an ICP JSON structure. DO NOT call any functions.
            Simply analyze the information and return the JSON structure as requested.
            
            IMPORTANT: Return ONLY the JSON, no function calls, no additional text.
            IMPORTANT: Limit pain_points to EXACTLY 3 most important items.
            Create an Ideal Customer Profile based on the following information:
            
            Business Information:
            {safe_business_info}
            
            Researched Companies:
            {companies_summary}
            
            Pay special attention to any enriched customer data found, as this represents actual customers of the business.
            
            Create a comprehensive ICP with criteria that match HDW search capabilities:
            
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
                "pain_points": ["pain1", "pain2", "pain3"],  // LIMIT TO EXACTLY 3
                "buying_signals": ["signal1", "signal2"]
            }}
            """
            
            # Use process_json_request to prevent the agent from calling functions
            # This ensures we get pure JSON output instead of function calls
            try:
                response = await self.process_json_request(icp_prompt)
            except Exception as e:
                self.logger.error(f"Error in process_json_request: {str(e)}")
                raise
            
            # Parse the JSON response
            try:
                icp_data = json.loads(response)
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parsing failed: {str(e)}, using fallback ICP")
                # Fallback if JSON parsing fails
                icp_data = self._create_fallback_icp(business_info)
            
            # Create ICP object
            try:
                icp = self._create_icp_from_data(icp_data)
            except Exception as e:
                self.logger.error(f"Error in _create_icp_from_data: {str(e)}")
                raise
            
            # Store the ICP
            try:
                self.active_icps[icp.id] = icp
            except Exception as e:
                self.logger.error(f"Error storing ICP: {str(e)}")
                raise
            
            self.logger.info(f"ICP created from research - Icp_Id: {icp.id}, Name: {icp.name}")
            
            return {
                "status": "success",
                "icp_id": icp.id,
                "icp": {
                    "id": icp.id,
                    "name": icp.name,
                    "description": icp.description,
                    "industries": icp.industries,
                    "target_roles": icp.target_roles,
                    "seniority_levels": icp.seniority_levels,
                    "departments": icp.departments,
                    "pain_points": icp.pain_points,
                    "goals": icp.goals,
                    "company_size": icp.company_size,
                    "geographic_regions": icp.geographic_regions
                },
                "research_used": len(researched_companies),
                "detailed_research": len(detailed_company_data)
            }
            
        except Exception as e:
            self.logger.error(f"Error creating ICP from research - Error: {str(e)}")
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
            
            # Handle case where scrape_result might be a string or not properly structured
            if not isinstance(scrape_result, dict):
                self.logger.warning(f"Scrape result is not a dictionary: {type(scrape_result)}")
                if isinstance(scrape_result, str):
                    try:
                        scrape_result = json.loads(scrape_result)
                    except:
                        scrape_result = {"status": "error", "error_message": "Invalid scrape result format"}
                else:
                    scrape_result = {"status": "error", "error_message": f"Unexpected scrape result type: {type(scrape_result)}"}
            
            if scrape_result.get("status") != "success":
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
            7. IMPORTANT: List any specific customer companies mentioned (e.g., "Our customers include Microsoft, Amazon...")
            
            Return as structured JSON with insights for ICP creation. Include a "mentioned_customers" field with any customer company names found.
            """
            
            # Use process_json_request to prevent recursive function calls
            analysis = await self.process_json_request(analysis_prompt)
            
            # Try to parse the analysis to extract mentioned customers
            enriched_customers = []
            try:
                # Try to parse JSON response
                import json
                if isinstance(analysis, str):
                    # Clean up markdown formatting if present
                    if "```json" in analysis:
                        analysis = analysis[analysis.find("```json")+7:analysis.rfind("```")]
                    elif "```" in analysis:
                        analysis = analysis[analysis.find("```")+3:analysis.rfind("```")]
                    analysis_data = json.loads(analysis)
                else:
                    analysis_data = analysis
                
                # Extract mentioned customers
                mentioned_customers = analysis_data.get("mentioned_customers", [])
                
                # Enrich customer data using HDW if available
                if mentioned_customers and "horizondatawave" in self.external_clients:
                    self.logger.info(f"Found {len(mentioned_customers)} customer companies to enrich")
                    
                    for customer_name in mentioned_customers[:5]:  # Limit to 5 for efficiency
                        if customer_name and isinstance(customer_name, str):  # Ensure valid customer name
                            hdw_result = await self.search_companies_hdw(query=customer_name, limit=1)
                            
                            # Handle case where hdw_result might be a string or not properly structured
                            if not isinstance(hdw_result, dict):
                                self.logger.warning(f"HDW result is not a dictionary: {type(hdw_result)}")
                                if isinstance(hdw_result, str):
                                    try:
                                        hdw_result = json.loads(hdw_result)
                                    except:
                                        hdw_result = {"status": "error", "error_message": "Invalid HDW result format"}
                                else:
                                    hdw_result = {"status": "error", "error_message": f"Unexpected HDW result type: {type(hdw_result)}"}
                            
                            if hdw_result.get("status") == "success" and hdw_result.get("companies"):
                                company_data = hdw_result["companies"][0]
                                enriched_customers.append({
                                    "name": getattr(company_data, "name", customer_name),
                                    "industry": getattr(company_data, "industry", "Unknown"),
                                    "company_size": getattr(company_data, "company_size", "Unknown"),
                                    "linkedin_url": getattr(company_data, "linkedin_url", ""),
                                    "description": getattr(company_data, "description", "")
                                })
                    
                    if enriched_customers:
                        # Add enriched data back to analysis
                        if isinstance(analysis_data, dict):
                            analysis_data["enriched_customers"] = enriched_customers
                            analysis = json.dumps(analysis_data, indent=2)
                        
            except Exception as e:
                self.logger.warning(f"Could not parse/enrich customer data: {e}")
            
            return {
                "status": "success",
                "url": url,
                "analysis": analysis,
                "enriched_customers": enriched_customers,
                "raw_content": scrape_result["content"][:1000]
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing website - Url: {url}, Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def refine_icp_criteria(
        self,
        icp_id: str,
        feedback: str,
        specific_changes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refine ICP criteria based on feedback.
        
        WARNING: This method uses process_json_request() to prevent infinite recursion.
        Since this method is registered as a tool, the agent might call it recursively
        when asked to generate JSON. Always use process_json_request() or json_generation_mode()
        when this method needs JSON output from the LLM.
        
        Args:
            icp_id: ID of the ICP to refine
            feedback: User feedback on the ICP
            specific_changes: Specific changes to make
            
        Returns:
            Dictionary with refined ICP data
        """
        try:
            self.logger.info(f"Starting ICP refinement - Icp_Id: {icp_id}, Feedback_Length: {len(feedback)}")
            
            # Get existing ICP
            existing_icp = self.active_icps.get(icp_id)
            if not existing_icp:
                return {"status": "error", "error_message": "ICP not found"}
            
            # Convert ICP to JSON-serializable format
            icp_dict = self._safe_icp_to_dict(existing_icp)
            # Convert datetime objects to strings
            for key in ['created_at', 'updated_at']:
                if key in icp_dict and hasattr(icp_dict[key], 'isoformat'):
                    icp_dict[key] = icp_dict[key].isoformat()
            # Convert feedback history datetimes
            for feedback_item in icp_dict.get('feedback_history', []):
                if 'timestamp' in feedback_item and hasattr(feedback_item['timestamp'], 'isoformat'):
                    feedback_item['timestamp'] = feedback_item['timestamp'].isoformat()
            
            # Generate refinement prompt
            refinement_prompt = f"""
            Refine this Ideal Customer Profile based on user feedback:
            
            Current ICP:
            {json.dumps(icp_dict, indent=2, cls=DateTimeEncoder)}
            
            User Feedback:
            {feedback}
            
            Specific Changes Requested:
            {json.dumps(specific_changes, indent=2, cls=DateTimeEncoder) if specific_changes else "None"}
            
            Update the ICP while maintaining the same structure. Focus on:
            1. Incorporating the feedback
            2. Adjusting weights and criteria
            3. Adding/removing values as needed
            4. Updating description to reflect changes
            
            Return the complete updated ICP as JSON with the same structure.
            """
            
            # Use process_json_request to prevent infinite recursion
            # The LLM might call refine_icp_criteria recursively when it's available as a tool
            self.logger.warning("Using JSON generation mode to prevent infinite recursion in ICP refinement")
            response = await self.process_json_request(refinement_prompt)
            
            # Parse the response
            try:
                # Clean markdown formatting if present
                if response.startswith("```json"):
                    response = response[7:-3].strip()
                elif response.startswith("```"):
                    response = response[3:-3].strip()
                refined_data = json.loads(response)
            except json.JSONDecodeError:
                refined_data = self._safe_icp_to_dict(existing_icp)
                # Apply specific changes manually if JSON parsing fails
                if specific_changes:
                    refined_data.update(specific_changes)
            
            # Create refined ICP
            refined_icp = self._create_icp_from_data(refined_data)
            refined_icp.add_feedback(feedback, specific_changes or {})
            
            # Store the refined ICP
            self.active_icps[refined_icp.id] = refined_icp
            
            self.logger.info(f"ICP refinement completed successfully - Original_Id: {icp_id}, Refined_Id: {refined_icp.id}")
            
            return {
                "status": "success",
                "icp_id": refined_icp.id,
                "icp": self._safe_icp_to_dict(refined_icp),
                "changes_applied": True
            }
            
        except Exception as e:
            self.logger.error(f"Error refining ICP - Icp_Id: {icp_id}, Error: {str(e)}")
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
                    "icp": self._safe_icp_to_dict(icp)
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
            self.logger.error(f"Error exporting ICP - Icp_Id: {icp_id}, Error: {str(e)}")
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
    
    async def retrieve_past_icps(
        self,
        query: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Retrieve previously created ICPs from memory.
        
        Args:
            query: Search query (e.g., "last ICP", "B2B SaaS ICP")
            limit: Maximum number of ICPs to retrieve
            
        Returns:
            Dictionary with retrieved ICPs
        """
        try:
            if not query:
                query = "ICP ideal customer profile created"
            
            self.logger.info(f"Searching for past ICPs with query: {query}")
            
            # First check active ICPs in memory
            active_icps = []
            for icp_id, icp in self.active_icps.items():
                active_icps.append({
                    "id": icp_id,
                    "name": icp.name,
                    "summary": self._create_icp_summary(icp),
                    "icp": self._safe_icp_to_dict(icp)
                })
            
            if active_icps:
                self.logger.info(f"Found {len(active_icps)} active ICPs in memory")
                return {
                    "status": "success",
                    "source": "active_memory",
                    "icps": active_icps[:limit],
                    "message": f"Found {len(active_icps)} ICPs in active memory"
                }
            
            # If no active ICPs, prompt to use load_memory tool
            return {
                "status": "success",
                "source": "none",
                "icps": [],
                "message": "No active ICPs found. Please use the load_memory tool to search for ICPs from previous sessions.",
                "suggestion": "Try using: load_memory('ICP') or load_memory('ideal customer profile')"
            }
            
        except Exception as e:
            self.logger.error(f"Error retrieving past ICPs - Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    # Required abstract method implementations
    
    def get_capabilities(self) -> List[str]:
        """Return list of ICP agent capabilities."""
        return [
            "create_icp_from_research",
            "refine_icp_criteria",
            "export_icp",
            "search_companies_hdw",
            "search_industries_hdw",
            "search_locations_hdw",
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
    
    def _safe_icp_to_dict(self, icp: ICP) -> Dict[str, Any]:
        """Safely convert ICP to dictionary without circular references."""
        return {
            "id": icp.id,
            "name": icp.name,
            "description": icp.description,
            "industries": icp.industries,
            "target_roles": icp.target_roles,
            "seniority_levels": icp.seniority_levels,
            "departments": icp.departments,
            "pain_points": icp.pain_points,
            "goals": icp.goals,
            "company_size": icp.company_size,
            "geographic_regions": icp.geographic_regions,
            "tech_stack": icp.tech_stack,
            "tools_used": icp.tools_used,
            "buying_signals": icp.buying_signals,
            "exclusions": icp.exclusions,
            "created_at": icp.created_at.isoformat() if hasattr(icp.created_at, 'isoformat') else str(icp.created_at),
            "updated_at": icp.updated_at.isoformat() if hasattr(icp.updated_at, 'isoformat') else str(icp.updated_at),
            "version": icp.version,
            "feedback_history": icp.feedback_history,
            "source_materials": getattr(icp, 'source_materials', []),
            "confidence_score": getattr(icp, 'confidence_score', 0.0)
        }
    
    def _safe_serialize_business_info(self, business_info: Any) -> str:
        """Safely serialize business_info to avoid circular references."""
        try:
            # If it's already a dict, try to serialize directly
            if isinstance(business_info, dict):
                return json.dumps(business_info, indent=2, cls=DateTimeEncoder)
            
            # If it's an object with attributes, extract safe data
            if hasattr(business_info, '__dict__'):
                safe_data = {}
                for key, value in business_info.__dict__.items():
                    # Skip private attributes and methods
                    if key.startswith('_') or callable(value):
                        continue
                    
                    # Handle specific problematic types
                    if hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, list, dict)):
                        # Convert complex objects to string representation
                        safe_data[key] = str(value)
                    else:
                        safe_data[key] = value
                
                return json.dumps(safe_data, indent=2, cls=DateTimeEncoder)
            
            # Fallback to string representation
            return str(business_info)
            
        except (TypeError, ValueError, RecursionError) as e:
            self.logger.warning(f"Could not serialize business_info: {e}")
            # Create a minimal safe representation
            if hasattr(business_info, 'company_identifier'):
                return f"Business Info: {business_info.company_identifier}"
            else:
                return f"Business Info: {type(business_info).__name__} object"