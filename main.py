#!/usr/bin/env python3
"""
Full ADK Multi-Agent Sales Lead Generation System for Cloud Run.
"""

import os
import sys
import asyncio
from pathlib import Path

# Setup Python path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logging_config import setup_logging, get_logger

# Configure logging with file output
setup_logging(
    log_file="logs/adk_agent_main.log",
    console_level="INFO",
    file_level="DEBUG"
)
logger = get_logger(__name__)

def get_port():
    """Get port from environment or default to 8080."""
    return int(os.environ.get("PORT", 8080))

def get_host():
    """Get host from environment or default to 0.0.0.0 for Cloud Run."""
    return os.environ.get("HOST", "0.0.0.0")

def create_gradio_app():
    """Create the Gradio application."""
    import gradio as gr
    from adk_main import ADKAgentOrchestrator  
    from utils.config import Config
    from web_interface import WebInterface
    
    logger.info("Creating Gradio application")
    
    # Ensure required directories exist
    for directory in ["cache", "logs", "sessions", "data"]:
        Path(directory).mkdir(exist_ok=True)
    
    # Initialize web interface
    web_interface = WebInterface()
    logger.info("Web interface initialized")
    
    # Create Gradio interface
    with gr.Blocks(
        title="ADK Multi-Agent Sales Lead Generation System",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        """
    ) as app:
            
            # Header
            gr.Markdown("""
            # 🎯 ADK Multi-Agent Sales Lead Generation System
            
            **Powered by Google ADK | HorizonDataWave | Exa AI | Firecrawl**
            
            Generate high-quality B2B sales prospects using AI-powered ICP creation and multi-source data enrichment.
            """)
            
            # Status indicator
            api_status = []
            if os.getenv("GOOGLE_API_KEY"): api_status.append("Google API ✅")
            if os.getenv("HDW_API_TOKEN"): api_status.append("HDW ✅")
            if os.getenv("EXA_API_KEY"): api_status.append("Exa ✅") 
            if os.getenv("FIRECRAWL_API_KEY"): api_status.append("Firecrawl ✅")
            
            status_text = f"🟢 System Ready | APIs: {' | '.join(api_status) if api_status else 'Google API Only'}"
            gr.HTML(f"<div style='padding: 10px; background: #e8f5e8; border-radius: 5px; text-align: center;'><strong>{status_text}</strong></div>")
            
            with gr.Row():
                with gr.Column(scale=2):
                    # Main chat interface
                    chatbot = gr.Chatbot(
                        label="ADK Agent Conversation",
                        height=500,
                        show_label=True,
                        container=True,
                        type="tuples"  # Fixed deprecated parameter
                    )
                    
                    msg = gr.Textbox(
                        label="Your Message",
                        placeholder="Describe your business, provide a website URL, or ask questions...",
                        lines=3,
                        max_lines=5
                    )
                    
                    with gr.Row():
                        send_btn = gr.Button("Send", variant="primary", scale=2)
                        clear_btn = gr.Button("New Conversation", variant="secondary", scale=1)
                
                with gr.Column(scale=1):
                    # System information panel
                    gr.Markdown("### System Information")
                    
                    conversation_info = gr.JSON(
                        label="Conversation Status",
                        value={"status": "Ready to start", "step": "Initial"}
                    )
                    
                    gr.Markdown("### Quick Actions")
                    
                    with gr.Column():
                        example_business = gr.Button("Example: SaaS Company", size="sm")
                        example_ecommerce = gr.Button("Example: E-commerce", size="sm")
                        example_consulting = gr.Button("Example: Consulting", size="sm")
            
            # Example business descriptions
            examples = {
                "saas": "We're a B2B SaaS company that provides project management tools for remote teams. Our current customers are mostly mid-size tech companies (50-500 employees) with distributed workforces. We help teams collaborate better and track project progress in real-time.",
                "ecommerce": "We run an e-commerce platform that helps small retailers create online stores. Our ideal customers are brick-and-mortar stores looking to expand online, typically with 5-50 employees. We provide inventory management, payment processing, and marketing tools.",
                "consulting": "We're a digital marketing consulting firm specializing in SEO and content marketing for SaaS companies. Our target clients are B2B SaaS startups and scale-ups with $1M-$50M ARR who need help with organic growth and lead generation."
            }
            
            # Define interaction functions
            async def process_message_stream_async(message, history):
                """Process user message with streaming."""
                if not message.strip():
                    yield history, ""
                    return
                
                try:
                    # Start new conversation if none exists
                    if not web_interface.current_conversation_id:
                        await web_interface.start_new_conversation()
                    
                    # Stream responses using the new streaming method
                    async for updated_history, status, table_data, table_visible in web_interface.process_message_stream(
                        message=message,
                        history=history,
                        agent_type="Main Workflow",  # Use main workflow for full system
                        attachments=None
                    ):
                        # Update conversation info
                        conversation = web_interface.orchestrator.conversations.get(web_interface.current_conversation_id)
                        if conversation:
                            info = {
                                "conversation_id": web_interface.current_conversation_id[:8] + "...",
                                "step": conversation.current_step.value,
                                "messages": len(conversation.messages),
                                "timestamp": conversation.updated_at.isoformat()
                            }
                            # Note: We can't update conversation_info in streaming mode without additional work
                        
                        # Yield the updated history
                        yield updated_history, ""
                    
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    error_response = f"❌ Error: {str(e)}. Please try again or start a new conversation."
                    history.append((message, error_response))
                    yield history, ""
            
            def process_message_stream_sync(message, history):
                """Synchronous wrapper for streaming message processing."""
                # Create an event loop if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        raise RuntimeError("Event loop is closed")
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Run the async generator
                async_gen = process_message_stream_async(message, history)
                
                # Yield from the async generator
                while True:
                    try:
                        result = loop.run_until_complete(async_gen.__anext__())
                        yield result
                    except StopAsyncIteration:
                        break
                    except Exception as e:
                        logger.error(f"Streaming error: {str(e)}")
                        raise
            
            async def clear_conversation_async():
                """Clear conversation asynchronously."""
                web_interface.current_conversation_id = None
                web_interface.conversation_history = []
                await web_interface.start_new_conversation()
                
                info = {
                    "status": "New conversation started",
                    "step": "Initial",
                    "conversation_id": web_interface.current_conversation_id[:8] + "..."
                }
                
                return [], info
            
            def clear_conversation_sync():
                """Synchronous wrapper for clearing conversation."""
                return asyncio.run(clear_conversation_async())
            
            def set_example(example_type):
                """Set example business description."""
                return examples.get(example_type, "")
            
            # Event handlers - now with streaming!
            send_btn.click(
                process_message_stream_sync,
                inputs=[msg, chatbot],
                outputs=[chatbot, msg]
            )
            
            msg.submit(
                process_message_stream_sync,
                inputs=[msg, chatbot],
                outputs=[chatbot, msg]
            )
            
            clear_btn.click(
                clear_conversation_sync,
                outputs=[chatbot, conversation_info]
            )
            
            # Example buttons
            example_business.click(lambda: set_example("saas"), outputs=[msg])
            example_ecommerce.click(lambda: set_example("ecommerce"), outputs=[msg])
            example_consulting.click(lambda: set_example("consulting"), outputs=[msg])
            
            # Footer
            gr.Markdown("""
            ---
            **System Status**: All integrations active | **Data Sources**: HorizonDataWave, Exa AI, Firecrawl  
            **Privacy**: Conversations are not permanently stored | **Support**: Built with Google ADK
            """)
    
    return app


def main():
    """Main entry point with FastAPI mounting."""
    logger.info("Starting ADK Multi-Agent Sales Lead Generation System")
    
    # Validate environment
    required_env_vars = ["GOOGLE_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing required environment variables: {missing_vars}")
        logger.info("Continuing startup - secrets may be provided by Cloud Run")
    
    try:
        # Import FastAPI and uvicorn
        from fastapi import FastAPI
        import uvicorn
        import gradio as gr
        
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
            return {"message": "ADK Sales System - Use /gradio for the UI"}
        
        # Create Gradio app
        gradio_app = create_gradio_app()
        
        # Mount Gradio app on the FastAPI app
        app = gr.mount_gradio_app(fastapi_app, gradio_app, path="/gradio")
        
        # Run with uvicorn
        logger.info(f"Starting FastAPI server on {get_host()}:{get_port()}")
        uvicorn.run(
            app,
            host=get_host(),
            port=get_port(),
            log_level="info"
        )
        
    except ImportError as e:
        logger.error(f"Failed to import required components: {e}")
        logger.info("Falling back to basic HTTP server")
        
        # Fallback to simple HTTP server
        import http.server
        import socketserver
        import json
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"status": "healthy", "service": "adk-sales-system", "mode": "fallback"}
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    html = """
                    <h1>🎯 ADK Sales System</h1>
                    <p>System is in fallback mode. Check logs for details.</p>
                    <p>Missing dependencies - check logs.</p>
                    """
                    self.wfile.write(html.encode())
        
        with socketserver.TCPServer(("", get_port()), Handler) as httpd:
            logger.info(f"Serving fallback on port {get_port()}")
            httpd.serve_forever()
            
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()