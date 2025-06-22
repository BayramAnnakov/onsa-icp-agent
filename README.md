# ICP Agent System - Multi-Agent Pipeline for B2B Prospect Discovery

A sophisticated multi-agent system built with Google ADK (Agent Development Kit) that creates Ideal Customer Profiles (ICPs) and discovers high-quality prospects through multiple data sources.

## 🚀 Features

- **ICP Generation**: AI-powered analysis of companies to create detailed Ideal Customer Profiles
- **Multi-Source Prospect Discovery**: Search across HorizonDataWave (LinkedIn) and Exa networks
- **Intelligent Scoring**: LLM-based prospect scoring with fallback mechanisms
- **Enhanced Search**: Incorporates buying signals, pain points, and company characteristics
- **Caching Strategy**: Efficient API usage with intelligent caching for expensive endpoints
- **Modular Architecture**: Selective tool loading for each agent based on requirements
- **A2A Protocol Support**: Standardized agent-to-agent communication protocol with REST API and WebSocket

## 🏗️ Architecture

### Agents

1. **ICP Agent** (`adk_icp_agent.py`)
   - Creates comprehensive ICPs from company research
   - Uses web scraping and company data analysis
   - Generates HDW-compatible search criteria

2. **Prospect Agent** (`adk_prospect_agent.py`)
   - Searches for prospects matching ICP criteria
   - Integrates multiple data sources (HDW, Exa)
   - Scores and ranks prospects

3. **Research Agent** (`adk_research_agent.py`)
   - Deep web research capabilities
   - Company and market analysis
   - Competitive intelligence gathering

### External Integrations

- **HorizonDataWave (HDW)**: LinkedIn data access for company and people search
- **Exa Websets**: Advanced web search with AI-powered enrichments
- **Firecrawl**: Web scraping and content extraction

## 🛠️ Setup

### Prerequisites

- Python 3.8+
- Google Cloud credentials (for Gemini API)
- API keys for external services

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/onsa-icp-agent.git
cd onsa-icp-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `config.yaml` file in the root directory:

```yaml
gemini:
  api_key: "your-gemini-api-key"
  model: "gemini-2.5-flash"
  temperature: 0.7
  max_output_tokens: 4096

external_apis:
  horizondatawave:
    api_key: "your-hdw-api-key"
    base_url: "https://api.horizondatawave.com/api/v1"
  
  exa:
    api_key: "your-exa-api-key"
  
  firecrawl:
    api_key: "your-firecrawl-api-key"

cache:
  directory: "./cache"
  max_size: "1GB"
  default_ttl: 3600

storage:
  base_path: "./data/json_storage"
  compress_threshold: 1048576
  max_file_size: 104857600

scoring:
  use_llm: true
  fallback_to_rules: true
  model: "gemini-2.5-flash"
```

## 🚦 Usage

### Web Interface (Recommended)

The system includes a Gradio-based web interface for easy interaction:

```bash
# Run the web interface
python web_interface.py
# or
python main.py
```

The interface will be available at: `http://localhost:7860`

#### Web Interface Features:
- **Interactive Chat**: Natural conversation with agents
- **Agent Selection**: Choose between Main Workflow or individual agents
- **File Attachments**: Add URLs for company analysis
- **Session Management**: Save and load conversations
- **Export Results**: Download in Markdown or JSON format
- **Real-time Progress**: See what agents are doing with streaming responses

### A2A Protocol Server

The system now includes an A2A (Agent-to-Agent) protocol server for programmatic access:

```bash
# Start the A2A server
python start_a2a_server.py
```

The A2A server will be available at: `http://localhost:8080`

#### A2A Features:
- **Agent Discovery**: Find available agents and their capabilities
- **OpenAPI Specs**: Auto-generated API documentation for each agent
- **RESTful API**: Standard HTTP endpoints for all agent operations
- **WebSocket Support**: Real-time bidirectional communication
- **Async Task Execution**: Long-running operations with status tracking

#### Example A2A Usage:

```python
# Discover agents
curl -X POST http://localhost:8080/a2a/discovery \
  -H "Content-Type: application/json" \
  -d '{"include_capabilities": true}'

# Execute a capability
curl -X POST http://localhost:8080/agents/{agent_id}/capabilities/search_companies_hdw \
  -H "Content-Type: application/json" \
  -d '{"query": "fintech startups", "limit": 10}'
```

See [A2A Protocol Documentation](docs/A2A_PROTOCOL.md) for detailed information.

### Command Line Usage

For programmatic access or testing:

```bash
python test_full_pipeline_fixed.py
```

This will:
1. Generate an ICP for a target company
2. Search for matching prospects
3. Score and rank prospects
4. Save results to JSON storage

### Creating an ICP

```python
from agents.adk_icp_agent import ADKICPAgent
from utils.config import Config

config = Config()
icp_agent = ADKICPAgent(config)

result = await icp_agent.create_icp_from_research(
    business_info={
        "company": "Example Corp",
        "website": "https://example.com",
        "industry": "SaaS",
        "description": "B2B software company"
    },
    research_depth="comprehensive"
)
```

### Searching for Prospects

```python
from agents.adk_prospect_agent import ADKProspectAgent

prospect_agent = ADKProspectAgent(config)

results = await prospect_agent.search_prospects_multi_source(
    icp_criteria=icp_data,
    search_limit=10,
    sources=["hdw", "exa"],
    location_filter="United States"
)
```

## 📊 Key Improvements (Latest)

### Bug Fixes
- ✅ Fixed ICP generation infinite loop issue
- ✅ Resolved HDW LinkedinSearchUser data model mismatch
- ✅ Added proper timeout handling for long operations

### Enhancements
- 🔍 Enhanced Exa search with buying signals integration
- 💾 Implemented webset caching to reduce API costs
- 🎯 Selective tool loading for improved performance
- 📈 Better prospect scoring with LLM fallback

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Test individual components
python test_fixes.py

# Test tool loading
python test_selective_tools.py

# Test full pipeline
python test_full_pipeline_fixed.py
```

## 📁 Project Structure

```
onsa-icp-agent/
├── agents/                 # Agent implementations
│   ├── adk_base_agent.py   # Base agent with tool management
│   ├── adk_icp_agent.py    # ICP generation agent
│   ├── adk_prospect_agent.py # Prospect discovery agent
│   └── adk_research_agent.py # Research agent
├── integrations/           # External API integrations
│   ├── hdw.py              # HorizonDataWave client
│   ├── exa_websets.py      # Exa websets client
│   └── firecrawl.py        # Firecrawl client
├── models/                 # Data models
│   ├── icp.py              # ICP model
│   ├── prospect.py         # Prospect model
│   └── conversation.py     # Conversation model
├── utils/                  # Utilities
│   ├── config.py           # Configuration management
│   ├── cache.py            # Caching utilities
│   ├── json_storage.py     # JSON storage
│   └── scoring.py          # Scoring utilities
├── data/                   # Data storage
│   └── json_storage/       # JSON file storage
├── cache/                  # Cache directory
├── test_*.py               # Test scripts
├── requirements.txt        # Python dependencies
└── config.yaml             # Configuration file
```

## 🚀 Deployment

### Google Cloud Run

The system is ready for deployment on Google Cloud Run:

```bash
# Build and deploy
gcloud run deploy adk-sales-system \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY,HDW_API_TOKEN=$HDW_API_TOKEN,EXA_API_KEY=$EXA_API_KEY,FIRECRAWL_API_KEY=$FIRECRAWL_API_KEY"
```

See `DEPLOYMENT.md` for detailed deployment instructions.

## 🔒 Security Notes

- Never commit API keys or `config.yaml` to version control
- Use environment variables for sensitive data in production
- The `.gitignore` file excludes sensitive files by default

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google ADK team for the agent development framework
- HorizonDataWave for LinkedIn data access
- Exa for advanced web search capabilities
- Firecrawl for web scraping infrastructure