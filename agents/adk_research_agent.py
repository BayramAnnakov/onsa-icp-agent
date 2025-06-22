"""Research Agent using Google ADK with external tools."""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.json_encoder import DateTimeEncoder
from .adk_base_agent import ADKAgent
from models import Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager
from integrations import HorizonDataWave, ExaWebsetsAPI, FirecrawlClient


class ADKResearchAgent(ADKAgent):
    """
    Research Agent built with Google ADK that conducts web research and analysis.
    
    Uses external tools for:
    - Website crawling and content extraction via Firecrawl
    - Company research via HorizonDataWave
    - People and content research via Exa
    """
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None, memory_manager=None):
        super().__init__(
            agent_name="research_agent",
            agent_description="Conducts comprehensive web research and analysis for business intelligence and competitive insights",
            config=config,
            cache_manager=cache_manager,
            memory_manager=memory_manager
        )
        
        # Research session management
        object.__setattr__(self, 'active_research_sessions', {})
        
        # Initialize external API clients
        self._setup_external_clients()
        
        # Setup tools - only add what Research agent needs
        self.setup_external_tools()  # This sets up memory tools from parent
        self.setup_research_specific_tools()
        self.setup_research_tools()
        
        self.logger.info("ADK Research Agent initialized")
    
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
    
    def setup_research_specific_tools(self) -> None:
        """Setup only the external tools that Research agent needs."""
        # Research agent primarily needs web scraping for deep website analysis
        self.setup_web_scraping_tools()
        
        # Research agent needs company search for competitive analysis
        self.add_external_tool(
            name="search_companies_hdw",
            description="Search for companies using HorizonDataWave API. Use when looking for company information, LinkedIn profiles, or business data.",
            func=self.search_companies_hdw
        )
        
        # Research agent uses basic people search for team research
        self.add_external_tool(
            name="search_people_exa",
            description="Search for people using Exa Websets API. Use when looking for contact information, people profiles, or decision makers.",
            func=self.search_people_exa
        )
        
        self.logger.info(f"Research-specific external tools configured - Tool_Count: {len(self.tools)}")
    
    def setup_research_tools(self) -> None:
        """Setup research-specific tools."""
        
        self.add_external_tool(
            name="analyze_company_comprehensive",
            description="Conduct comprehensive analysis of a company using multiple sources. Use when deep company research is needed.",
            func=self.analyze_company_comprehensive
        )
        
        self.add_external_tool(
            name="competitive_analysis",
            description="Analyze competitors in a specific industry or market. Use when understanding competitive landscape.",
            func=self.competitive_analysis
        )
        
        self.add_external_tool(
            name="industry_research",
            description="Research industry trends, challenges, and opportunities. Use when understanding market dynamics.",
            func=self.industry_research
        )
        
        self.add_external_tool(
            name="website_content_analysis",
            description="Deep analysis of website content for business insights. Use when extracting detailed business information.",
            func=self.website_content_analysis
        )
        
        self.add_external_tool(
            name="linkedin_company_research",
            description="Research company LinkedIn presence and employee information. Use when understanding company culture and team.",
            func=self.linkedin_company_research
        )
    
    async def analyze_company_comprehensive(
        self,
        company_identifier: str,
        analysis_depth: str = "standard",
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Conduct comprehensive company analysis.
        
        Args:
            company_identifier: Company name, domain, or LinkedIn URL
            analysis_depth: Depth of analysis (basic, standard, comprehensive)
            focus_areas: Specific areas to focus on (business_model, technology, team, etc.)
            
        Returns:
            Dictionary with comprehensive company analysis
        """
        try:
            if focus_areas is None:
                focus_areas = ["business_model", "technology", "customers", "market_position"]
            
            self.logger.info(f"Starting comprehensive company analysis - Company: {company_identifier}, Depth: {analysis_depth}")
            
            analysis_results = {
                "company_identifier": company_identifier,
                "analysis_timestamp": datetime.now().isoformat(),
                "sources_used": [],
                "findings": {}
            }
            
            # If identifier is a URL, analyze website first to extract company name
            extracted_company_name = None
            if company_identifier.startswith("http") or "." in company_identifier:
                if not company_identifier.startswith("http"):
                    company_identifier = f"https://{company_identifier}"
                
                # Analyze website first
                website_result = await self.website_content_analysis(
                    url=company_identifier,
                    analysis_focus=focus_areas
                )
                
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
                    analysis_results["findings"]["website_analysis"] = website_result["analysis"]
                    analysis_results["sources_used"].append("firecrawl")
                    
                    # Try to extract company name from website analysis
                    try:
                        if isinstance(website_result["analysis"], str):
                            import json, re
                            analysis_data = json.loads(website_result["analysis"])
                            # Look in business model section
                            if "analysis" in analysis_data:
                                business_section = analysis_data["analysis"].get("business_model", {})
                                desc = business_section.get("description", "")
                                # Extract company name patterns
                                name_match = re.search(r'([\w]+\.ai|[\w]+\s+(?:Inc|Corp|LLC|Ltd))', desc, re.IGNORECASE)
                                if name_match:
                                    extracted_company_name = name_match.group(1).replace(".ai", "").strip()
                    except Exception as e:
                        self.logger.debug(f"Could not extract company name from website: {e}")
            
            # Search for company in HorizonDataWave using name (not URL)
            search_query = extracted_company_name if extracted_company_name else (
                company_identifier if not company_identifier.startswith("http") else None
            )
            
            if "horizondatawave" in self.external_clients and search_query:
                self.logger.info(f"Searching HDW for: {search_query}")
                hdw_result = await self.search_companies_hdw(
                    query=search_query,
                    limit=1
                )
                
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
                    company_obj = hdw_result["companies"][0]
                    # Convert company object to dictionary
                    company_data = {
                        "name": getattr(company_obj, "name", None),
                        "industry": getattr(company_obj, "industry", None),
                        "company_size": getattr(company_obj, "company_size", None),
                        "description": getattr(company_obj, "description", None),
                        "website": getattr(company_obj, "website", None),
                        "linkedin_url": getattr(company_obj, "linkedin_url", None),
                        "founded_year": getattr(company_obj, "founded_year", None),
                        "specialties": getattr(company_obj, "specialties", [])
                    }
                    analysis_results["findings"]["linkedin_data"] = company_data
                    analysis_results["sources_used"].append("horizondatawave")
            
            # If we haven't done website analysis yet (i.e., company name was provided)
            if "website_analysis" not in analysis_results["findings"] and (company_identifier.startswith("http") or "." in company_identifier):
                if not company_identifier.startswith("http"):
                    company_identifier = f"https://{company_identifier}"
                
                website_result = await self.website_content_analysis(
                    url=company_identifier,
                    analysis_focus=focus_areas
                )
                
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
                    analysis_results["findings"]["website_analysis"] = website_result["analysis"]
                    analysis_results["sources_used"].append("firecrawl")
            
            # 3. Generate AI-powered insights (Skipping people research for ICP)
            insights_raw = await self._generate_company_insights(analysis_results["findings"], focus_areas)
            
            # Parse the JSON string returned by _generate_company_insights to maintain dict structure
            try:
                import json
                insights = json.loads(insights_raw) if isinstance(insights_raw, str) else insights_raw
            except (json.JSONDecodeError, TypeError):
                self.logger.debug("Failed to parse insights JSON, using raw string - this is expected when LLM returns markdown format")
                insights = {"raw_insights": insights_raw}
            
            analysis_results["insights"] = insights
            
            # 4. Store research session
            session_id = f"research_{int(datetime.now().timestamp())}"
            self.active_research_sessions[session_id] = analysis_results
            
            self.logger.info(f"Company analysis completed - Company: {company_identifier}, Sources: {len(analysis_results['sources_used'])}")
            
            return {
                "status": "success",
                "session_id": session_id,
                "analysis": analysis_results
            }
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive company analysis - Company: {company_identifier}, Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def competitive_analysis(
        self,
        target_company: str,
        industry: str,
        competitor_count: int = 5
    ) -> Dict[str, Any]:
        """Analyze competitors in the industry.
        
        Args:
            target_company: Main company to analyze
            industry: Industry to analyze
            competitor_count: Number of competitors to analyze
            
        Returns:
            Dictionary with competitive analysis
        """
        try:
            self.logger.info(f"Starting competitive analysis - Target: {target_company}, Industry: {industry}")
            
            competitive_analysis = {
                "target_company": target_company,
                "industry": industry,
                "analysis_timestamp": datetime.now().isoformat(),
                "competitors": [],
                "market_insights": {}
            }
            
            # 1. Find competitors via company search
            if "horizondatawave" in self.external_clients:
                competitors_result = await self.search_companies_hdw(
                    query=f"{industry} companies",
                    limit=competitor_count + 2  # Get extra to filter out target company
                )
                
                if competitors_result["status"] == "success":
                    potential_competitors = competitors_result["companies"]
                    
                    # Filter out target company
                    competitors = [
                        comp for comp in potential_competitors
                        if target_company.lower() not in comp.get("name", "").lower()
                    ][:competitor_count]
                    
                    competitive_analysis["competitors"] = competitors
            
            # 2. Analyze each competitor's website
            for competitor in competitive_analysis["competitors"][:3]:  # Limit detailed analysis
                website_url = competitor.get("website")
                if website_url:
                    website_analysis = await self.website_content_analysis(
                        url=website_url,
                        analysis_focus=["business_model", "pricing", "features"]
                    )
                    if website_analysis["status"] == "success":
                        competitor["website_analysis"] = website_analysis["analysis"]
            
            # 3. Generate competitive insights
            insights_prompt = f"""
            Analyze this competitive landscape and provide insights:
            
            Target Company: {target_company}
            Industry: {industry}
            Competitors: {json.dumps(competitive_analysis["competitors"][:3], indent=2, cls=DateTimeEncoder)}
            
            Provide insights on:
            1. Market positioning
            2. Competitive advantages/disadvantages
            3. Pricing strategies
            4. Target customer differences
            5. Technology approaches
            6. Market opportunities
            
            Return as structured JSON with competitive insights.
            """
            
            # Use process_json_request to prevent infinite recursion
            insights_raw = await self.process_json_request(insights_prompt)
            
            # Parse the JSON string to maintain dict structure
            try:
                import json
                insights = json.loads(insights_raw) if isinstance(insights_raw, str) else insights_raw
            except (json.JSONDecodeError, TypeError):
                self.logger.warning("Failed to parse competitive analysis insights JSON, using raw string")
                insights = {"raw_insights": insights_raw}
            
            competitive_analysis["market_insights"] = insights
            
            return {
                "status": "success",
                "competitive_analysis": competitive_analysis
            }
            
        except Exception as e:
            self.logger.error(f"Error in competitive analysis - Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def industry_research(
        self,
        industry: str,
        research_focus: Optional[List[str]] = None,
        depth: str = "standard"
    ) -> Dict[str, Any]:
        """Research industry trends and insights.
        
        Args:
            industry: Industry to research
            research_focus: Specific areas to focus on
            depth: Research depth
            
        Returns:
            Dictionary with industry research
        """
        try:
            if research_focus is None:
                research_focus = ["trends", "challenges", "opportunities", "key_players"]
            
            self.logger.info(f"Starting industry research - Industry: {industry}, Focus: {research_focus}")
            
            research_results = {
                "industry": industry,
                "research_timestamp": datetime.now().isoformat(),
                "focus_areas": research_focus,
                "findings": {}
            }
            
            # 1. Find key companies in the industry
            if "horizondatawave" in self.external_clients:
                companies_result = await self.search_companies_hdw(
                    query=f"{industry} companies leaders",
                    limit=10
                )
                if companies_result["status"] == "success":
                    research_results["findings"]["key_companies"] = companies_result["companies"]
            
            # 2. Research industry content via Exa
            if "exa" in self.external_clients:
                content_result = await self.search_people_exa(
                    query=f"{industry} trends challenges opportunities 2024",
                    limit=5
                )
                if content_result["status"] == "success":
                    research_results["findings"]["industry_content"] = content_result["people"]
            
            # 3. Generate industry insights
            insights_prompt = f"""
            Analyze this industry and provide comprehensive insights:
            
            Industry: {industry}
            Key Companies: {json.dumps(research_results["findings"].get("key_companies", [])[:3], indent=2, cls=DateTimeEncoder)}
            Research Focus: {research_focus}
            
            Provide detailed analysis of:
            1. Current industry trends
            2. Major challenges facing the industry
            3. Emerging opportunities
            4. Key market players and their strategies
            5. Technology disruptions
            6. Future outlook
            
            Return as structured JSON with industry insights.
            """
            
            # Use process_json_request to prevent infinite recursion
            insights_raw = await self.process_json_request(insights_prompt)
            
            # Parse the JSON string to maintain dict structure
            try:
                import json
                insights = json.loads(insights_raw) if isinstance(insights_raw, str) else insights_raw
            except (json.JSONDecodeError, TypeError):
                self.logger.warning("Failed to parse industry research insights JSON, using raw string")
                insights = {"raw_insights": insights_raw}
            
            research_results["insights"] = insights
            
            return {
                "status": "success",
                "industry_research": research_results
            }
            
        except Exception as e:
            self.logger.error(f"Error in industry research - Industry: {industry}, Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def website_content_analysis(
        self,
        url: str,
        analysis_focus: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Deep analysis of website content.
        
        Args:
            url: Website URL to analyze
            analysis_focus: Specific aspects to focus on
            
        Returns:
            Dictionary with website analysis
        """
        try:
            if analysis_focus is None:
                analysis_focus = ["business_model", "target_market", "technology", "pricing"]
            
            # Scrape website content
            scrape_result = await self.scrape_website_firecrawl(
                url=url,
                include_links=True,
                max_depth=2
            )
            
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
            Conduct deep analysis of this website content:
            
            URL: {url}
            Content: {str(scrape_result.get("content", ""))[:4000]}...
            
            Analysis Focus: {analysis_focus}
            
            Extract and analyze:
            1. Business model and value proposition
            2. Target customers and market
            3. Products/services offered
            4. Pricing strategy (if mentioned)
            5. Technology stack indicators
            6. Company culture and values
            7. Competitive positioning
            8. Contact information and team
            
            Return as structured JSON with detailed analysis for each focus area.
            """
            
            # Use process_json_request to prevent infinite recursion
            analysis_raw = await self.process_json_request(analysis_prompt)
            
            # Parse the JSON string to maintain dict structure
            try:
                import json
                analysis = json.loads(analysis_raw) if isinstance(analysis_raw, str) else analysis_raw
            except (json.JSONDecodeError, TypeError):
                self.logger.warning("Failed to parse website analysis JSON, using raw string")
                analysis = {"raw_analysis": analysis_raw}
            
            return {
                "status": "success",
                "url": url,
                "analysis": analysis,
                "content_length": len(scrape_result["content"]),
                "analysis_focus": analysis_focus
            }
            
        except Exception as e:
            self.logger.error(f"Error in website content analysis - Url: {url}, Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def linkedin_company_research(
        self,
        company_name: str,
        research_depth: str = "standard"
    ) -> Dict[str, Any]:
        """Research company LinkedIn presence.
        
        Args:
            company_name: Name of company to research
            research_depth: Depth of research
            
        Returns:
            Dictionary with LinkedIn research results
        """
        try:
            self.logger.info(f"Starting LinkedIn company research - Company: {company_name}")
            
            # Search for company in HorizonDataWave (LinkedIn data)
            if "horizondatawave" not in self.external_clients:
                return {"status": "error", "error_message": "HorizonDataWave client not available"}
            
            hdw_result = await self.search_companies_hdw(
                query=company_name,
                limit=1
            )
            
            if hdw_result["status"] != "success" or not hdw_result["companies"]:
                return {"status": "error", "error_message": "Company not found in LinkedIn data"}
            
            company_data = hdw_result["companies"][0]
            
            # Enhance with people search if deep research requested
            team_data = []
            if research_depth in ["comprehensive", "deep"]:
                people_result = await self.search_people_exa(
                    query=f"{company_name} employees team members",
                    limit=15
                )
                if people_result["status"] == "success":
                    team_data = people_result["people"]
            
            return {
                "status": "success",
                "company_data": company_data,
                "team_data": team_data,
                "research_depth": research_depth
            }
            
        except Exception as e:
            self.logger.error(f"Error in LinkedIn company research - Company: {company_name}, Error: {str(e)}")
            return {"status": "error", "error_message": str(e)}
    
    async def _generate_company_insights(
        self,
        findings: Dict[str, Any],
        focus_areas: List[str]
    ) -> str:
        """Generate AI-powered insights from research findings."""
        
        insights_prompt = f"""
        Generate comprehensive insights from this company research:
        
        Research Findings:
        {json.dumps(findings, indent=2, cls=DateTimeEncoder)}
        
        Focus Areas: {focus_areas}
        
        Provide insights on:
        1. Business model and strategy
        2. Market position and competitive advantages
        3. Technology and innovation approach
        4. Growth trajectory and potential
        5. Challenges and opportunities
        6. Ideal customer profile indicators
        7. Target customer characteristics
        
        Return as structured JSON analysis with clear insights and recommendations.
        Format your response as valid JSON with the following structure:
        {{
            "business_model_strategy": "analysis here",
            "market_position": "analysis here", 
            "technology_innovation": "analysis here",
            "growth_potential": "analysis here",
            "challenges_opportunities": "analysis here",
            "icp_indicators": "analysis here",
            "target_characteristics": "analysis here"
        }}
        """
        
        # Use process_json_request to prevent infinite recursion
        return await self.process_json_request(insights_prompt)
    
    # Required abstract method implementations
    
    def get_capabilities(self) -> List[str]:
        """Return list of Research agent capabilities."""
        return [
            "analyze_company_comprehensive",
            "competitive_analysis",
            "industry_research",
            "website_content_analysis",
            "linkedin_company_research",
            "search_companies_hdw",
            "search_people_exa",
            "scrape_website_firecrawl"
        ]
    
    async def execute_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute research-related tasks."""
        
        task_handlers = {
            "analyze_sources": self._handle_analyze_sources_task,
            "competitive_research": self._handle_competitive_research_task,
            "industry_analysis": self._handle_industry_analysis_task,
            "website_analysis": self._handle_website_analysis_task
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
        """Process research-related queries."""
        
        # Use Google ADK to process the query with tools
        return await self.process_message(query, conversation_id, context)
    
    # Task handlers
    
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
                    analysis = await self.website_content_analysis(url)
                    findings[url] = analysis
            elif source.get("type") == "company":
                company = source.get("name") or source.get("url")
                if company:
                    analysis = await self.analyze_company_comprehensive(company)
                    findings[company] = analysis
        
        return {"status": "success", "findings": findings}
    
    async def _handle_competitive_research_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle competitive research task."""
        
        return await self.competitive_analysis(
            target_company=task_data.get("target_company"),
            industry=task_data.get("industry"),
            competitor_count=task_data.get("competitor_count", 5)
        )
    
    async def _handle_industry_analysis_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle industry analysis task."""
        
        return await self.industry_research(
            industry=task_data.get("industry"),
            research_focus=task_data.get("focus_areas"),
            depth=task_data.get("depth", "standard")
        )
    
    async def _handle_website_analysis_task(
        self,
        task_data: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle website analysis task."""
        
        return await self.website_content_analysis(
            url=task_data.get("url"),
            analysis_focus=task_data.get("focus_areas")
        )