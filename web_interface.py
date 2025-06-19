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
import structlog
from setup_logging import setup_logging

# Setup file logging
log_file = setup_logging(log_dir="logs", log_level="INFO")
logger = structlog.get_logger()


class WebInterface:
    """Gradio web interface for the ADK agent system."""
    
    def __init__(self):
        self.config = Config.load_from_file()
        self.config.ensure_directories()
        self.orchestrator = ADKAgentOrchestrator(self.config)
        self.current_conversation_id: Optional[str] = None
        self.conversation_history: List[Tuple[str, str]] = []
        
        # Session storage
        self.sessions_dir = Path("sessions")
        self.sessions_dir.mkdir(exist_ok=True)
        
        logger.info("Web interface initialized")
    
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


def create_interface():
    """Create the Gradio interface."""
    
    web_interface = WebInterface()
    
    with gr.Blocks(title="ADK Multi-Agent Sales System", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 🎯 ADK Multi-Agent Sales Lead Generation System
            
            Test the main workflow and individual agents for ICP creation and prospect discovery.
            
            **Quick Start**: Type your company URL (e.g., "my company is https://onsa.ai") or describe your business to begin!
            """
        )
        
        with gr.Row():
            with gr.Column(scale=3):
                # Chat interface
                chatbot = gr.Chatbot(
                    label="Conversation",
                    height=500,
                    show_copy_button=True
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
                return chat_history, status.value
            
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
            
            # Process message
            updated_history, new_status = await web_interface.process_message(
                message,
                chat_history,
                agent,
                attachments
            )
            
            return updated_history, new_status
        
        # Submit handlers
        msg.submit(
            respond,
            [msg, chatbot, agent_type, attachments],
            [chatbot, status]
        ).then(
            lambda: "",
            None,
            msg
        )
        
        submit.click(
            respond,
            [msg, chatbot, agent_type, attachments],
            [chatbot, status]
        ).then(
            lambda: "",
            None,
            msg
        )
        
        # Session management
        async def start_new_session():
            await web_interface.start_new_conversation()
            return [], "New session started", web_interface.get_saved_sessions()
        
        new_session.click(
            start_new_session,
            None,
            [chatbot, status, session_dropdown]
        )
        
        clear.click(
            lambda: ([], "History cleared"),
            None,
            [chatbot, status]
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


if __name__ == "__main__":
    print("Starting ADK Multi-Agent Web Interface...")
    print("Loading configuration...")
    print(f"📄 Logs will be saved to: {log_file}")
    
    try:
        app = create_interface()
        print("\n✅ Web interface ready!")
        print("🌐 Opening at http://localhost:7860")
        print("\nPress Ctrl+C to stop the server\n")
        print("💡 To analyze logs for issues, run: python analyze_logs.py")
        
        app.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            show_error=True
        )
        
    except Exception as e:
        print(f"\n❌ Error starting web interface: {str(e)}")
        print(f"📄 Check logs at: {log_file}")
        raise