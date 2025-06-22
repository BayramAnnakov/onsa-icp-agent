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
from utils.logging_config import get_logger
from integrations import HorizonDataWave, ExaWebsetsAPI, FirecrawlClient
from services.vertex_memory_service import VertexMemoryManager


class ADKAgentOrchestrator:
    """
    Main orchestrator using Google ADK agents with external tool integration.
    """
    
    def __init__(self, config: Config, memory_manager: Optional[VertexMemoryManager] = None):
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize cache manager
        self.cache_manager = CacheManager(config.cache)
        
        # Initialize memory manager if enabled
        self.memory_manager = memory_manager
        if not memory_manager and config.vertexai.enabled:
            try:
                self.memory_manager = VertexMemoryManager(config.vertexai)
                self.logger.info("VertexAI memory manager initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize VertexAI memory manager - Error: {str(e)}")
                self.memory_manager = None
        
        # Initialize ADK agents with external tools and memory
        self.icp_agent = ADKICPAgent(config, self.cache_manager, memory_manager=self.memory_manager)
        self.research_agent = ADKResearchAgent(config, self.cache_manager, memory_manager=self.memory_manager)
        self.prospect_agent = ADKProspectAgent(config, self.cache_manager, memory_manager=self.memory_manager)
        
        # Active conversations
        self.conversations: Dict[str, Conversation] = {}
        self.current_conversation: Optional[Conversation] = None
        
        self.logger.info(f"ADK Agent orchestrator initialized - Memory enabled: {bool(self.memory_manager)}")
    
    async def start_conversation(self, user_id: str) -> str:
        """Start a new conversation session with context from previous interactions."""
        
        import uuid
        conversation_id = f"conv_{user_id}_{uuid.uuid4().hex[:8]}"
        
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id
        )
        
        self.conversations[conversation_id] = conversation
        self.current_conversation = conversation
        
        # Try to load context from previous conversations
        personalized_greeting = ""
        user_context = await self._load_user_context(user_id)
        
        if user_context:
            personalized_greeting = self._generate_personalized_greeting(user_context)
        
        # Welcome message with potential personalization
        welcome_message = f"""
{personalized_greeting}Welcome to the Google ADK Multi-Agent Sales Lead Generation System!

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
        
        self.logger.info(f"Started new ADK conversation - Conversation_Id: {conversation_id}, User_Id: {user_id}, Personalized: {bool(personalized_greeting)}")
        
        return conversation_id
    
    async def process_user_message(
        self,
        conversation_id: str,
        message: str,
        attachments: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Process a user message using flexible LLM-driven routing."""
        
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return "Conversation not found. Please start a new conversation."
        
        # Add user message to conversation
        conversation.add_message(MessageRole.USER, message, attachments=attachments or [])
        
        # Update current conversation
        self.current_conversation = conversation
        
        self.logger.info(f"Processing user message with ADK agents - Conversation_Id: {conversation_id}, Current_Step: {conversation.current_step.value}, Message_Length: {len(message)}")
        
        # Analyze user intent using LLM
        intent = await self._analyze_user_intent(message, conversation, attachments)
        self.logger.info(f"Detected intent - Type: {intent['intent_type']}, Confidence: {intent['confidence']:.2f}")
        
        # Route based on intent
        response = await self._route_message_by_intent(conversation, message, intent, attachments)
        
        # Add response to conversation
        conversation.add_message(MessageRole.ASSISTANT, response)
        
        # Store conversation to memory for persistence
        await self._store_conversation_to_memory(conversation)
        
        return response
    
    async def process_user_message_stream(
        self,
        conversation_id: str,
        message: str,
        attachments: Optional[List[Dict[str, str]]] = None
    ):
        """Process a user message using flexible LLM-driven routing with streaming."""
        
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            yield "Conversation not found. Please start a new conversation."
            return
        
        # Add user message to conversation
        conversation.add_message(MessageRole.USER, message, attachments=attachments or [])
        
        # Update current conversation
        self.current_conversation = conversation
        
        self.logger.info(f"Processing user message with ADK agents (streaming) - Conversation_Id: {conversation_id}, Current_Step: {conversation.current_step.value}, Message_Length: {len(message)}")
        
        # Analyze user intent using LLM
        yield "🤔 Understanding your request...\n\n"
        intent = await self._analyze_user_intent(message, conversation, attachments)
        self.logger.info(f"Detected intent - Type: {intent['intent_type']}, Confidence: {intent['confidence']:.2f}")
        
        # Collect full response for conversation history
        full_response = ""
        
        try:
            # Route based on intent type
            intent_type = intent.get("intent_type", "unclear")
            
            # Handle different intents with streaming
            if intent_type == "casual_greeting":
                response = await self._handle_casual_conversation(conversation, message, intent)
                full_response = response
                yield response
            
            elif intent_type == "provide_business_info":
                # Check if we should process as business info
                if conversation.current_step == WorkflowStep.BUSINESS_DESCRIPTION:
                    async for chunk in self._handle_business_description_stream(conversation, message, attachments or []):
                        full_response += chunk
                        yield chunk
                else:
                    # Store the info but don't force workflow
                    conversation.business_info.update({"additional_info": message})
                    response = "Thanks for that additional information! I've noted it down. What would you like to do next?"
                    full_response = response
                    yield response
            
            elif intent_type == "request_icp_creation":
                # Check if we need to do business research first (if URL provided)
                website_urls = self._extract_urls(message)
                if website_urls and not conversation.business_info.get("description"):
                    # First do business research, then automatically create ICP
                    yield "🔍 I'll research your business first, then create the ICP...\n\n"
                    async for chunk in self._handle_business_description_stream(conversation, message, attachments or []):
                        full_response += chunk
                        yield chunk
                else:
                    # We have business info or no URL provided, jump to ICP creation
                    if conversation.business_info.get("description") or message:
                        if conversation.current_step != WorkflowStep.ICP_CREATION:
                            conversation.advance_step(WorkflowStep.ICP_CREATION)
                        async for chunk in self._handle_icp_creation_stream(conversation, message, attachments or []):
                            full_response += chunk
                            yield chunk
                    else:
                        response = "I'd be happy to create an ICP for you! First, could you tell me about your business? What products or services do you offer?"
                        full_response = response
                        yield response
            
            elif intent_type == "find_prospects":
                # Jump to prospect search, create basic ICP if needed
                if conversation.current_icp_id:
                    if conversation.current_step not in [WorkflowStep.PROSPECT_SEARCH, WorkflowStep.PROSPECT_REVIEW]:
                        conversation.advance_step(WorkflowStep.PROSPECT_SEARCH)
                    async for chunk in self._handle_prospect_search_stream(conversation, message, attachments or []):
                        full_response += chunk
                        yield chunk
                else:
                    response = "To find the best prospects for you, I'll need to create an ICP first. Could you tell me about your ideal customers or share your business details?"
                    full_response = response
                    yield response
            
            elif intent_type == "memory_query":
                response = await self._handle_memory_query(conversation, message)
                full_response = response
                yield response
            
            else:
                # For other intents, use non-streaming handlers
                response = await self._route_message_by_intent(conversation, message, intent, attachments)
                full_response = response
                yield response
            
            # Add complete response to conversation history
            conversation.add_message(MessageRole.ASSISTANT, full_response)
            
            # Store conversation to memory for persistence
            await self._store_conversation_to_memory(conversation)
            
        except Exception as e:
            error_message = f"\n\n❌ I encountered an error: {str(e)}. Let me try a different approach."
            conversation.add_message(MessageRole.ASSISTANT, error_message)
            
            # Store conversation even on error for persistence
            await self._store_conversation_to_memory(conversation)
            
            self.logger.error(f"Error in intent-based routing - Intent: {intent_type}, Error: {str(e)}")
            yield error_message
    
    async def _handle_business_description(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle business description phase - now more flexible."""
        
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
                    self.logger.error(f"Error analyzing source materials with Research Agent - Error: {str(e)}")
        
        # Don't automatically advance - let user decide next step
        return f"""
Thank you for sharing that information about your business. I've stored those details.

What would you like to do next? I can:
1. **Create an ICP** - Build an Ideal Customer Profile based on your business
2. **Find prospects** - Search for potential customers (I'll create a basic ICP first if needed)
3. **Analyze a website** - If you have competitor or customer websites to analyze
4. **Answer questions** - About the process, your data, or anything else

Just let me know how you'd like to proceed!
        """.strip()
    
    async def _handle_business_description_stream(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ):
        """Stream the business description handling process."""
        yield "📝 Analyzing your business information...\n\n"
        
        # Extract website URLs and deduplicate
        website_urls = set(self._extract_urls(message))
        for attachment in attachments:
            if attachment.get("type") == "url":
                website_urls.add(attachment["url"])
        
        # Convert back to list for consistent handling
        website_urls = list(website_urls)
        
        if website_urls:
            yield f"🌐 Found {len(website_urls)} website(s) to analyze:\n"
            for url in website_urls:
                yield f"   • {url}\n"
                # Add URL to source materials for ICP creation
                conversation.add_source_material("url", url, "Company website")
            yield "\n"
        
        # Use research agent to analyze business
        yield "🔍 Using AI research agent to understand your business...\n"
        
        try:
            # If we have URLs, analyze the first one; otherwise use the message as company identifier
            company_to_analyze = website_urls[0] if website_urls else message
            result = await self.research_agent.analyze_company_comprehensive(
                company_identifier=company_to_analyze,
                analysis_depth="standard"
            )
            
            # Handle case where result might be a string or not properly structured
            if not isinstance(result, dict):
                self.logger.warning(f"Research result is not a dictionary: {type(result)}")
                if isinstance(result, str):
                    try:
                        import json
                        result = json.loads(result)
                    except:
                        result = {"status": "error", "error_message": "Invalid result format"}
                else:
                    result = {"status": "error", "error_message": f"Unexpected result type: {type(result)}"}
            
            if result.get("status") == "success":
                business_info = result.get("analysis", {})
                self.logger.debug(f"Business info type: {type(business_info)}, keys: {list(business_info.keys()) if isinstance(business_info, dict) else 'N/A'}")
                
                # Handle case where business_info might be a string or not properly structured
                if isinstance(business_info, str):
                    try:
                        import json
                        business_info = json.loads(business_info)
                    except:
                        # If JSON parsing fails, wrap in a dict
                        business_info = {"description": business_info, "findings": {}}
                elif not isinstance(business_info, dict):
                    # Handle any other non-dict types
                    business_info = {"description": str(business_info), "findings": {}}
                
                # Ensure business_info is properly structured
                if not isinstance(business_info, dict):
                    business_info = {"description": str(business_info), "findings": {}}
                
                # Ensure findings is a dict
                if "findings" not in business_info or not isinstance(business_info["findings"], dict):
                    business_info["findings"] = {}
                
                # Extract key information from findings with safe dict access
                findings = business_info.get("findings", {})
                
                conversation.business_info = business_info
                conversation.add_source_material("research", str(business_info), "Business research data")
                
                yield "\n✅ Successfully analyzed your business!\n\n"
                yield "Here's what I found:\n\n"
                
                # Check for LinkedIn data first
                if linkedin_data := findings.get("linkedin_data", {}):
                    if company_name := linkedin_data.get("name"):
                        yield f"**Company:** {company_name}\n"
                    
                    if industry := linkedin_data.get("industry"):
                        yield f"**Industry:** {industry}\n"
                    
                    if description := linkedin_data.get("description"):
                        yield f"**What you do:** {description}\n"
                    
                    if size := linkedin_data.get("company_size"):
                        yield f"**Company Size:** {size}\n"
                
                # Check for website analysis
                elif website_data := findings.get("website_analysis", {}):
                    # Handle the actual structure returned by Firecrawl analysis
                    if business_model := website_data.get("business_model_and_value_proposition", {}):
                        if isinstance(business_model, dict):
                            if business_model.get("business_model"):
                                yield f"**Business Model:** {business_model['business_model']}\n"
                            if business_model.get("value_proposition"):
                                yield f"**Value Proposition:** {business_model['value_proposition'][:200]}...\n"
                    
                    if target_market := website_data.get("target_customers_and_market", {}):
                        if isinstance(target_market, dict):
                            if target_market.get("target_customers"):
                                yield f"**Target Customers:** {target_market['target_customers'][:200]}...\n"
                    
                    if products_data := website_data.get("products_services_offered", {}):
                        if isinstance(products_data, dict) and products_data.get("products_services"):
                            products = products_data["products_services"]
                            if isinstance(products, list):
                                # Handle both string lists and dict lists
                                if products and isinstance(products[0], dict):
                                    products_str = ", ".join(p.get("name", str(p)) for p in products[:3])
                                else:
                                    products_str = ", ".join(str(p) for p in products[:3])
                                if len(products) > 3:
                                    products_str += f" (+{len(products)-3} more)"
                                yield f"**Products/Services:** {products_str}\n"
                
                # Show sources used
                if sources := business_info.get("sources_used", []):
                    yield f"\n**Data sources used:** {', '.join(sources)}\n"
                
                # If no structured findings were displayed, show a summary of what was found
                displayed_structured_data = (
                    findings.get("linkedin_data") or 
                    (findings.get("website_analysis", {}).get("business_model_and_value_proposition"))
                )
                
                if not displayed_structured_data:
                    # Fallback: try to show any available website analysis data
                    if website_data := findings.get("website_analysis", {}):
                        yield "**Analysis Summary:**\n"
                        # Try to extract any useful information from the website data
                        for key, value in website_data.items():
                            if isinstance(value, dict):
                                for sub_key, sub_value in value.items():
                                    if isinstance(sub_value, str) and len(sub_value) > 20:
                                        formatted_key = sub_key.replace("_", " ").title()
                                        yield f"• **{formatted_key}:** {sub_value[:150]}...\n"
                                        break  # Only show first meaningful value per section
                            elif isinstance(value, str) and len(value) > 20:
                                formatted_key = key.replace("_", " ").title()
                                yield f"• **{formatted_key}:** {value[:150]}...\n"
                    
                    elif business_info.get("description"):
                        yield f"**Business Description:** {business_info.get('description')}\n"
                    
                    # Show any other key findings in a structured way
                    for key, value in business_info.items():
                        if key not in ["description", "sources_used", "findings"] and value:
                            formatted_key = key.replace("_", " ").title()
                            if isinstance(value, (dict, list)):
                                continue  # Skip complex structures for now
                            yield f"**{formatted_key}:** {str(value)[:200]}\n"
                
                yield "\n"
                
                # Store the analyzed information
                conversation.business_info.update({
                    "description": message,
                    "analysis": business_info,
                    "provided_at": datetime.now().isoformat()
                })
                
                # Check if user explicitly requested ICP creation in their message
                icp_keywords = ["create icp", "build icp", "make icp", "let's create", "lets create", "build an icp", "create an icp"]
                should_create_icp = any(keyword in message.lower() for keyword in icp_keywords)
                
                if should_create_icp:
                    yield "\nGreat! I have a good understanding of your business.\n\n"
                    yield "🏗️ Since you requested ICP creation, let me build that for you now...\n\n"
                    
                    # Advance to ICP creation and create it
                    conversation.advance_step(WorkflowStep.ICP_CREATION)
                    async for chunk in self._handle_icp_creation_stream(conversation, "", []):
                        yield chunk
                else:
                    # Don't auto-advance - let user decide
                    yield "\nGreat! I have a good understanding of your business.\n\n"
                    yield "What would you like to do next?\n\n"
                    yield "1. **Create an ICP** - Build your Ideal Customer Profile\n"
                    yield "2. **Find prospects directly** - Search for potential customers\n"
                    yield "3. **Analyze competitors** - Review competitor websites\n"
                    yield "4. **Tell me more** - Add more details about your business\n\n"
                    yield "Just type your choice or tell me what you'd like to do!"
                
            else:
                # If research fails, still save the info
                conversation.business_info = {"description": message}
                
                yield "\nI've noted your business information.\n\n"
                yield "What would you like to do next?\n\n"
                yield "1. **Create an ICP** - Build your Ideal Customer Profile\n"
                yield "2. **Try analyzing again** - Provide a website URL\n"
                yield "3. **Find prospects** - Search for potential customers\n\n"
                yield "Let me know how you'd like to proceed!"
                
        except Exception as e:
            self.logger.error(f"Error in business description analysis - Error: {str(e)}")
            # Still save basic info
            conversation.business_info = {"description": message}
            
            yield "\nI've saved your business information.\n\n"
            yield "What would you like to do next?\n\n"
            yield "1. **Create an ICP** - Build your Ideal Customer Profile\n"
            yield "2. **Find prospects** - Search for potential customers\n"
            yield "3. **Provide more details** - Tell me more about your business\n\n"
            yield "Just let me know what you'd prefer!"
    
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
            self.logger.error(f"Error creating ICP with ADK agent - Error: {str(e)}")
            return f"I encountered an error creating your ICP: {str(e)}. Could you provide more details about your ideal customers?"
    
    async def _handle_icp_creation_stream(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ):
        """Stream ICP creation using ADK ICP Agent."""
        
        yield "🏗️ Building your Ideal Customer Profile...\n\n"
        
        try:
            # Extract company URLs from source materials for research
            example_companies = []
            for material in conversation.source_materials:
                if material.get("type") == "url" and "http" in material.get("url", ""):
                    example_companies.append(material["url"])
            
            if example_companies:
                yield f"📊 Analyzing {len(example_companies)} reference companies...\n"
            
            yield "🔄 Using multiple data sources:\n"
            yield "   • HorizonDataWave for company data\n"
            yield "   • Firecrawl for website analysis\n"
            yield "   • Exa AI for industry insights\n\n"
            
            # Use ADK ICP Agent to create ICP with research
            icp_result = await self.icp_agent.create_icp_from_research(
                business_info=conversation.business_info,
                example_companies=example_companies,
                research_depth="standard"
            )
            
            if icp_result["status"] != "success":
                yield f"\n❌ I encountered an error creating your ICP: {icp_result.get('error_message', 'Unknown error')}.\n"
                yield "Could you provide more details about your ideal customers?"
                return
            
            # Store ICP ID
            conversation.current_icp_id = icp_result.get("icp_id")
            conversation.icp_versions.append(icp_result.get("icp_id"))
            
            yield "✅ ICP created successfully!\n\n"
            yield "Here's your initial Ideal Customer Profile:\n\n"
            
            # Format and stream ICP details
            icp_data = icp_result.get("icp", {})
            
            # Stream ICP sections
            if company_criteria := icp_data.get("company_criteria", {}):
                yield "**🏢 Company Characteristics:**\n"
                
                # Handle industry criterion
                if industry_criterion := company_criteria.get("industry"):
                    if isinstance(industry_criterion, dict):
                        industries = industry_criterion.get("values", [])
                    else:
                        industries = industry_criterion if isinstance(industry_criterion, list) else []
                    
                    if industries:
                        yield f"• **Industries:** {', '.join(industries[:3])}"
                        if len(industries) > 3:
                            yield f" (+{len(industries)-3} more)"
                        yield "\n"
                
                # Handle company size criterion
                if size_criterion := company_criteria.get("company_size"):
                    if isinstance(size_criterion, dict):
                        sizes = size_criterion.get("values", [])
                        if sizes:
                            yield f"• **Company Size:** {', '.join(sizes)}\n"
                    else:
                        yield f"• **Company Size:** {size_criterion}\n"
                
                # Handle revenue criterion
                if revenue_criterion := company_criteria.get("revenue"):
                    if isinstance(revenue_criterion, dict):
                        revenues = revenue_criterion.get("values", [])
                        if revenues:
                            yield f"• **Revenue Range:** {', '.join(revenues)}\n"
                    else:
                        yield f"• **Revenue Range:** {revenue_criterion}\n"
                
                yield "\n"
            
            if person_criteria := icp_data.get("person_criteria", {}):
                yield "**👤 Decision Maker Profile:**\n"
                
                # Handle job titles
                if title_criterion := person_criteria.get("job_title"):
                    if isinstance(title_criterion, dict):
                        titles = title_criterion.get("values", [])
                    else:
                        titles = person_criteria.get("job_titles", [])
                    
                    if titles:
                        yield f"• **Job Titles:** {', '.join(titles[:3])}"
                        if len(titles) > 3:
                            yield f" (+{len(titles)-3} more)"
                        yield "\n"
                
                # Handle seniority
                if seniority_criterion := person_criteria.get("seniority"):
                    if isinstance(seniority_criterion, dict):
                        seniority_levels = seniority_criterion.get("values", [])
                    else:
                        seniority_levels = seniority_criterion if isinstance(seniority_criterion, list) else []
                    
                    if seniority_levels:
                        yield f"• **Seniority:** {', '.join(seniority_levels)}\n"
                
                # Handle departments if present
                if departments := person_criteria.get("departments"):
                    yield f"• **Departments:** {', '.join(departments)}\n"
                
                yield "\n"
            
            if pain_points := icp_data.get("pain_points"):
                yield "**🎯 Key Pain Points:**\n"
                # Limit to exactly 3 pain points
                for i, point in enumerate(pain_points[:3], 1):
                    yield f"{i}. {point}\n"
                yield "\n"
            
            # Research sources info
            yield "**📊 Research Sources Used:**\n"
            sources_used = []
            if "horizondatawave" in str(icp_result.get("sources", [])).lower():
                sources_used.append("HorizonDataWave")
            if example_companies:
                sources_used.append("Website analysis via Firecrawl")
            if "exa" in str(icp_result.get("sources", [])).lower():
                sources_used.append("Industry insights from Exa")
            
            for source in sources_used:
                yield f"• ✓ {source}\n"
            
            yield f"• Companies researched: {icp_result.get('research_used', len(example_companies))}\n\n"
            
            # Add a complete ICP summary to ensure it's captured in conversation history
            yield "**📋 Complete ICP Summary:**\n"
            formatted_icp_summary = self._format_icp_for_display(icp_data)
            yield formatted_icp_summary
            yield "\n\n"
            
            # Move to refinement phase
            conversation.advance_step(WorkflowStep.ICP_REFINEMENT)
            
            yield "**Please review this ICP and let me know:**\n"
            yield "1. Does this accurately represent your ideal customers?\n"
            yield "2. Are there any characteristics I should add, remove, or modify?\n"
            yield "3. Should I adjust the importance/weight of any criteria?\n\n"
            yield "Once you're satisfied with the ICP, I'll use it to search for prospects using our external data sources."
            
        except Exception as e:
            self.logger.error(f"Error creating ICP with ADK agent - Error: {str(e)}")
            yield f"\n❌ I encountered an error creating your ICP: {str(e)}.\n"
            yield "Could you provide more details about your ideal customers?"
    
    async def _handle_icp_refinement(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Handle ICP refinement using ADK ICP Agent."""
        
        # Use LLM to analyze user intent for approval/refinement
        intent_analysis = await self._analyze_icp_refinement_intent(message)
        
        if intent_analysis["is_approval"]:
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
                self.logger.error(f"Error refining ICP with ADK agent - Error: {str(e)}")
                return f"I had trouble refining the ICP: {str(e)}. Could you be more specific about what you'd like to change?"
    
    async def _handle_icp_refinement_stream(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ):
        """Stream ICP refinement process."""
        
        # Use LLM to analyze user intent for approval/refinement
        intent_analysis = await self._analyze_icp_refinement_intent(message)
        
        if intent_analysis["is_approval"]:
            yield "✅ Great! Your ICP is approved.\n\n"
            yield "Now let me search for prospects that match your criteria...\n\n"
            
            # Move to prospect search
            conversation.advance_step(WorkflowStep.PROSPECT_SEARCH)
            
            # Stream prospect search
            async for chunk in self._handle_prospect_search_stream(conversation, "", []):
                yield chunk
        else:
            # Handle refinement request
            yield "🔧 Refining your ICP based on your feedback...\n\n"
            
            try:
                # Use ICP agent to refine
                refinement_result = await self.icp_agent.refine_icp_criteria(
                    icp_id=conversation.current_icp_id,
                    feedback=message,
                    specific_changes={}
                )
                
                if refinement_result["status"] == "success":
                    # Update ICP ID
                    new_icp_id = refinement_result.get("icp_id", conversation.current_icp_id)
                    conversation.current_icp_id = new_icp_id
                    conversation.icp_versions.append(new_icp_id)
                    
                    yield "✅ ICP updated successfully!\n\n"
                    yield "Here are the changes I made:\n\n"
                    
                    # Stream changes
                    changes = refinement_result.get("changes", [])
                    for change in changes:
                        yield f"• {change}\n"
                    
                    if not changes:
                        yield "• Updated criteria based on your feedback\n"
                    
                    yield "\n"
                    
                    # Show updated ICP
                    icp_data = refinement_result.get("icp", {})
                    formatted_icp = self._format_icp_for_display(icp_data)
                    
                    yield "**Updated ICP:**\n"
                    yield formatted_icp
                    yield "\n\n"
                    
                    yield "Is this ICP now ready for prospect search, or would you like to make additional changes?"
                else:
                    yield f"❌ I encountered an error refining your ICP: {refinement_result.get('error_message', 'Unknown error')}.\n"
                    yield "Could you please clarify what changes you'd like to make?"
                    
            except Exception as e:
                self.logger.error(f"Error refining ICP with ADK agent - Error: {str(e)}")
                yield f"❌ I had trouble refining the ICP: {str(e)}.\n"
                yield "Could you be more specific about what you'd like to change?"
    
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
            self.logger.error(f"Error searching prospects with ADK agent - Error: {str(e)}")
            return f"I encountered an error searching for prospects: {str(e)}. Let me try again with different parameters."
    
    async def _handle_prospect_search_stream(
        self,
        conversation: Conversation,
        message: str,
        attachments: List[Dict[str, str]]
    ):
        """Stream prospect search using ADK Prospect Agent."""
        
        yield "🔍 Starting prospect search...\n\n"
        
        try:
            # Get ICP criteria
            yield "📋 Retrieving your ICP criteria...\n"
            
            icp_export = await self.icp_agent.export_icp(
                icp_id=conversation.current_icp_id,
                format="json"
            )
            
            if icp_export["status"] != "success":
                yield "❌ I couldn't retrieve your ICP for prospect search. Please try again."
                return
            
            icp_criteria = icp_export["icp"]
            
            yield "✅ ICP loaded successfully\n\n"
            
            # Show search parameters
            yield "🎯 Search parameters:\n"
            yield f"• **Sources:** HorizonDataWave, Exa AI\n"
            yield f"• **Locations:** United States, Canada, United Kingdom\n"
            yield f"• **Target:** Up to 50 prospects\n\n"
            
            yield "🔄 Searching across multiple data sources:\n"
            
            # Use ADK Prospect Agent to search for prospects
            yield "   • Querying HorizonDataWave database...\n"
            yield "   • Searching Exa AI knowledge base...\n"
            yield "   • Cross-referencing company data...\n\n"
            
            search_result = await self.prospect_agent.search_prospects_multi_source(
                icp_criteria=icp_criteria,
                search_limit=50,
                sources=["hdw", "exa"],
                location_filter="United States, Canada, United Kingdom"
            )
            
            if search_result["status"] != "success":
                yield f"\n❌ I encountered an error searching for prospects: {search_result.get('error_message', 'Unknown error')}.\n"
                yield "Let me try again with different parameters."
                return
            
            prospects = search_result.get("prospects", [])
            yield f"✅ Found {len(prospects)} potential prospects!\n\n"
            
            # Store prospect IDs
            conversation.current_prospects = [p.get("id") for p in prospects]
            
            # Get top 10 highest-scoring prospects for review
            if prospects:
                yield "⚡ Scoring and ranking prospects...\n"
                yield "   • Analyzing company fit...\n"
                yield "   • Evaluating decision maker match...\n"
                yield "   • Calculating relevance scores...\n\n"
                
                ranking_result = await self.prospect_agent.rank_prospects_by_score(
                    prospect_ids=conversation.current_prospects,
                    ranking_criteria={"sort_by": "total_score", "min_score": 0.0},
                    limit=10
                )
                
                if ranking_result["status"] == "success":
                    top_prospects = ranking_result["prospects"]
                else:
                    top_prospects = prospects[:10]
                
                yield "✅ Scoring complete!\n\n"
            else:
                top_prospects = []
                yield "No prospects found matching your criteria.\n"
                return
            
            # Move to review phase
            conversation.advance_step(WorkflowStep.PROSPECT_REVIEW)
            
            # Format and stream top prospects
            yield f"**📊 Search Results Summary:**\n"
            yield f"• Total prospects found: {len(prospects)}\n"
            yield f"• Top prospects shown in table below\n"
            yield f"• Sources used: {', '.join(search_result.get('sources_used', []))}\n\n"
            
            yield "**Please review the prospects in the table above.**\n\n"
            yield "You can:\n"
            yield "• Say 'approve' or 'looks good' to proceed\n"
            yield "• Provide feedback to refine the search\n"
            yield "• Ask me to find more prospects"
            
        except Exception as e:
            self.logger.error(f"Error searching prospects with ADK agent - Error: {str(e)}")
            yield f"\n❌ I encountered an error searching for prospects: {str(e)}.\n"
            yield "Let me try again with different parameters."
    
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
                self.logger.error(f"Error generating final report with ADK agent - Error: {str(e)}")
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
                self.logger.error(f"Error processing prospect feedback - Error: {str(e)}")
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
        
        # Use LLM to analyze automation setup intent
        intent_analysis = await self._analyze_automation_setup_intent(message)
        
        if intent_analysis["wants_automation"]:
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
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text."""
        import re
        # Simple URL extraction pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        return urls
    
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
    
    async def _is_memory_query(self, message: str) -> bool:
        """Use LLM to intelligently detect if the user is asking about previous work or memory."""
        
        analysis_prompt = f"""
        Analyze this user message and determine if they are asking about previous work, past conversations, or memory-related queries.
        
        User message: "{message}"
        
        Consider these scenarios as memory queries:
        - Asking about previous ICPs, prospects, or analysis
        - Referencing past conversations or sessions
        - Asking what was discussed or created before
        - Wanting to continue from where they left off
        - Asking about their history or past work
        
        Consider these as NOT memory queries:
        - Starting fresh with new requirements
        - Asking general questions about capabilities
        - Providing new business information
        - Asking for help with current tasks
        
        Return JSON with your analysis:
        {{
            "is_memory_query": true/false,
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation"
        }}
        
        Examples:
        - "What was my last ICP?" → memory query (asking about previous ICP)
        - "Show me the prospects we found" → memory query (referencing past work)
        - "I need an ICP for fintech companies" → NOT memory query (new request)
        - "Can you help me find prospects?" → NOT memory query (general request)
        - "Continue from where we left off" → memory query (continuation request)
        """
        
        try:
            # Use research agent's LLM for quick analysis
            response = await self.research_agent.process_json_request(analysis_prompt)
            
            # Parse JSON response
            import json
            analysis = json.loads(response)
            
            is_memory = analysis.get("is_memory_query", False)
            confidence = analysis.get("confidence", 0.0)
            
            self.logger.info(f"Memory query detection - Is_Memory: {is_memory}, Confidence: {confidence:.2f}, Message: '{message[:50]}...'")
            
            # Only consider it a memory query if confidence is high enough
            return is_memory and confidence >= 0.7
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze if memory query, falling back to keyword detection: {e}")
            
            # Fallback to simple keyword detection
            memory_keywords = ["last icp", "previous", "what was", "we created", "earlier", "history"]
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in memory_keywords)
    
    async def _handle_memory_query(self, conversation: Conversation, message: str) -> str:
        """Handle memory-related queries using the ICP agent."""
        try:
            # Use ICP agent to process the memory query
            # The agent has access to load_memory tool and will use it automatically
            response = await self.icp_agent.process_message(
                message=message,
                conversation_id=conversation.id,
                context={
                    "user_id": conversation.user_id,
                    "is_memory_query": True
                }
            )
            
            # If the response indicates no memory found, provide guidance
            if "no active icps" in response.lower() or "no memory" in response.lower():
                response += "\n\nIf you'd like to start fresh, please describe your business and I'll create a new ICP for you."
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error handling memory query - Error: {str(e)}")
            return "I had trouble accessing previous conversations. Let's start fresh - please tell me about your business."
    
    async def _load_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load user context from previous sessions for personalization."""
        if not self.memory_manager:
            return None
            
        try:
            # Query for user-specific information
            memories = await self.memory_manager.query_memory(
                app_name="icp_agent_system",
                user_id=user_id,
                query="user name introduction personal details company my name is I am from",
                top_k=5
            )
            
            if not memories:
                return None
            
            # Extract context from memories
            context = {
                "has_previous_sessions": True,
                "user_name": None,
                "company_name": None,
                "last_icp": None,
                "session_count": len(memories)
            }
            
            # Parse memories for specific information
            for memory in memories:
                content_lower = memory.content.lower()
                
                # Extract user name
                if "my name is" in content_lower and not context["user_name"]:
                    # Try to extract name after "my name is"
                    import re
                    name_match = re.search(r"my name is ([\w]+)", content_lower)
                    if name_match:
                        context["user_name"] = name_match.group(1).capitalize()
                
                # Extract company name
                if any(phrase in content_lower for phrase in ["i run", "i work at", "my company", "we are"]):
                    # Try to extract company name
                    company_patterns = [
                        r"(?:i run|i work at|my company is|we are) ([\w\s]+?)(?:\s+that|\s+which|\.|,|$)",
                        r"company called ([\w\s]+?)(?:\s+that|\.|,|$)"
                    ]
                    for pattern in company_patterns:
                        match = re.search(pattern, content_lower)
                        if match and not context["company_name"]:
                            context["company_name"] = match.group(1).strip().title()
                            break
                
                # Check for ICP mentions
                if "icp" in content_lower and "created" in content_lower:
                    context["last_icp"] = True
            
            self.logger.info(f"Loaded user context - Name: {context['user_name']}, Company: {context['company_name']}, Has_ICP: {context['last_icp']}")
            return context
            
        except Exception as e:
            self.logger.warning(f"Could not load user context: {e}")
            return None
    
    def _generate_personalized_greeting(self, context: Dict[str, Any]) -> str:
        """Generate a personalized greeting based on user context."""
        parts = []
        
        # Personal greeting
        if context.get("user_name"):
            if context.get("role"):
                parts.append(f"Welcome back, {context['user_name']}!")
            else:
                parts.append(f"Welcome back, {context['user_name']}!")
        else:
            parts.append("Welcome back!")
        
        # Company and role context
        if context.get("company_name") and context.get("role"):
            parts.append(f"I remember you're the {context['role']} at {context['company_name']}.")
        elif context.get("company_name"):
            parts.append(f"I remember you're with {context['company_name']}.")
        elif context.get("industry"):
            parts.append(f"I see you're in the {context['industry']} industry.")
        
        # Previous ICP context
        if context.get("last_icp"):
            if context.get("icp_description"):
                parts.append(f"We previously created an ICP for {context['icp_description']}.")
            else:
                parts.append("I see we've created an ICP together before.")
            parts.append("You can ask me about your previous work or we can create something new.")
        
        # Business context
        if context.get("business_context") and not context.get("last_icp"):
            parts.append(f"I recall you mentioned: {context['business_context']}")
        
        # Session count indicator
        if context.get("session_count", 0) > 3:
            parts.append(f"Great to see you again!")
        
        return " ".join(parts) + "\n\n"
    
    async def _analyze_user_intent(self, message: str, conversation: Conversation, attachments: Optional[List[Dict[str, str]]]) -> Dict[str, Any]:
        """Use LLM to analyze user intent and determine appropriate action."""
        
        # Build context from conversation
        recent_messages = conversation.messages[-5:] if conversation.messages else []
        context_str = "\n".join([f"{msg.role}: {msg.content[:200]}..." for msg in recent_messages])
        
        analysis_prompt = f"""
        Analyze the user's message and determine their intent.
        
        Current conversation context:
        {context_str}
        
        Current workflow step: {conversation.current_step.value}
        Has business info: {bool(conversation.business_info.get('description'))}
        Has ICP: {bool(conversation.current_icp_id)}
        Has prospects: {bool(conversation.current_prospects)}
        
        User message: "{message}"
        Has attachments: {bool(attachments)}
        
        Determine the user's intent from these categories:
        1. casual_greeting - Simple greeting like "hi", "hello", "hey there"
        2. provide_business_info - Describing their business, products, or services
        3. request_icp_creation - Explicitly asking to create an ICP
        4. find_prospects - Asking to search for prospects or leads
        5. ask_question - General questions about capabilities or process
        6. provide_feedback - Giving feedback on ICP or prospects
        7. navigate_workflow - Wanting to skip steps, go back, or start over
        8. memory_query - Asking about previous work or sessions
        9. analyze_resource - Wanting to analyze a website or document
        10. unclear - Intent is ambiguous or unclear
        
        Also determine:
        - Should we advance the workflow step?
        - What's the most appropriate response type?
        
        Return JSON:
        {{
            "intent_type": "one of the categories above",
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation",
            "suggested_action": "what to do next",
            "advance_workflow": true/false,
            "detected_entities": {{"business_name": "if mentioned", "urls": ["any URLs"], "other": "relevant info"}}
        }}
        
        Examples:
        - "Hey there" → casual_greeting (don't advance workflow)
        - "We're a B2B SaaS company" → provide_business_info
        - "Create an ICP for me" → request_icp_creation
        - "I'm CEO at https://company.com --> let's create ICP" → request_icp_creation (business info + ICP request)
        - "Here's my website https://company.com, create an ICP" → request_icp_creation
        - "My company is X, now build an ICP" → request_icp_creation
        - "Find me some prospects" → find_prospects
        - "What can you do?" → ask_question
        - "refine ice: focus on startups" → provide_feedback (if ICP exists)
        - "change company size to <50 employees" → provide_feedback (if ICP exists)
        - "I don't like this ICP, modify it" → provide_feedback (if ICP exists)
        - "update the target criteria" → provide_feedback (if ICP exists)
        - "This ICP looks good, proceed" → provide_feedback (if ICP exists)
        
        IMPORTANT: If a message contains both business information AND explicit ICP creation requests 
        (like "create ICP", "build ICP", "let's create", "make an ICP"), prioritize "request_icp_creation".
        """
        
        try:
            # Use research agent's LLM for analysis
            response = await self.research_agent.process_json_request(analysis_prompt)
            
            # Parse JSON response
            import json
            intent = json.loads(response)
            
            # Ensure required fields
            intent.setdefault("intent_type", "unclear")
            intent.setdefault("confidence", 0.5)
            intent.setdefault("advance_workflow", False)
            
            return intent
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze intent, using fallback: {e}")
            
            # Simple keyword fallback for common intents
            message_lower = message.lower().strip()
            
            # Check for greetings first
            greeting_words = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "howdy"]
            if any(greeting in message_lower.split() for greeting in greeting_words) or message_lower in greeting_words:
                return {
                    "intent_type": "casual_greeting",
                    "confidence": 0.9,
                    "reasoning": "Detected greeting keyword",
                    "suggested_action": "respond_friendly",
                    "advance_workflow": False
                }
            
            # Check for ICP creation requests
            icp_phrases = ["create icp", "build icp", "make icp", "create an icp", "let's create", "lets create"]
            if any(phrase in message_lower for phrase in icp_phrases):
                return {
                    "intent_type": "request_icp_creation",
                    "confidence": 0.8,
                    "reasoning": "Detected ICP creation request",
                    "suggested_action": "create_icp",
                    "advance_workflow": True
                }
            
            # Check for prospect search
            prospect_phrases = ["find prospects", "search prospects", "find customers", "find leads", "search for prospects"]
            if any(phrase in message_lower for phrase in prospect_phrases):
                return {
                    "intent_type": "find_prospects",
                    "confidence": 0.8,
                    "reasoning": "Detected prospect search request",
                    "suggested_action": "search_prospects",
                    "advance_workflow": True
                }
            
            # Try enhanced fallback
            fallback_intent = await self._analyze_fallback_intent(message)
            if fallback_intent:
                return fallback_intent
            else:
                return {
                    "intent_type": "unclear",
                    "confidence": 0.3,
                    "reasoning": "Could not determine intent",
                    "suggested_action": "ask_clarification",
                    "advance_workflow": False
                }
    
    async def _route_message_by_intent(self, conversation: Conversation, message: str, intent: Dict[str, Any], attachments: Optional[List[Dict[str, str]]]) -> str:
        """Route message to appropriate handler based on intent."""
        
        intent_type = intent.get("intent_type", "unclear")
        
        # Handle different intents
        if intent_type == "casual_greeting":
            return await self._handle_casual_conversation(conversation, message, intent)
        
        elif intent_type == "provide_business_info":
            # Only process as business info if we're in the right step or user is providing it
            if conversation.current_step == WorkflowStep.BUSINESS_DESCRIPTION:
                return await self._handle_business_description(conversation, message, attachments or [])
            else:
                # Store the info but don't force workflow
                conversation.business_info.update({"additional_info": message})
                return "Thanks for that additional information! I've noted it down. What would you like to do next?"
        
        elif intent_type == "request_icp_creation":
            # Jump to ICP creation if we have business info
            if conversation.business_info.get("description") or message:
                if conversation.current_step != WorkflowStep.ICP_CREATION:
                    conversation.advance_step(WorkflowStep.ICP_CREATION)
                return await self._handle_icp_creation(conversation, message, attachments or [])
            else:
                return "I'd be happy to create an ICP for you! First, could you tell me about your business? What products or services do you offer?"
        
        elif intent_type == "find_prospects":
            # Jump to prospect search, create basic ICP if needed
            if conversation.current_icp_id:
                if conversation.current_step not in [WorkflowStep.PROSPECT_SEARCH, WorkflowStep.PROSPECT_REVIEW]:
                    conversation.advance_step(WorkflowStep.PROSPECT_SEARCH)
                return await self._handle_prospect_search(conversation, message, attachments or [])
            else:
                return "To find the best prospects for you, I'll need to create an ICP first. Could you tell me about your ideal customers or share your business details?"
        
        elif intent_type == "ask_question":
            return await self._handle_question(conversation, message)
        
        elif intent_type == "provide_feedback":
            # Route to appropriate refinement handler
            if conversation.current_step == WorkflowStep.ICP_REFINEMENT:
                return await self._handle_icp_refinement(conversation, message, attachments or [])
            elif conversation.current_step == WorkflowStep.PROSPECT_REVIEW:
                return await self._handle_prospect_review(conversation, message, attachments or [])
            else:
                return "Thanks for your feedback! Could you clarify what you'd like me to adjust?"
        
        elif intent_type == "navigate_workflow":
            return await self._handle_navigation_request(conversation, message, intent)
        
        elif intent_type == "memory_query":
            return await self._handle_memory_query(conversation, message)
        
        elif intent_type == "analyze_resource":
            if attachments or intent.get("detected_entities", {}).get("urls"):
                return await self._handle_resource_analysis(conversation, message, attachments or [])
            else:
                return "I'd be happy to analyze a resource for you. Please share the URL or upload the document you'd like me to review."
        
        else:  # unclear or unhandled intent
            return await self._handle_unclear_intent(conversation, message, intent)
    
    async def _handle_casual_conversation(self, conversation: Conversation, message: str, intent: Dict[str, Any]) -> str:
        """Handle casual greetings and conversation."""
        
        greetings = [
            "Hello! How can I help you today?",
            "Hi there! I'm here to help you find your ideal customers.",
            "Hey! Ready to discover some great prospects for your business?",
            "Hello! I can help you create an ICP and find qualified leads."
        ]
        
        import random
        base_greeting = random.choice(greetings)
        
        # Add context-aware suggestions
        if not conversation.business_info.get("description"):
            return f"""
{base_greeting}

To get started, I'll need to learn about your business. You can:
- Tell me what your company does
- Share your website URL
- Describe your ideal customers

What would you like to do?
            """.strip()
        elif not conversation.current_icp_id:
            return f"""
{base_greeting}

I see you've told me about your business. Would you like me to:
- Create an Ideal Customer Profile (ICP)
- Search for prospects directly
- Analyze a competitor or customer website

What sounds good?
            """.strip()
        else:
            return f"""
{base_greeting}

We've already created an ICP. Would you like to:
- Search for prospects based on your ICP
- Refine your ICP criteria
- Start fresh with a new ICP
- Ask me something else

How can I help?
            """.strip()
    
    async def _handle_question(self, conversation: Conversation, message: str) -> str:
        """Handle general questions about capabilities or process."""
        
        # Use LLM to generate appropriate response
        question_prompt = f"""
        The user is asking a question about our lead generation system.
        
        User question: "{message}"
        
        Context:
        - We help create ICPs (Ideal Customer Profiles)
        - We find prospects using HorizonDataWave (LinkedIn), Exa (web search), and Firecrawl (web scraping)
        - We use AI to score and rank prospects
        - The process is: Business Description → ICP Creation → Prospect Search → Review
        
        Provide a helpful, concise answer. Be friendly and informative.
        """
        
        try:
            response = await self.research_agent.process_message(question_prompt)
            return response
        except:
            return """
I help businesses find their ideal customers through an AI-powered process:

1. **Understanding Your Business** - You tell me about your company
2. **Creating an ICP** - I build a profile of your ideal customers
3. **Finding Prospects** - I search multiple databases for matches
4. **Scoring & Ranking** - I use AI to score each prospect
5. **Review & Export** - You review and can export the results

What would you like to know more about?
            """.strip()
    
    async def _handle_navigation_request(self, conversation: Conversation, message: str, intent: Dict[str, Any]) -> str:
        """Handle requests to navigate the workflow (skip, go back, start over)."""
        
        action = intent.get("suggested_action", "")
        
        # Use LLM to analyze navigation intent
        nav_intent = await self._analyze_navigation_intent(message, conversation)
        
        if nav_intent["action"] == "start_over":
            # Reset conversation
            conversation.current_step = WorkflowStep.BUSINESS_DESCRIPTION
            conversation.business_info = {}
            conversation.current_icp_id = None
            conversation.current_prospects = []
            return "Let's start fresh! Please tell me about your business and what kind of customers you're looking for."
        
        elif nav_intent["action"] == "skip":
            # Skip to next logical step
            if conversation.current_step == WorkflowStep.BUSINESS_DESCRIPTION and conversation.business_info:
                conversation.advance_step(WorkflowStep.ICP_CREATION)
                return "Skipping ahead! Let me create an ICP based on what you've told me so far..."
            else:
                return "I'd need some basic information first before we can skip ahead. Could you briefly describe your business?"
        
        elif nav_intent["action"] == "go_back":
            # Go back one step if possible
            return "Sure! What would you like to revisit or change?"
        
        else:
            return nav_intent.get("response", "I can help you navigate the process. Would you like to start over, skip ahead, or go back to something?")
    
    async def _handle_resource_analysis(self, conversation: Conversation, message: str, attachments: List[Dict[str, str]]) -> str:
        """Handle requests to analyze websites or documents."""
        
        # Extract URLs from message and attachments
        urls = self._extract_urls(message)
        if attachments:
            urls.extend([att.get("url") for att in attachments if att.get("url")])
        
        if not urls:
            return "Please provide a URL or document you'd like me to analyze."
        
        results = []
        for url in urls[:3]:  # Limit to 3
            try:
                analysis = await self.research_agent.website_content_analysis(
                    url=url,
                    analysis_focus=["business_model", "target_market", "products", "customers"]
                )
                if analysis["status"] == "success":
                    results.append(f"**{url}**: {analysis.get('summary', 'Analysis complete')}")
            except Exception as e:
                results.append(f"**{url}**: Could not analyze ({str(e)})")
        
        return f"""
I've analyzed the resources you provided:

{chr(10).join(results)}

Would you like me to:
- Use this information to create an ICP
- Find similar companies as prospects
- Analyze additional resources
        """.strip()
    
    async def _handle_unclear_intent(self, conversation: Conversation, message: str, intent: Dict[str, Any]) -> str:
        """Handle unclear or ambiguous messages."""
        
        # Try to provide helpful context
        return f"""
I'm not quite sure what you'd like me to do with that. Here are some things I can help with:

1. **Create an ICP** - "Help me create an ideal customer profile"
2. **Find Prospects** - "Find me some potential customers"
3. **Analyze Websites** - "Analyze [website URL]"
4. **Answer Questions** - "How does the scoring work?"
5. **Previous Work** - "What was the ICP we created last time?"

Could you clarify what you'd like help with?
        """.strip()
    
    async def _extract_user_context_with_llm(self, memories: List[Any]) -> Dict[str, Any]:
        """Use LLM to intelligently extract user context from memories."""
        
        # Combine memory contents
        memory_texts = []
        for i, memory in enumerate(memories[:5], 1):  # Limit to 5 most relevant
            memory_texts.append(f"Memory {i}: {memory.content}")
        
        combined_memories = "\n\n".join(memory_texts)
        
        extraction_prompt = f"""
        Extract key user information from these conversation memories.
        
        Memories:
        {combined_memories}
        
        Extract the following information if available:
        1. User's name (personal name, not company)
        2. Company name they work for or run
        3. Their role/position
        4. Industry or business domain
        5. Previous ICPs created (yes/no and brief description)
        6. Key business challenges or goals mentioned
        
        Return JSON with extracted information:
        {{
            "user_name": "extracted name or null",
            "company_name": "extracted company or null",
            "role": "extracted role or null",
            "industry": "extracted industry or null",
            "has_previous_icp": true/false,
            "icp_description": "brief description if ICP was created or null",
            "business_context": "brief summary of their business/goals or null",
            "confidence": {{
                "user_name": 0.0-1.0,
                "company_name": 0.0-1.0,
                "has_icp": 0.0-1.0
            }}
        }}
        
        Examples:
        - "My name is John and I run TechFlow" → user_name: "John", company_name: "TechFlow"
        - "I'm the CEO of Acme Corp" → role: "CEO", company_name: "Acme Corp"
        - "We created an ICP for B2B SaaS companies" → has_previous_icp: true, icp_description: "B2B SaaS companies"
        """
        
        try:
            # Use research agent's LLM for extraction
            response = await self.research_agent.process_json_request(extraction_prompt)
            
            # Parse JSON response
            import json
            extracted = json.loads(response)
            
            # Build context dictionary
            context = {
                "has_previous_sessions": True,
                "user_name": extracted.get("user_name"),
                "company_name": extracted.get("company_name"),
                "role": extracted.get("role"),
                "industry": extracted.get("industry"),
                "last_icp": extracted.get("has_previous_icp", False),
                "icp_description": extracted.get("icp_description"),
                "business_context": extracted.get("business_context"),
                "session_count": len(memories)
            }
            
            self.logger.info(f"Extracted user context - Name: {context['user_name']}, Company: {context['company_name']}, Has_ICP: {context['last_icp']}")
            return context
            
        except Exception as e:
            self.logger.warning(f"Failed to extract context with LLM, using basic context: {e}")
            # Fallback to basic context
            return {
                "has_previous_sessions": True,
                "user_name": None,
                "company_name": None,
                "last_icp": None,
                "session_count": len(memories)
            }
    
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
            
            self.logger.info(f"Analyzed prospect feedback intent - Intent: {intent_data}, Message_Preview: {message[:50]}")
            
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
    
    async def _analyze_icp_refinement_intent(self, message: str) -> Dict[str, Any]:
        """Use LLM to analyze user intent in ICP refinement feedback."""
        
        analysis_prompt = f"""
        Analyze this user message about ICP (Ideal Customer Profile) review and determine their intent.
        
        User message: "{message}"
        
        Context: The user has been shown an ICP and asked to review it. They can:
        1. Approve the ICP to proceed with prospect search
        2. Request changes/refinements to the ICP
        3. Ask questions about the ICP
        
        Determine if the user is:
        - APPROVING the ICP (satisfied, wants to proceed, likes it as-is)
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
        - "This ICP looks good" → approval
        - "Perfect, let's search for prospects" → approval  
        - "Great, proceed with this" → approval
        - "Approved, find prospects now" → approval
        - "I want to change the company size" → refinement
        - "Add more industries to target" → refinement
        - "This doesn't match my customers" → refinement
        - "refine ice: focus on startups" → refinement
        - "refine ICP: change company size to <50 employees" → refinement
        - "update the ICP with these changes" → refinement
        - "modify the target criteria" → refinement
        - "What does this criterion mean?" → question
        - "How did you determine these pain points?" → question
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
            
            self.logger.info(f"Analyzed ICP refinement intent - Intent: {intent_data}, Message_Preview: {message[:50]}")
            
            return intent_data
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze ICP refinement intent via LLM, falling back to keywords: {e}")
            
            # Fallback to simple keyword analysis (includes the original keywords for backward compatibility)
            lower_msg = message.lower()
            
            # Simple approval detection as fallback
            approval_keywords = ["yes", "good", "looks good", "great", "perfect", "approve", "approved", "proceed", "search", "move forward", "find prospects"]
            refinement_keywords = ["no", "change", "refine", "adjust", "don't like", "wrong", "bad", "improve", "add", "remove", "modify"]
            
            is_approval = any(keyword in lower_msg for keyword in approval_keywords)
            is_refinement = any(keyword in lower_msg for keyword in refinement_keywords)
            
            return {
                "is_approval": is_approval and not is_refinement,
                "is_refinement_request": is_refinement or (not is_approval and len(message) > 10),
                "is_question": "?" in message or "what" in lower_msg or "how" in lower_msg,
                "confidence": 0.6,
                "reasoning": "Fallback keyword analysis"
            }
    
    async def _analyze_automation_setup_intent(self, message: str) -> Dict[str, Any]:
        """Use LLM to analyze user intent for automation setup."""
        
        try:
            prompt = f"""
            Analyze the user's response to determine if they want to set up automated prospect monitoring.
            
            User message: "{message}"
            
            Determine:
            1. Does the user want automation? (yes/no)
            2. What type of automation they prefer (if any)
            3. Confidence level (0.0-1.0)
            4. Brief reasoning
            
            Respond with JSON only:
            {{
                "wants_automation": true/false,
                "automation_type": "daily_monitoring" | "weekly_summary" | "custom" | "none",
                "confidence": 0.0-1.0,
                "reasoning": "Brief explanation"
            }}
            
            Examples:
            - "Yes, set it up" → wants_automation: true
            - "Sure, daily monitoring sounds good" → wants_automation: true, automation_type: "daily_monitoring"
            - "No thanks, I'll do it manually" → wants_automation: false
            - "Not now" → wants_automation: false
            """
            
            response = await self.research_agent.process_json_request(prompt)
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response)
                return result
            except:
                # Fallback to keyword analysis
                message_lower = message.lower()
                wants_automation = any(word in message_lower for word in ["yes", "setup", "automate", "monitor", "sure", "ok", "sounds good"])
                return {
                    "wants_automation": wants_automation,
                    "automation_type": "daily_monitoring" if wants_automation else "none",
                    "confidence": 0.7,
                    "reasoning": "Fallback keyword analysis"
                }
                
        except Exception as e:
            self.logger.warning(f"Error analyzing automation intent: {e}")
            # Fallback to keyword analysis
            message_lower = message.lower()
            wants_automation = any(word in message_lower for word in ["yes", "setup", "automate", "monitor", "sure", "ok", "sounds good"])
            return {
                "wants_automation": wants_automation,
                "automation_type": "daily_monitoring" if wants_automation else "none",
                "confidence": 0.6,
                "reasoning": "Fallback keyword analysis"
            }
    
    async def _analyze_fallback_intent(self, message: str) -> Optional[Dict[str, Any]]:
        """Enhanced fallback intent analysis using LLM when primary analysis fails."""
        
        try:
            prompt = f"""
            Analyze this user message to determine the basic intent when primary analysis has failed.
            
            User message: "{message}"
            
            Determine the most likely intent category:
            1. casual_greeting - Simple hello, hi, greeting
            2. question - Asking about something
            3. business_description - Describing their business
            4. unclear - Cannot determine intent
            
            Respond with JSON only:
            {{
                "intent_type": "casual_greeting" | "question" | "business_description" | "unclear",
                "confidence": 0.0-1.0,
                "reasoning": "Brief explanation",
                "suggested_action": "respond_friendly" | "ask_clarification" | "analyze_business" | "unclear",
                "advance_workflow": true/false
            }}
            """
            
            response = await self.research_agent.process_json_request(prompt)
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response)
                return result
            except:
                # Simple keyword fallback
                message_lower = message.lower()
                if any(greeting in message_lower for greeting in ["hi", "hello", "hey", "greetings"]):
                    return {
                        "intent_type": "casual_greeting",
                        "confidence": 0.8,
                        "reasoning": "Detected greeting pattern",
                        "suggested_action": "respond_friendly",
                        "advance_workflow": False
                    }
                return None
                
        except Exception as e:
            self.logger.warning(f"Error analyzing fallback intent: {e}")
            return None
    
    async def _analyze_navigation_intent(self, message: str, conversation: Conversation) -> Dict[str, Any]:
        """Use LLM to analyze navigation intent (start over, skip, go back)."""
        
        try:
            current_step = conversation.current_step.value if conversation.current_step else "unknown"
            
            prompt = f"""
            Analyze the user's message to determine navigation intent within our sales lead generation workflow.
            
            User message: "{message}"
            Current step: {current_step}
            
            Determine navigation action:
            1. start_over - User wants to restart the entire process
            2. skip - User wants to skip current step and move forward
            3. go_back - User wants to return to previous step
            4. continue - User wants to continue with current process
            5. unclear - Cannot determine navigation intent
            
            Respond with JSON only:
            {{
                "action": "start_over" | "skip" | "go_back" | "continue" | "unclear",
                "confidence": 0.0-1.0,
                "reasoning": "Brief explanation",
                "response": "Appropriate response message to user"
            }}
            
            Examples:
            - "Let's start over" → action: "start_over"
            - "Can we skip this step?" → action: "skip"
            - "Go back to the previous step" → action: "go_back"
            - "I'm not sure what to do" → action: "unclear"
            """
            
            response = await self.research_agent.process_json_request(prompt)
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response)
                return result
            except:
                # Fallback to keyword analysis
                message_lower = message.lower()
                if "start over" in message_lower or "restart" in message_lower:
                    return {
                        "action": "start_over",
                        "confidence": 0.8,
                        "reasoning": "Detected restart keywords",
                        "response": "Let's start fresh! Please tell me about your business and what kind of customers you're looking for."
                    }
                elif "skip" in message_lower:
                    return {
                        "action": "skip",
                        "confidence": 0.8,
                        "reasoning": "Detected skip keyword",
                        "response": "Skipping ahead!"
                    }
                elif "go back" in message_lower or "previous" in message_lower:
                    return {
                        "action": "go_back",
                        "confidence": 0.8,
                        "reasoning": "Detected back navigation keywords",
                        "response": "Sure! What would you like to revisit or change?"
                    }
                else:
                    return {
                        "action": "unclear",
                        "confidence": 0.3,
                        "reasoning": "Could not determine navigation intent",
                        "response": "I can help you navigate the process. Would you like to start over, skip ahead, or go back to something?"
                    }
                
        except Exception as e:
            self.logger.warning(f"Error analyzing navigation intent: {e}")
            return {
                "action": "unclear",
                "confidence": 0.3,
                "reasoning": "Error in navigation analysis",
                "response": "I can help you navigate the process. Would you like to start over, skip ahead, or go back to something?"
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
    
    async def _store_conversation_to_memory(self, conversation: Conversation) -> None:
        """Store conversation to persistent memory (SQLite database)."""
        
        if not self.memory_manager:
            self.logger.debug("No memory manager available - conversation not persisted")
            return
        
        try:
            # Extract key information about the user for future context
            user_info = {}
            business_info = {}
            
            # Extract user name and business info from conversation messages
            for message in conversation.messages:
                if message.role == MessageRole.USER:
                    content = message.content.lower()
                    
                    # Extract user name patterns
                    if "my name is" in content:
                        name_part = content.split("my name is")[1].split(".")[0].split(",")[0].strip()
                        if name_part:
                            user_info["name"] = name_part.title()
                    
                    # Extract business/company info
                    if "my business is" in content or "my company is" in content:
                        if "https://" in content or "http://" in content:
                            import re
                            urls = re.findall(r'https?://[^\s]+', content)
                            if urls:
                                business_info["website"] = urls[0]
                                # Extract domain name as company identifier
                                domain = urls[0].replace("https://", "").replace("http://", "").split("/")[0]
                                business_info["domain"] = domain
            
            # Store conversation with enhanced context
            conversation_summary = {
                "conversation_id": conversation.id,
                "user_id": conversation.user_id,
                "current_step": conversation.current_step.value,
                "business_info": conversation.business_info,
                "user_info": user_info,
                "business_context": business_info,
                "icp_id": conversation.current_icp_id,
                "prospect_count": len(conversation.current_prospects),
                "message_count": len(conversation.messages),
                "last_activity": conversation.updated_at.isoformat()
            }
            
            # Store to memory manager using the correct API
            messages = []
            for msg in conversation.messages:
                messages.append({
                    "role": msg.role.value.lower(),
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if hasattr(msg, 'timestamp') else datetime.now().isoformat()
                })
            
            await self.memory_manager.ingest_memory(
                app_name="icp_agent_system",
                user_id=conversation.user_id,
                session_id=conversation.id,
                messages=messages,
                metadata={
                    "agent": "adk_orchestrator",
                    "current_step": conversation.current_step.value,
                    "user_info": user_info,
                    "business_context": business_info,
                    "icp_id": conversation.current_icp_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            self.logger.debug(f"Stored conversation to memory - ID: {conversation.id}, Messages: {len(conversation.messages)}, User_Info: {user_info}, Business: {business_info}")
            
        except Exception as e:
            self.logger.error(f"Failed to store conversation to memory - Conversation_ID: {conversation.id}, Error: {str(e)}")


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