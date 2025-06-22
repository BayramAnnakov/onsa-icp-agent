#!/bin/bash
# Setup SQLite database memory for ADK agents

echo "Setting up SQLite Database Memory for ADK Agents"
echo "=============================================="
echo ""

# Create data directory if it doesn't exist
mkdir -p data

echo "✅ Database directory created: ./data/"
echo ""
echo "To use SQLite database for persistent memory, export these variables:"
echo "-------------------------------------------------------------------"
echo "export USE_DATABASE_MEMORY=true"
echo "export DATABASE_URL=sqlite:///./data/adk_agent_memory.db"
echo ""
echo "Or add to your .env file:"
echo "------------------------"
echo "USE_DATABASE_MEMORY=true"
echo "DATABASE_URL=sqlite:///./data/adk_agent_memory.db"
echo ""
echo "Benefits:"
echo "- ✅ Persistent memory across restarts"
echo "- ✅ No cloud dependencies"  
echo "- ✅ Easy local development"
echo "- ✅ Full ADK compatibility"
echo ""
echo "The database will be created automatically at: ./data/adk_agent_memory.db"