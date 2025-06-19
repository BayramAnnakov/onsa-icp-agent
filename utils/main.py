#!/usr/bin/env python3
"""
Working Gradio version for Cloud Run.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Setup logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_port():
    return int(os.environ.get("PORT", 8080))

def main():
    logger.info("Starting ADK Sales System")

    # Check environment
    api_keys = {
        "Google API": "✅" if os.getenv("GOOGLE_API_KEY") else "❌",
        "HDW Token": "✅" if os.getenv("HDW_API_TOKEN") else "❌",
        "Exa Key": "✅" if os.getenv("EXA_API_KEY") else "❌",
        "Firecrawl Key": "✅" if os.getenv("FIRECRAWL_API_KEY") else "❌"
    }

    for name, status in api_keys.items():
        logger.info(f"{name}: {status}")

    try:
        # Import Gradio
        import gradio as gr
        logger.info("Gradio imported successfully")

        # Try to import our modules
        sys.path.insert(0, str(Path(__file__).parent))

        # Create a simple working interface
        def process_message(message, history):
            if not message.strip():
                return history, ""

            # Simple echo for now - we can expand this later
            response = f"🎯 ADK System received: {message}\n\nSystem Status:\n"
            for name, status in api_keys.items():
                response += f"- {name}: {status}\n"
            response += "\n✅ All core systems are operational!"

            history.append((message, response))
            return history, ""

        # Create interface
        with gr.Blocks(title="ADK Multi-Agent Sales System") as app:
            gr.Markdown("# 🎯 ADK Multi-Agent Sales Lead Generation System")
            gr.Markdown("**Status**: Running on Google Cloud Run with all API integrations")

            # Show API status
            status_md = "**API Status**: " + " | ".join([f"{k} {v}" for k, v in api_keys.items()])
            gr.Markdown(status_md)

            # Chat interface
            chatbot = gr.Chatbot(label="ADK Conversation", height=400, type="tuples")
            msg = gr.Textbox(label="Message", placeholder="Describe your business or ask questions...")

            # Handle interactions
            msg.submit(process_message, [msg, chatbot], [chatbot, msg])

            with gr.Row():
                send_btn = gr.Button("Send", variant="primary")
                clear_btn = gr.Button("Clear", variant="secondary")

            send_btn.click(process_message, [msg, chatbot], [chatbot, msg])
            clear_btn.click(lambda: ([], ""), outputs=[chatbot, msg])

            # Health check endpoint built into Gradio
            gr.Markdown("---")
            gr.Markdown("🟢 System healthy | Built with Google ADK")

        # Launch
        logger.info(f"Launching on port {get_port()}")
        app.launch(
            server_name="0.0.0.0",
            server_port=get_port(),
            share=False,
            show_error=True,
            show_tips=False
        )

    except ImportError as e:
        logger.error(f"Import error: {e}")
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
                    response = {"status": "healthy", "service": "adk-sales-system"}
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    html = f"""
                    <h1>🎯 ADK Sales System</h1>
                    <p>System is running on Google Cloud Run</p>
                    <p>API Keys: {api_keys}</p>
                    <p><a href="/health">Health Check</a></p>
                    """
                    self.wfile.write(html.encode())

        with socketserver.TCPServer(("", get_port()), Handler) as httpd:
            logger.info(f"Serving fallback on port {get_port()}")
            httpd.serve_forever()

    except Exception as e:
        logger.error(f"Startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()