#!/usr/bin/env python3
"""
Quick start script for the web interface.
"""

import sys
import subprocess
import os

def check_gradio():
    """Check if gradio is installed."""
    try:
        import gradio
        print(f"✅ Gradio {gradio.__version__} is installed")
        return True
    except ImportError:
        print("❌ Gradio is not installed")
        return False

def install_gradio():
    """Install gradio if not present."""
    print("Installing gradio...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio"])
        print("✅ Gradio installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install gradio")
        return False

def main():
    """Main entry point."""
    print("🎯 ADK Multi-Agent Sales System - Web Interface Launcher")
    print("=" * 50)
    
    # Check environment
    if not os.path.exists(".env"):
        print("⚠️  Warning: .env file not found. Make sure your API keys are configured.")
    
    # Check gradio
    if not check_gradio():
        response = input("\nWould you like to install gradio? (y/n): ")
        if response.lower() == 'y':
            if not install_gradio():
                print("\nPlease install gradio manually: pip install gradio")
                sys.exit(1)
        else:
            print("\nPlease install gradio manually: pip install gradio")
            sys.exit(1)
    
    # Start the web interface
    print("\n🚀 Starting web interface...")
    print("=" * 50)
    
    try:
        subprocess.run([sys.executable, "web_interface.py"])
    except KeyboardInterrupt:
        print("\n\n👋 Web interface stopped")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()