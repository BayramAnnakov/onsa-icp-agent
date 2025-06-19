"""
Main orchestrator using Google ADK agents with external tools.

This is the primary entry point that coordinates all ADK-based agents and manages the user workflow.
"""

import asyncio
import json
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from agents.adk_icp_agent import ADKICPAgent
from agents.adk_research_agent import ADKResearchAgent  
from agents.adk_prospect_agent import ADKProspectAgent
from models import Conversation, WorkflowStep, MessageRole
from utils.config import Config
from utils.cache import CacheManager
from integrations import HorizonDataWave, ExaWebsetsAPI, FirecrawlClient


class ADKAgentOrchestrator:
    """
    Main orchestrator using Google ADK agents with external tool integration.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = structlog.get_logger().bind(component="adk_orchestrator")
        
        # Initialize cache manager
        self.cache_manager = CacheManager(config.cache)
        
        # Initialize ADK agents with external tools
        self.icp_agent = ADKICPAgent(config, self.cache_manager)
        self.research_agent = ADKResearchAgent(config, self.cache_manager)
        self.prospect_agent = ADKProspectAgent(config, self.cache_manager)
        
        # Active conversations
        self.conversations: Dict[str, Conversation] = {}
        self.current_conversation: Optional[Conversation] = None
        
        self.logger.info("ADK Agent orchestrator initialized")
    
    async def start_conversation(self, user_id: str) -> str:
        """Start a new conversation session."""
        
        conversation_id = f"conv_{user_id}_{int(datetime.now().timestamp())}"
        
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id
        )
        
        self.conversations[conversation_id] = conversation
        self.current_conversation = conversation
        
        # Welcome message
        welcome_message = """
Welcome to the Google ADK Multi-Agent Sales Lead Generation System!

I'll help you create an Ideal Customer Profile (ICP) and find high-quality prospects using:
- Google ADK for intelligent agent coordination
- HorizonDataWave for LinkedIn company data
- Exa for people and content research  
- Firecrawl for website analysis

Let's start by understanding your business. Please tell me:
1. What does your company do?
2. What products or services do you offer?
3. Who are your current best customers?
4. Do you have any company websites or LinkedIn profiles you'd like me to analyze?

You can also provide links to:
- Your company website
- LinkedIn profiles of ideal customers
- Example customer companies
- Any supporting documents
        """.strip()
        
        conversation.add_message(MessageRole.ASSISTANT, welcome_message)
        
        self.logger.info("Started new ADK conversation", conversation_id=conversation_id, user_id=user_id)
        
        return conversation_id
    
    async def process_user_message(
        self,
        conversation_id: str,
        message: str,
        attachments: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Process a user message using ADK agents."""
        
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return "Conversation not found. Please start a new conversation."
        
        # Add user message to conversation
        conversation.add_message(MessageRole.USER, message, attachments=attachments or [])
        
        # Update current conversation
        self.current_conversation = conversation
        
        self.logger.info(
            "Processing user message with ADK agents",
            conversation_id=conversation_id,
            current_step=conversation.current_step.value,
            message_length=len(message)
        )
        
        # Route to appropriate workflow step handler
        step_handlers = {
            WorkflowStep.BUSINESS_DESCRIPTION: self._handle_business_description,
            WorkflowStep.ICP_CREATION: self._handle_icp_creation,
            WorkflowStep.ICP_REFINEMENT: self._handle_icp_refinement,
            WorkflowStep.PROSPECT_SEARCH: self._handle_prospect_search,
            WorkflowStep.PROSPECT_REVIEW: self._handle_prospect_review,
            WorkflowStep.FINAL_APPROVAL: self._handle_final_approval,
            WorkflowStep.AUTOMATION_SETUP: self._handle_automation_setup
        }
        
        handler = step_handlers.get(conversation.current_step)
        if handler:
            try:
                response = await handler(conversation, message, attachments or [])
                conversation.add_message(MessageRole.ASSISTANT, response)
                return response
            except Exception as e:
                error_message = f"I encountered an error: {str(e)}. Let me try a different approach."
                conversation.add_message(MessageRole.ASSISTANT, error_message)
                self.logger.error("Error in ADK step handler", step=conversation.current_step.value, error=str(e))
                return error_message
        else:
            return "I'm not sure how to handle this step. Please contact support."
    
    async def _handle_business_description(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle the business description phase using ADK agents."""
        
        # Store business information
        conversation.business_info.update({
            "description": message,
            "provided_at": datetime.now().isoformat()
        })
        
        # Process any attachments (URLs, documents) using Research Agent
        if attachments:
            conversation.source_materials.extend(attachments)
            
            # Extract URLs for analysis
            urls = [att.get("url") for att in attachments if att.get("url")]
            if urls:
                try:
                    # Use Research Agent to analyze provided sources
                    for url in urls[:3]:  # Limit to 3 URLs
                        analysis_result = await self.research_agent.website_content_analysis(
                            url=url,
                            analysis_focus=["business_model", "target_market", "products"]
                        )
                        
                        if analysis_result["status"] == "success":
                            conversation.business_info.setdefault("research_findings", []).append(analysis_result)
                    
                except Exception as e:
                    self.logger.error("Error analyzing source materials with Research Agent", error=str(e))
        
        # Move to ICP creation
        conversation.advance_step(WorkflowStep.ICP_CREATION)
        
        # Automatically trigger ICP creation
        icp_response = await self._handle_icp_creation(conversation, "", [])
        
        return f"""
Thank you for providing that information! I've analyzed your business details using our AI research tools.

Let me now create an initial Ideal Customer Profile (ICP) for you using Google ADK agents and external data sources.

{icp_response}
        """.strip()
    
    async def _handle_icp_creation(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle ICP creation using ADK ICP Agent."""
        
        try:
            # Extract company URLs from source materials for research
            example_companies = []
            for material in conversation.source_materials:
                if material.get("type") == "url" and "http" in material.get("url", ""):
                    example_companies.append(material["url"])
            
            # Use ADK ICP Agent to create ICP with research
            icp_result = await self.icp_agent.create_icp_from_research(
                business_info=conversation.business_info,
                example_companies=example_companies,
                research_depth="standard"
            )
            
            if icp_result["status"] != "success":
                return f"I encountered an error creating your ICP: {icp_result.get('error_message', 'Unknown error')}. Could you provide more details about your ideal customers?"
            
            # Store ICP ID
            conversation.current_icp_id = icp_result.get("icp_id")
            conversation.icp_versions.append(icp_result.get("icp_id"))
            
            # Format ICP for user review
            icp_data = icp_result.get("icp", {})
            formatted_icp = self._format_icp_for_display(icp_data)
            
            # Move to refinement phase
            conversation.advance_step(WorkflowStep.ICP_REFINEMENT)
            
            return f"""
I've created your initial Ideal Customer Profile using Google ADK and multi-source research! Here's what I found:

{formatted_icp}

**Research Sources Used:**
- Company data from HorizonDataWave: {"✓" if "horizondatawave" in icp_result.get("icp", {}).get("source_materials", []) else "○"}
- Website analysis via Firecrawl: {"✓" if example_companies else "○"}  
- Industry insights from Exa: {"✓" if "exa" in icp_result.get("icp", {}).get("source_materials", []) else "○"}
- Companies researched: {icp_result.get("research_used", 0)}

Please review this ICP and let me know:
1. Does this accurately represent your ideal customers?
2. Are there any characteristics I should add, remove, or modify?
3. Should I adjust the importance/weight of any criteria?

Once you're satisfied with the ICP, I'll use it to search for prospects using our external data sources.
            """.strip()
            
        except Exception as e:
            self.logger.error("Error creating ICP with ADK agent", error=str(e))
            return f"I encountered an error creating your ICP: {str(e)}. Could you provide more details about your ideal customers?"
    
    async def _handle_icp_refinement(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle ICP refinement using ADK ICP Agent."""
        
        # Check if user is satisfied or wants changes
        if any(word in message.lower() for word in ["good", "looks good", "approved", "proceed", "search"]):
            # User approves ICP, move to prospect search
            conversation.advance_step(WorkflowStep.PROSPECT_SEARCH)
            
            # Automatically trigger prospect search
            search_response = await self._handle_prospect_search(conversation, "", [])
            
            return f"""
Great! Your ICP looks good. Now I'll search for prospects using Google ADK agents and multiple data sources.

I'll search through:
- HorizonDataWave for LinkedIn company data
- Exa for people and contact information  
- Firecrawl for website analysis and enrichment

{search_response}
            """.strip()
        
        else:
            # User wants refinements - use ADK ICP Agent
            try:
                refinement_result = await self.icp_agent.refine_icp_criteria(
                    icp_id=conversation.current_icp_id,
                    feedback=message,
                    specific_changes={}  # Could parse specific changes from message
                )
                
                if refinement_result["status"] != "success":
                    return f"I had trouble refining the ICP: {refinement_result.get('error_message', 'Unknown error')}. Could you be more specific about what you'd like to change?"
                
                # Update ICP version
                conversation.icp_versions.append(refinement_result.get("icp_id"))
                conversation.current_icp_id = refinement_result.get("icp_id")
                
                # Format refined ICP
                refined_icp = refinement_result.get("icp", {})
                formatted_icp = self._format_icp_for_display(refined_icp)
                
                return f"""
I've updated your ICP based on your feedback using AI analysis:

{formatted_icp}

**Refinement Applied:**
- User feedback incorporated using Google ADK
- Criteria weights and values adjusted
- ICP version updated

How does this look now? Please let me know if you'd like any other changes, or if you're ready for me to search for prospects using our external data sources.
                """.strip()
                
            except Exception as e:
                self.logger.error("Error refining ICP with ADK agent", error=str(e))
                return f"I had trouble refining the ICP: {str(e)}. Could you be more specific about what you'd like to change?"
    
    async def _handle_prospect_search(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle prospect search using ADK Prospect Agent."""
        
        try:
            # Get ICP criteria
            icp_export = await self.icp_agent.export_icp(
                icp_id=conversation.current_icp_id,
                format="json"
            )
            
            if icp_export["status"] != "success":
                return "I couldn't retrieve your ICP for prospect search. Please try again."
            
            icp_criteria = icp_export["icp"]
            
            # Use ADK Prospect Agent to search for prospects
            search_result = await self.prospect_agent.search_prospects_multi_source(
                icp_criteria=icp_criteria,
                search_limit=50,
                sources=["hdw", "exa"],
                location_filter="United States, Canada, United Kingdom"
            )
            
            if search_result["status"] != "success":
                return f"I encountered an error searching for prospects: {search_result.get('error_message', 'Unknown error')}. Let me try again with different parameters."
            
            prospects = search_result.get("prospects", [])
            
            # Store prospect IDs
            conversation.current_prospects = [p.get("id") for p in prospects]
            
            # Get top 10 highest-scoring prospects for review
            if prospects:
                ranking_result = await self.prospect_agent.rank_prospects_by_score(
                    prospect_ids=conversation.current_prospects,
                    ranking_criteria={"sort_by": "total_score", "min_score": 0.0},
                    limit=10
                )
                
                if ranking_result["status"] == "success":
                    top_prospects = ranking_result["prospects"]
                else:
                    top_prospects = prospects[:10]
            else:
                top_prospects = []
            
            # Format prospects for display
            formatted_prospects = self._format_prospects_for_display(top_prospects)
            
            # Move to prospect review
            conversation.advance_step(WorkflowStep.PROSPECT_REVIEW)
            
            return f"""
I found {len(prospects)} prospects using Google ADK agents and scored them against your ICP!

**Search Results:**
- Companies found via HorizonDataWave: {search_result.get("companies_found", 0)}
- People found via Exa: {search_result.get("people_found", 0)}
- Total prospects created: {len(prospects)}
- Sources used: {", ".join(search_result.get("sources_used", []))}

**Top 10 Highest-Scoring Prospects:**

{formatted_prospects}

Please review these prospects and let me know:
1. Do these look like good potential customers?
2. Which ones would you prioritize?
3. Are there any you would exclude and why?
4. Should I adjust the scoring criteria?

Your feedback will help me improve the prospect selection using AI analysis.
            """.strip()
            
        except Exception as e:
            self.logger.error("Error searching prospects with ADK agent", error=str(e))
            return f"I encountered an error searching for prospects: {str(e)}. Let me try again with different parameters."
    
    async def _handle_prospect_review(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle prospect review using ADK Prospect Agent."""
        
        # Use LLM to analyze user intent for approval/refinement
        intent_analysis = await self._analyze_prospect_feedback_intent(message)
        
        if intent_analysis["is_approval"]:
            # Move to final approval
            conversation.advance_step(WorkflowStep.FINAL_APPROVAL)
            
            # Generate final report using ADK Prospect Agent
            try:
                report_result = await self.prospect_agent.generate_prospect_insights(
                    prospect_ids=conversation.current_prospects[:10],
                    analysis_type="summary"
                )
                
                if report_result["status"] == "success":
                    insights = report_result["insights"]
                    
                    return f"""
Excellent! Here's your final prospect analysis generated by Google ADK:

**AI-Generated Insights:**
{insights}

**Summary:**
- Total prospects analyzed: {report_result.get("prospects_analyzed", 0)}
- Analysis powered by Google ADK and external data sources
- Multi-source verification complete

Would you like me to set up automated prospect monitoring using ADK agents? I can:
- Continuously search for new prospects matching your ICP
- Send you daily/weekly updates with new qualified leads
- Use AI to refine searches based on your feedback
                    """.strip()
                else:
                    return "I'll finalize your prospect list. Would you like me to set up automated monitoring for new prospects using ADK agents?"
                
            except Exception as e:
                self.logger.error("Error generating final report with ADK agent", error=str(e))
                return "I'll finalize your prospect list. Would you like me to set up automated monitoring for new prospects?"
        
        elif intent_analysis["is_question"]:
            # User is asking questions - provide clarification
            return """
I'd be happy to help clarify! Here's what each element means:

**Score Explanation:**
- 🟢 0.8-1.0: Excellent match to your ICP
- 🟡 0.6-0.8: Good match with some minor gaps  
- 🔴 0.0-0.6: Poor match, significant gaps

**What you can do:**
1. **"These look good"** or **"Approve"** → Move to final steps
2. **Give specific feedback** → "I don't like #3, focus on larger companies"
3. **Ask for adjustments** → "Can you find more VP-level prospects?"

Which prospects interest you most, or what would you like to adjust?
            """.strip()
            
        else:
            # User wants to iterate - process feedback and refine
            try:
                # Use LLM to parse feedback and identify good/bad prospects
                parse_prompt = f"""
                Analyze the user's feedback about the prospects and extract:
                1. Which prospect numbers they liked (if any)
                2. Which prospect numbers they didn't like (if any)
                3. General feedback about what to change
                
                User feedback: {message}
                
                Total prospects shown: 10 (numbered 1-10)
                
                Return a JSON object with:
                {{
                    "liked_prospects": [list of prospect numbers they liked, e.g. [1, 3, 5]],
                    "disliked_prospects": [list of prospect numbers they didn't like, e.g. [2, 4]],
                    "general_feedback": "summary of what they want changed",
                    "specific_requests": {{
                        "company_size": "preference if mentioned",
                        "industry": "preference if mentioned", 
                        "seniority": "preference if mentioned",
                        "location": "preference if mentioned",
                        "other": "any other specific requests"
                    }}
                }}
                
                Note: The user might provide feedback in any language or format. Extract the meaning regardless of language.
                """
                
                # Use the ICP agent to parse (it has LLM capabilities)
                parse_response = await self.icp_agent.process_message(parse_prompt)
                
                try:
                    parsed_feedback = json.loads(parse_response)
                except json.JSONDecodeError:
                    # Fallback to empty lists if parsing fails
                    parsed_feedback = {
                        "liked_prospects": [],
                        "disliked_prospects": [],
                        "general_feedback": message,
                        "specific_requests": {}
                    }
                
                # Convert prospect numbers to IDs
                good_prospect_ids = []
                bad_prospect_ids = []
                
                for num in parsed_feedback.get("liked_prospects", []):
                    if 0 < num <= len(conversation.current_prospects):
                        good_prospect_ids.append(conversation.current_prospects[num-1])
                
                for num in parsed_feedback.get("disliked_prospects", []):
                    if 0 < num <= len(conversation.current_prospects):
                        bad_prospect_ids.append(conversation.current_prospects[num-1])
                
                # Get current ICP
                icp_export = await self.icp_agent.export_icp(
                    icp_id=conversation.current_icp_id,
                    format="json"
                )
                
                if icp_export["status"] != "success":
                    return "I couldn't retrieve your ICP for refinement. Please try again."
                
                icp_criteria = icp_export["icp"]
                
                # Use prospect agent to refine search based on feedback
                refinement_result = await self.prospect_agent.refine_prospect_search(
                    current_prospects=conversation.current_prospects,
                    feedback=message,
                    good_prospect_ids=good_prospect_ids,
                    bad_prospect_ids=bad_prospect_ids,
                    icp_criteria=icp_criteria
                )
                
                if refinement_result["status"] != "success":
                    return f"I had trouble refining the search: {refinement_result.get('error_message', 'Unknown error')}. Could you provide more specific feedback?"
                
                # Update prospect list
                new_prospects = refinement_result["prospects"]
                conversation.current_prospects = [p.get("id") if isinstance(p, dict) else p.id for p in new_prospects]
                
                # Get top 10 for display
                if new_prospects:
                    ranking_result = await self.prospect_agent.rank_prospects_by_score(
                        prospect_ids=conversation.current_prospects,
                        ranking_criteria={"sort_by": "total_score", "min_score": 0.0},
                        limit=10
                    )
                    
                    if ranking_result["status"] == "success":
                        top_prospects = ranking_result["prospects"]
                    else:
                        top_prospects = new_prospects[:10]
                else:
                    top_prospects = []
                
                # Format prospects for display
                formatted_prospects = self._format_prospects_for_display(top_prospects)
                
                # Get refinements applied
                refinements = refinement_result.get("refinements_applied", {})
                refinement_summary = []
                
                if refinements.get("refined_criteria"):
                    criteria = refinements["refined_criteria"]
                    if "company_size" in criteria:
                        refinement_summary.append(f"• Company size: {', '.join(criteria['company_size'])}")
                    if "industries" in criteria:
                        refinement_summary.append(f"• Industries: {', '.join(criteria['industries'][:3])}")
                    if "job_titles" in criteria:
                        refinement_summary.append(f"• Job titles: {', '.join(criteria['job_titles'][:3])}")
                
                return f"""
I've refined the prospect search based on your feedback using Google ADK analysis!

**Refinements Applied:**
{chr(10).join(refinement_summary) if refinement_summary else "• AI-based adjustments to match your preferences"}
• Similarity scoring based on your examples
• Feedback incorporated into search parameters

**Updated Top 10 Prospects:**

{formatted_prospects}

**Search Results:**
- Total prospects found: {len(new_prospects)}
- Feedback processed: ✓
- AI refinement applied: ✓

How do these prospects look? You can:
1. Provide more feedback to further refine
2. Approve to move forward
3. Specify exact criteria to adjust

What would you like to do?
                """.strip()
                
            except Exception as e:
                self.logger.error("Error processing prospect feedback", error=str(e))
                return f"""
I understand you'd like to adjust the prospect selection. Let me help you refine the search.

Could you be more specific about:
1. Which prospects you liked and why? (e.g., "I like #1 and #3")
2. Which prospects you didn't like and why? (e.g., "Not #2 - wrong industry")  
3. What characteristics should I prioritize? (e.g., "Focus on larger companies")

I'll use this feedback to improve the prospect selection using AI analysis.
                """.strip()
    
    async def _handle_final_approval(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle final approval and automation setup."""
        
        if any(word in message.lower() for word in ["yes", "setup", "automate", "monitor"]):
            conversation.advance_step(WorkflowStep.AUTOMATION_SETUP)
            conversation.automation_enabled = True
            
            return """
Perfect! I've set up automated prospect monitoring using Google ADK agents.

**ADK Automation Details:**
- Frequency: Daily monitoring with AI-powered search
- Sources: HorizonDataWave + Exa AI + Firecrawl
- Intelligence: Google ADK agents continuously learn and improve
- Notification: Daily summaries of new high-quality prospects
- Quality threshold: Only prospects scoring above 0.6 will be included

**Your ICP and preferences have been saved and will be used by:**
- ADK ICP Agent: For profile refinement
- ADK Research Agent: For market intelligence  
- ADK Prospect Agent: For lead discovery and scoring

**Next Steps:**
1. ADK agents start monitoring immediately
2. You'll receive your first update within 24 hours
3. Provide feedback to help agents learn and improve
4. AI-powered refinement based on your interactions

Thank you for using the Google ADK Multi-Agent Sales Lead Generation System! 🎯
            """.strip()
        
        else:
            conversation.advance_step(WorkflowStep.COMPLETED)
            
            return """
No problem! Your ICP and prospect list have been saved with Google ADK.

**What you have:**
- AI-generated ICP based on multi-source research
- List of 50 scored prospects from HorizonDataWave and Exa
- Top 10 highest-priority prospects for immediate outreach
- All data processed and validated by Google ADK agents

You can return anytime to:
- Set up automated monitoring with ADK agents
- Refine your ICP using AI feedback
- Search for more prospects with improved criteria
- Export your prospect data in various formats

Thank you for using our Google ADK system! Feel free to reach out when you need more prospects.
            """.strip()
    
    async def _handle_automation_setup(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle automation setup completion."""
        
        conversation.advance_step(WorkflowStep.COMPLETED)
        
        return """
Your Google ADK automated prospect monitoring is now active! 

The AI agents are working in the background to continuously find new prospects that match your ICP. 
You'll receive regular updates with fresh leads powered by intelligent analysis.

Is there anything else I can help you with today?
        """.strip()
    
    def _format_icp_for_display(self, icp_data: Dict[str, Any]) -> str:
        """Format ICP data for user-friendly display."""
        
        formatted = f"""
**{icp_data.get('name', 'Your ICP')}**

{icp_data.get('description', '')}

**Target Companies:**
- Industries: {', '.join(icp_data.get('industries', []))}
- Company Size: {self._extract_company_size(icp_data)}
- Technologies: {', '.join(icp_data.get('tech_stack', []))}

**Target People:**
- Roles: {', '.join(icp_data.get('target_roles', []))}
- Departments: {self._extract_departments(icp_data)}

**Key Pain Points:**
{chr(10).join([f"- {pain}" for pain in icp_data.get('pain_points', [])])}

**Buying Signals:**
{chr(10).join([f"- {signal}" for signal in icp_data.get('buying_signals', [])])}
        """.strip()
        
        return formatted
    
    def _extract_company_size(self, icp_data: Dict[str, Any]) -> str:
        """Extract company size from ICP criteria."""
        company_criteria = icp_data.get('company_criteria', {})
        size_criteria = company_criteria.get('company_size', {})
        if isinstance(size_criteria, dict) and 'values' in size_criteria:
            return ', '.join(size_criteria['values'])
        return "Any"
    
    def _extract_departments(self, icp_data: Dict[str, Any]) -> str:
        """Extract departments from ICP criteria."""
        person_criteria = icp_data.get('person_criteria', {})
        dept_criteria = person_criteria.get('department', {})
        if isinstance(dept_criteria, dict) and 'values' in dept_criteria:
            return ', '.join(dept_criteria['values'])
        return "Any"
    
    def _format_prospects_for_display(self, prospects: List[Dict[str, Any]]) -> str:
        """Format prospects for user-friendly display with enhanced formatting."""
        
        # Create a summary table first
        table_lines = ["| # | Name | Title | Company | Score |", 
                      "|---|------|-------|---------|-------|"]
        
        for i, prospect in enumerate(prospects[:10], 1):
            company = prospect.get('company', {})
            person = prospect.get('person', {})
            score = prospect.get('score', {})
            
            # Format score with emoji
            score_val = score.get('total_score', 0)
            if score_val >= 0.8:
                score_emoji = "🟢"
            elif score_val >= 0.6:
                score_emoji = "🟡"
            else:
                score_emoji = "🔴"
            
            name = f"{person.get('first_name', 'Unknown')} {person.get('last_name', '')}"
            title = person.get('title', 'Unknown')[:30]
            company_name = company.get('name', 'Unknown')[:25]
            
            table_lines.append(f"| {i} | {name} | {title} | {company_name} | {score_emoji} {score_val:.2f} |")
        
        # Add detailed view
        detailed_prospects = []
        
        for i, prospect in enumerate(prospects[:10], 1):
            company = prospect.get('company', {})
            person = prospect.get('person', {})
            score = prospect.get('score', {})
            
            # Make LinkedIn URL clickable if available
            linkedin = person.get('linkedin_url', '')
            linkedin_display = f"[View Profile]({linkedin})" if linkedin and linkedin != 'Not available' else 'Not available'
            
            email = person.get('email', 'Not available')
            email_display = f"`{email}`" if email != 'Not available' else email
            
            formatted_prospect = f"""
<details>
<summary><b>{i}. {person.get('first_name', 'Unknown')} {person.get('last_name', 'Person')}</b> - {person.get('title', 'Unknown Title')}</summary>

**Company:** {company.get('name', 'Unknown Company')}  
**Industry:** {company.get('industry', 'Unknown')}  
**Size:** {company.get('employee_range', 'Unknown')}  
**Location:** {company.get('headquarters', 'Unknown')}  

**Score:** {score.get('total_score', 0):.2f}/1.0 (AI-Generated)  
**Email:** {email_display}  
**LinkedIn:** {linkedin_display}  

</details>"""
            
            detailed_prospects.append(formatted_prospect)
        
        return "\n".join(table_lines) + "\n\n**Detailed View (click to expand):**\n\n" + '\n'.join(detailed_prospects)
    
    async def _analyze_prospect_feedback_intent(self, message: str) -> Dict[str, Any]:
        """Use LLM to analyze user intent in prospect feedback."""
        
        analysis_prompt = f"""
        Analyze this user message about prospect review and determine their intent.
        
        User message: "{message}"
        
        Context: The user has been shown a list of prospects and asked if they want to:
        1. Provide more feedback to further refine
        2. Approve to move forward  
        3. Specify exact criteria to adjust
        
        Determine if the user is:
        - APPROVING the prospects (wants to move forward, satisfied, likes them)
        - REQUESTING REFINEMENT (wants changes, adjustments, improvements)
        - ASKING QUESTIONS (unclear, needs clarification)
        
        Return JSON:
        {{
            "is_approval": true/false,
            "is_refinement_request": true/false,
            "is_question": true/false,
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation of the classification"
        }}
        
        Examples:
        - "Yes, these look good" → approval
        - "Looks great, let's proceed" → approval  
        - "Perfect, move forward" → approval
        - "2" (referring to option 2) → approval
        - "I don't like #3, too small company" → refinement
        - "Can you focus more on tech companies?" → refinement
        - "What does the score mean?" → question
        - "These are not what I'm looking for" → refinement
        """
        
        try:
            # Use research agent's LLM to analyze intent
            response = await self.research_agent.process_json_request(analysis_prompt)
            
            # Parse JSON response
            import json
            intent_data = json.loads(response)
            
            # Validate required fields
            required_fields = ["is_approval", "is_refinement_request", "is_question", "confidence"]
            for field in required_fields:
                if field not in intent_data:
                    intent_data[field] = False if field != "confidence" else 0.5
            
            self.logger.info("Analyzed prospect feedback intent", 
                           intent=intent_data, 
                           message_preview=message[:50])
            
            return intent_data
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze intent via LLM, falling back to keywords: {e}")
            
            # Fallback to simple keyword analysis
            lower_msg = message.lower()
            
            # Simple approval detection as fallback
            approval_keywords = ["yes", "good", "great", "perfect", "approve", "proceed", "move forward", "looks good"]
            refinement_keywords = ["no", "change", "refine", "adjust", "don't like", "wrong", "bad", "improve"]
            
            is_approval = any(keyword in lower_msg for keyword in approval_keywords)
            is_refinement = any(keyword in lower_msg for keyword in refinement_keywords)
            
            return {
                "is_approval": is_approval and not is_refinement,
                "is_refinement_request": is_refinement or (not is_approval and len(message) > 10),
                "is_question": "?" in message or "what" in lower_msg or "how" in lower_msg,
                "confidence": 0.6,
                "reasoning": "Fallback keyword analysis"
            }
    
    def _format_prospects_as_table(self, prospects: List[Dict[str, Any]]) -> List[List[str]]:
        """Format prospects as table data for better UI display."""
        
        table_data = []
        headers = ["#", "Name", "Title", "Company", "Industry", "Score", "Email", "LinkedIn"]
        
        for i, prospect in enumerate(prospects[:10], 1):
            company = prospect.get('company', {})
            person = prospect.get('person', {})
            score = prospect.get('score', {})
            
            # Format score with color indicator
            score_val = score.get('total_score', 0)
            if score_val >= 0.8:
                score_display = f"🟢 {score_val:.2f}"
            elif score_val >= 0.6:
                score_display = f"🟡 {score_val:.2f}"
            else:
                score_display = f"🔴 {score_val:.2f}"
            
            row = [
                str(i),
                f"{person.get('first_name', '')} {person.get('last_name', '')}".strip() or "Unknown",
                person.get('title', 'Unknown'),
                company.get('name', 'Unknown'),
                company.get('industry', 'Unknown'),
                score_display,
                person.get('email', 'N/A'),
                person.get('linkedin_url', 'N/A')[:30] + "..." if person.get('linkedin_url') else 'N/A'
            ]
            table_data.append(row)
        
        return [headers] + table_data
    
    def get_conversation_history(self, conversation_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get conversation message history."""
        
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return None
        
        return [msg.model_dump() for msg in conversation.messages]
    
    def get_conversation_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation status and progress."""
        
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return None
        
        return {
            "conversation_id": conversation_id,
            "current_step": conversation.current_step.value,
            "completed_steps": [step.value for step in conversation.completed_steps],
            "message_count": len(conversation.messages),
            "created_at": conversation.created_at.isoformat(),
            "icp_id": conversation.current_icp_id,
            "prospect_count": len(conversation.current_prospects),
            "automation_enabled": conversation.automation_enabled,
            "powered_by": "Google ADK"
        }


class ADKCLIInterface:
    """
    Command-line interface for the Google ADK multi-agent system.
    """
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.config.ensure_directories()
        
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.current_conversation_id: Optional[str] = None
        
        # Configure logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    async def start(self):
        """Start the ADK CLI interface."""
        
        print("🎯 Google ADK Multi-Agent Sales Lead Generation System")
        print("=" * 55)
        print("Powered by Google Agent Development Kit (ADK)")
        print()
        
        # Start a new conversation
        user_id = "cli_user"  # In a real app, this would be the actual user ID
        self.current_conversation_id = await self.orchestrator.start_conversation(user_id)
        
        print("Type 'exit' to quit, 'status' to see progress, or 'help' for commands.")
        print()
        
        # Main conversation loop
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() == 'exit':
                    print("Goodbye! 👋")
                    break
                elif user_input.lower() == 'status':
                    await self._show_status()
                    continue
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                elif user_input.lower().startswith('attach '):
                    # Handle file attachments (URLs, etc.)
                    url = user_input[7:].strip()
                    if url:
                        attachments = [{"type": "url", "url": url, "description": "User provided URL"}]
                        response = await self.orchestrator.process_user_message(
                            self.current_conversation_id, 
                            f"Please analyze this URL: {url}",
                            attachments
                        )
                        print(f"\nAssistant: {response}\n")
                    continue
                
                # Process user message
                print("\nProcessing with Google ADK agents...")
                
                response = await self.orchestrator.process_user_message(
                    self.current_conversation_id,
                    user_input
                )
                
                print(f"\nAssistant: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")
                print("Please try again or type 'help' for assistance.\n")
    
    async def _show_status(self):
        """Show current conversation status."""
        
        if not self.current_conversation_id:
            print("No active conversation.")
            return
        
        status = self.orchestrator.get_conversation_status(self.current_conversation_id)
        if status:
            print("\n📊 Google ADK Conversation Status:")
            print(f"- Current Step: {status['current_step'].replace('_', ' ').title()}")
            print(f"- Messages Exchanged: {status['message_count']}")
            print(f"- ICP Created: {'Yes' if status['icp_id'] else 'No'}")
            print(f"- Prospects Found: {status['prospect_count']}")
            print(f"- Automation Enabled: {'Yes' if status['automation_enabled'] else 'No'}")
            print(f"- Powered By: {status['powered_by']}")
            print()
    
    def _show_help(self):
        """Show help information."""
        
        print("\n📋 Google ADK System Commands:")
        print("- Just type your message to continue the conversation")
        print("- 'attach <URL>' - Attach a website URL for analysis")
        print("- 'status' - Show current progress")
        print("- 'help' - Show this help message")
        print("- 'exit' - End the session")
        print("\n💡 ADK Agent Features:")
        print("- ICP Agent: AI-powered customer profile creation")
        print("- Research Agent: Multi-source business intelligence")
        print("- Prospect Agent: Intelligent lead discovery and scoring")
        print("- External Tools: HorizonDataWave, Exa, Firecrawl integration")
        print()


async def main():
    """Main entry point for Google ADK system."""
    
    print("Initializing Google ADK Multi-Agent Sales Lead Generation System...")
    
    try:
        cli = ADKCLIInterface()
        await cli.start()
    except Exception as e:
        print(f"Failed to start ADK system: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Set up asyncio event loop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())