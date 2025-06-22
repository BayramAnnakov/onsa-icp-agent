"""
Gradio web interface for testing the ADK multi-agent sales lead generation system.

This provides an easy-to-use interface for testing main and feedback workflows.
"""

import asyncio
import gradio as gr
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import json
import os
from pathlib import Path

from adk_main import ADKAgentOrchestrator
from utils.config import Config
from models import WorkflowStep
from utils.logging_config import setup_logging, get_logger
import structlog

# Setup logging with file output
setup_logging(
    log_file="logs/adk_agent_web.log",
    console_level="INFO",
    file_level="DEBUG"
)
logger = get_logger(__name__)


class WebInterface:
    """Gradio web interface for the ADK agent system."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.config.ensure_directories()
        
        # Initialize memory manager if VertexAI is enabled
        memory_manager = None
        if self.config.vertexai.enabled:
            try:
                from services.vertex_memory_service import VertexMemoryManager
                memory_manager = VertexMemoryManager(self.config.vertexai)
                logger.info("VertexAI memory manager initialized for web interface")
            except Exception as e:
                logger.error(f"Failed to initialize VertexAI memory: {str(e)}")
        
        self.orchestrator = ADKAgentOrchestrator(self.config, memory_manager=memory_manager)
        self.current_conversation_id: Optional[str] = None
        self.conversation_history: List[Tuple[str, str]] = []
        self.current_prospects: List[Dict[str, Any]] = []  # Store prospects for table display
        
        # Session storage
        self.sessions_dir = Path("sessions")
        self.sessions_dir.mkdir(exist_ok=True)
        
        logger.info(f"Web interface initialized - Memory enabled: {bool(memory_manager)}")
    
    async def start_new_conversation(self, user_id: str = "web_user") -> str:
        """Start a new conversation."""
        self.current_conversation_id = await self.orchestrator.start_conversation(user_id)
        self.conversation_history = []
        logger.info(f"Started new conversation: {self.current_conversation_id}")
        return self.current_conversation_id
    
    async def process_message(
        self,
        message: str,
        history: List[Tuple[str, str]],
        agent_type: str,
        attachments: Optional[List[str]] = None
    ) -> Tuple[List[Tuple[str, str]], str]:
        """Process a user message and return updated history."""
        
        try:
            # Start conversation if needed
            if not self.current_conversation_id:
                await self.start_new_conversation()
            
            # Add user message to history
            history.append((message, None))
            
            # Process attachments if any
            attachment_list = []
            if attachments:
                for attachment in attachments:
                    attachment_list.append({
                        "type": "url",
                        "url": attachment
                    })
            
            # Process message based on agent type
            if agent_type == "Main Workflow":
                response = await self.orchestrator.process_user_message(
                    self.current_conversation_id,
                    message,
                    attachment_list
                )
            else:
                # Direct agent interaction
                response = await self._process_direct_agent_message(
                    agent_type,
                    message,
                    attachment_list
                )
            
            # Update history with response
            history[-1] = (message, response)
            
            # Get status
            status = self._get_conversation_status()
            
            return history, status
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_response = f"❌ Error: {str(e)}"
            if history and history[-1][1] is None:
                history[-1] = (history[-1][0], error_response)
            else:
                history.append((message, error_response))
            return history, "Error occurred"
    
    async def _process_direct_agent_message(
        self,
        agent_type: str,
        message: str,
        attachments: List[Dict[str, str]]
    ) -> str:
        """Process message for direct agent interaction."""
        
        if agent_type == "ICP Agent":
            # Example: Create ICP from company URLs
            if attachments:
                company_urls = [att["url"] for att in attachments]
                result = await self.orchestrator.icp_agent.create_icp_from_research(
                    business_info={"description": message},
                    example_companies=company_urls,
                    research_depth="standard"
                )
                
                if result["status"] == "success":
                    icp_data = result.get("icp", {})
                    formatted_icp = self.orchestrator._format_icp_for_display(icp_data)
                    return f"✅ ICP Created Successfully!\n\n{formatted_icp}"
                else:
                    return f"❌ Error creating ICP: {result.get('error_message', 'Unknown error')}"
            else:
                return "Please attach company URLs to analyze for ICP creation."
        
        elif agent_type == "Prospect Agent":
            # Search for prospects
            if self.current_conversation_id and self.orchestrator.conversations.get(self.current_conversation_id):
                conv = self.orchestrator.conversations[self.current_conversation_id]
                if conv.current_icp_id:
                    result = await self.orchestrator.prospect_agent.search_prospects(
                        icp_id=conv.current_icp_id,
                        limit=10,
                        search_mode="fast"
                    )
                    
                    if result["status"] == "success":
                        prospects = result.get("prospects", [])
                        formatted = self.orchestrator._format_prospects_for_display(prospects)
                        return f"✅ Found {len(prospects)} prospects:\n\n{formatted}"
                    else:
                        return f"❌ Error searching prospects: {result.get('error_message', 'Unknown error')}"
                else:
                    return "Please create an ICP first before searching for prospects."
            else:
                return "Please start with the main workflow to create an ICP."
        
        elif agent_type == "Research Agent":
            # Perform research
            result = await self.orchestrator.research_agent.research_topic(
                topic=message,
                max_results=5
            )
            
            if result["status"] == "success":
                research_data = result.get("research", {})
                summary = research_data.get("summary", "No summary available")
                sources = research_data.get("sources", [])
                
                formatted_sources = "\n".join([f"- {s.get('title', 'Unknown')}: {s.get('url', '')}" for s in sources[:5]])
                
                return f"✅ Research Complete!\n\n**Summary:**\n{summary}\n\n**Sources:**\n{formatted_sources}"
            else:
                return f"❌ Error performing research: {result.get('error_message', 'Unknown error')}"
        
        return "Please select a valid agent type."
    
    async def process_message_stream(
        self,
        message: str,
        history: List[Tuple[str, str]],
        agent_type: str,
        attachments: Optional[List[str]] = None
    ):
        """Process a user message with streaming responses.
        
        Yields (history, status, prospect_table_data, prospect_table_visible) tuples.
        """
        
        try:
            # Start conversation if needed
            if not self.current_conversation_id:
                await self.start_new_conversation()
            
            # Add user message to history
            history.append((message, ""))
            
            # Process attachments if any
            attachment_list = []
            if attachments:
                for attachment in attachments:
                    attachment_list.append({
                        "type": "url",
                        "url": attachment
                    })
            
            # Process message based on agent type
            if agent_type == "Main Workflow":
                # Collect full response for history tracking
                full_response = ""
                async for chunk in self.orchestrator.process_user_message_stream(
                    self.current_conversation_id,
                    message,
                    attachment_list
                ):
                    full_response += chunk
                    # Update the last message in history with accumulated response
                    history[-1] = (message, full_response)
                    
                    # Check if we have prospects to display
                    status = self.orchestrator.get_conversation_status(self.current_conversation_id)
                    if status and status.get('current_step') == 'prospect_review' and status.get('prospect_count', 0) > 0:
                        # Get prospects from orchestrator
                        conversation = self.orchestrator.conversations.get(self.current_conversation_id)
                        if conversation and hasattr(conversation, 'current_prospects'):
                            # Get prospect details
                            prospect_ids = conversation.current_prospects
                            if prospect_ids and self.orchestrator.prospect_agent.active_prospects:
                                prospects = []
                                for pid in prospect_ids[:10]:  # Top 10
                                    if pid in self.orchestrator.prospect_agent.active_prospects:
                                        prospect = self.orchestrator.prospect_agent.active_prospects[pid]
                                        prospects.append(prospect.model_dump())
                                
                                if prospects:
                                    self.current_prospects = prospects
                                    table_data = self._format_prospects_for_dataframe(prospects)
                                    yield history, self._get_conversation_status(), table_data, True
                                    continue
                    
                    yield history, self._get_conversation_status(), [], False
            else:
                # Direct agent interaction (non-streaming for now)
                response = await self._process_direct_agent_message(
                    agent_type,
                    message,
                    attachment_list
                )
                history[-1] = (message, response)
                yield history, self._get_conversation_status(), [], False
            
        except Exception as e:
            logger.error(f"Error processing message stream: {str(e)}")
            error_response = f"❌ Error: {str(e)}"
            if history and history[-1][1] == "":
                history[-1] = (history[-1][0], error_response)
            else:
                history.append((message, error_response))
            yield history, "Error occurred", [], False
    
    def _get_conversation_status(self) -> str:
        """Get current conversation status."""
        
        if not self.current_conversation_id:
            return "No active conversation"
        
        status = self.orchestrator.get_conversation_status(self.current_conversation_id)
        if not status:
            return "Conversation not found"
        
        step = status['current_step'].replace('_', ' ').title()
        icp_status = "✅" if status['icp_id'] else "⏳"
        prospect_count = status['prospect_count']
        
        return f"📊 Status: {step} | ICP: {icp_status} | Prospects: {prospect_count}"
    
    def _format_prospects_for_dataframe(self, prospects: List[Dict[str, Any]]) -> List[List[str]]:
        """Format prospects for Gradio DataFrame display."""
        data = []
        
        # Sort prospects by total_score in descending order
        sorted_prospects = sorted(prospects, key=lambda p: p.get('score', {}).get('total_score', 0), reverse=True)
        
        for prospect in sorted_prospects[:10]:  # Limit to top 10
            company = prospect.get('company', {})
            person = prospect.get('person', {})
            score_data = prospect.get('score', {})
            
            # Format name with LinkedIn link
            first_name = person.get('first_name', 'Unknown')
            last_name = person.get('last_name', '')
            person_name = f"{first_name} {last_name}".strip()
            linkedin_url = person.get('linkedin_url', '')
            
            if linkedin_url and linkedin_url != 'Not available':
                # HTML link that opens in new tab
                name_display = f'<a href="{linkedin_url}" target="_blank" style="color: #0066cc; text-decoration: none;">{person_name}</a>'
            else:
                name_display = person_name
            
            # Format company with LinkedIn link
            company_name = company.get('name') or 'N/A'
            company_linkedin = company.get('linkedin_url', '')
            
            if company_linkedin and company_linkedin != 'Not available':
                # HTML link that opens in new tab
                company_display = f'<a href="{company_linkedin}" target="_blank" style="color: #0066cc; text-decoration: none;">{company_name}</a>'
            else:
                company_display = company_name
            
            # Format score with emoji (already in 0-1 scale from scoring)
            total_score = score_data.get('total_score', 0)
            
            if total_score >= 0.8:
                score_emoji = "🟢"
            elif total_score >= 0.6:
                score_emoji = "🟡"
            else:
                score_emoji = "🔴"
            
            # Display as 0-10 scale for user readability
            score_display = f"{score_emoji} {total_score * 10:.1f}"
            
            # Get reasoning from score_explanation
            reasoning = score_data.get('score_explanation', 'No reasoning provided')
            if len(reasoning) > 150:
                reasoning = reasoning[:147] + "..."
            
            data.append([name_display, company_display, score_display, reasoning])
        
        return data
    
    def save_session(self, name: str, history: List[Tuple[str, str]]) -> str:
        """Save the current session."""
        
        if not history:
            return "No conversation to save"
        
        session_data = {
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "conversation_id": self.current_conversation_id,
            "history": history,
            "status": self._get_conversation_status()
        }
        
        filename = f"{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.sessions_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(session_data, f, indent=2)
            return f"✅ Session saved to {filename}"
        except Exception as e:
            return f"❌ Error saving session: {str(e)}"
    
    def load_session(self, session_file: str) -> Tuple[List[Tuple[str, str]], str]:
        """Load a saved session."""
        
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            history = session_data.get("history", [])
            # Convert to tuples if needed
            history = [(h[0], h[1]) for h in history]
            
            status = session_data.get("status", "Session loaded")
            
            return history, f"✅ Loaded session: {session_data.get('name', 'Unknown')}"
        except Exception as e:
            return [], f"❌ Error loading session: {str(e)}"
    
    def get_saved_sessions(self) -> List[str]:
        """Get list of saved sessions."""
        
        sessions = []
        for file in self.sessions_dir.glob("*.json"):
            sessions.append(str(file))
        return sorted(sessions, reverse=True)
    
    def export_results(self, history: List[Tuple[str, str]], format: str = "markdown") -> str:
        """Export conversation results."""
        
        if not history:
            return "No conversation to export"
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if format == "markdown":
            content = f"# ADK Agent Conversation Export\n\n"
            content += f"**Exported:** {timestamp}\n\n"
            content += f"**Status:** {self._get_conversation_status()}\n\n"
            content += "## Conversation History\n\n"
            
            for user_msg, agent_msg in history:
                content += f"### User:\n{user_msg}\n\n"
                content += f"### Agent:\n{agent_msg}\n\n"
                content += "---\n\n"
            
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            
        else:  # JSON format
            export_data = {
                "timestamp": timestamp,
                "conversation_id": self.current_conversation_id,
                "status": self._get_conversation_status(),
                "history": history
            }
            content = json.dumps(export_data, indent=2)
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.sessions_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return f"✅ Exported to {filename}"
        except Exception as e:
            return f"❌ Error exporting: {str(e)}"


def create_interface(web_interface=None, deployment_mode="local"):
    """Create the Gradio interface.
    
    Args:
        web_interface: Optional WebInterface instance. If None, creates a new one.
        deployment_mode: Either "local" or "cloud_run" to control UI elements
    """
    
    if web_interface is None:
        web_interface = WebInterface()
    
    # Adjust theme and CSS based on deployment
    css = """
    .gradio-container {
        max-width: 1200px !important;
    }
    """ if deployment_mode == "cloud_run" else ""
    
    with gr.Blocks(
        title="ADK Multi-Agent Sales System", 
        theme=gr.themes.Soft(),
        css=css
    ) as app:
        # Header with deployment mode indicator
        deployment_badge = "☁️ Cloud Run" if deployment_mode == "cloud_run" else "💻 Local"
        
        gr.Markdown(
            f"""
            # 🎯 ADK Multi-Agent Sales Lead Generation System
            
            <div style='text-align: right; font-size: 0.9em; color: #666;'>{deployment_badge}</div>
            
            Test the main workflow and individual agents for ICP creation and prospect discovery.
            
            **Quick Start**: Type your company URL (e.g., "my company is https://onsa.ai") or describe your business to begin!
            """
        )
        
        with gr.Row():
            with gr.Column(scale=3):
                # Chat interface
                chatbot = gr.Chatbot(
                    label="Conversation",
                    height=400,
                    show_copy_button=True
                )
                
                # Prospect DataFrame (initially hidden)
                prospect_table = gr.DataFrame(
                    headers=["Name", "Company", "Score", "Reasoning"],
                    datatype=["html", "html", "markdown", "str"],
                    interactive=False,
                    visible=False,
                    label="🏆 Top Prospects",
                    wrap=True,
                    row_count=(10, "fixed"),
                    col_count=(4, "fixed")
                )
                
                with gr.Row():
                    msg = gr.Textbox(
                        label="Your Message",
                        placeholder="Describe your ideal customers or ask a question... (URLs in message will be auto-detected)",
                        lines=2,
                        scale=4
                    )
                    
                    submit = gr.Button("Send", variant="primary", scale=1)
                
                with gr.Row():
                    attachments = gr.Textbox(
                        label="Additional URLs (Optional)",
                        placeholder="Enter additional URLs separated by commas (or include URLs directly in your message)",
                        lines=1
                    )
                
                # Status display
                status = gr.Textbox(
                    label="Status",
                    value="Ready to start",
                    interactive=False
                )
            
            with gr.Column(scale=1):
                # Controls
                agent_type = gr.Radio(
                    ["Main Workflow", "ICP Agent", "Prospect Agent", "Research Agent"],
                    label="Agent Type",
                    value="Main Workflow"
                )
                
                gr.Markdown("### Session Management")
                
                new_session = gr.Button("New Session", variant="secondary")
                clear = gr.Button("Clear History", variant="secondary")
                
                session_name = gr.Textbox(
                    label="Session Name",
                    placeholder="My ICP Session",
                    value=f"Session_{datetime.now().strftime('%Y%m%d')}"
                )
                
                save_btn = gr.Button("Save Session", variant="secondary")
                save_status = gr.Textbox(label="Save Status", interactive=False)
                
                gr.Markdown("### Load Session")
                
                session_dropdown = gr.Dropdown(
                    choices=web_interface.get_saved_sessions(),
                    label="Saved Sessions",
                    interactive=True
                )
                
                load_btn = gr.Button("Load Session", variant="secondary")
                
                gr.Markdown("### Export Results")
                
                export_format = gr.Radio(
                    ["markdown", "json"],
                    label="Export Format",
                    value="markdown"
                )
                
                export_btn = gr.Button("Export", variant="secondary")
                export_status = gr.Textbox(label="Export Status", interactive=False)
        
        # Event handlers
        async def respond(message, chat_history, agent, attach_text):
            if not message:
                yield chat_history, status.value, gr.update(visible=False)
                return
            
            # Parse attachments
            attachments = []
            if attach_text:
                urls = [url.strip() for url in attach_text.split(',') if url.strip()]
                attachments = urls
            
            # Also check if message contains URLs
            import re
            url_pattern = r'https?://[^\s]+'
            urls_in_message = re.findall(url_pattern, message)
            if urls_in_message and not attachments:
                attachments = urls_in_message
            
            # Process message with streaming
            try:
                async for updated_history, new_status, table_data, table_visible in web_interface.process_message_stream(
                    message,
                    chat_history,
                    agent,
                    attachments
                ):
                    if table_visible and table_data:
                        # Ensure table data is properly formatted
                        yield updated_history, new_status, gr.update(value=table_data, visible=True)
                    else:
                        # Keep table hidden if no data
                        yield updated_history, new_status, gr.update(visible=False)
            except Exception as e:
                logger.error(f"Error in respond handler: {str(e)}")
                yield chat_history, f"Error: {str(e)}", gr.update(visible=False)
        
        # Submit handlers
        msg.submit(
            respond,
            [msg, chatbot, agent_type, attachments],
            [chatbot, status, prospect_table]
        ).then(
            lambda: "",
            None,
            msg
        )
        
        submit.click(
            respond,
            [msg, chatbot, agent_type, attachments],
            [chatbot, status, prospect_table]
        ).then(
            lambda: "",
            None,
            msg
        )
        
        # Session management
        async def start_new_session():
            await web_interface.start_new_conversation()
            return [], "New session started", web_interface.get_saved_sessions(), gr.update(visible=False)
        
        new_session.click(
            start_new_session,
            None,
            [chatbot, status, session_dropdown, prospect_table]
        )
        
        clear.click(
            lambda: ([], "History cleared", gr.update(visible=False)),
            None,
            [chatbot, status, prospect_table]
        )
        
        # Save/Load handlers
        save_btn.click(
            lambda name, history: web_interface.save_session(name, history),
            [session_name, chatbot],
            save_status
        ).then(
            lambda: web_interface.get_saved_sessions(),
            None,
            session_dropdown
        )
        
        load_btn.click(
            lambda session: web_interface.load_session(session),
            session_dropdown,
            [chatbot, status]
        )
        
        # Export handler
        export_btn.click(
            lambda history, fmt: web_interface.export_results(history, fmt),
            [chatbot, export_format],
            export_status
        )
        
        # Refresh session list on load
        app.load(
            lambda: web_interface.get_saved_sessions(),
            None,
            session_dropdown
        )
    
    return app


def create_app_for_deployment(deployment_mode="local"):
    """Create app configured for specific deployment mode.
    
    Args:
        deployment_mode: Either "local" or "cloud_run"
        
    Returns:
        Gradio app configured for the deployment mode
    """
    # Create web interface instance once
    web_interface = WebInterface()
    
    # Create Gradio app with deployment-specific configuration
    app = create_interface(web_interface=web_interface, deployment_mode=deployment_mode)
    
    if deployment_mode == "cloud_run":
        # For Cloud Run, we'll return the app to be mounted on FastAPI
        return app, web_interface
    else:
        # For local deployment, return just the app
        return app


def run_local_server():
    """Run the web interface locally."""
    import os
    
    print("Starting ADK Multi-Agent Web Interface...")
    print("Loading configuration...")
    
    # Get port from environment or default
    port = int(os.environ.get("PORT", 7860))
    host = os.environ.get("HOST", "0.0.0.0")
    
    try:
        app = create_app_for_deployment("local")
        print("\n✅ Web interface ready!")
        print(f"🌐 Opening at http://{host}:{port}")
        print("\nPress Ctrl+C to stop the server\n")
        
        app.launch(
            server_name=host,
            server_port=port,
            share=False,
            show_error=True
        )
        
    except Exception as e:
        print(f"\n❌ Error starting web interface: {str(e)}")
        print("📄 Check logs for more details")
        raise


def run_cloud_server():
    """Run the web interface for Cloud Run with FastAPI."""
    import os
    from fastapi import FastAPI
    import uvicorn
    import gradio as gr
    
    logger.info("Starting ADK Multi-Agent Sales System for Cloud Run")
    
    # Create FastAPI app
    fastapi_app = FastAPI(title="ADK Sales System")
    
    # Add health check endpoint
    @fastapi_app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "adk-sales-system",
            "version": "1.0.0",
            "apis": {
                "google": bool(os.getenv("GOOGLE_API_KEY")),
                "hdw": bool(os.getenv("HDW_API_TOKEN")),
                "exa": bool(os.getenv("EXA_API_KEY")),
                "firecrawl": bool(os.getenv("FIRECRAWL_API_KEY"))
            }
        }
    
    # Add root endpoint
    @fastapi_app.get("/")
    async def root():
        return {"message": "ADK Sales System - Access the UI at /gradio"}
    
    # Create Gradio app for Cloud Run
    gradio_app, _ = create_app_for_deployment("cloud_run")
    
    # Mount Gradio app on the FastAPI app
    app = gr.mount_gradio_app(fastapi_app, gradio_app, path="/gradio")
    
    # Get host and port
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8080))
    
    # Run with uvicorn
    logger.info(f"Starting FastAPI server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    import os
    
    # Check deployment mode
    deployment_mode = os.environ.get("DEPLOYMENT_MODE", "local").lower()
    
    if deployment_mode == "cloud_run":
        run_cloud_server()
    else:
        run_local_server()