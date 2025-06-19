# Web Interface for ADK Multi-Agent System

A Gradio-based web interface for testing the main workflow and feedback loops of the multi-agent sales lead generation system.

## Features

### 🎯 Main Capabilities
- **Interactive Chat Interface**: Converse with agents naturally
- **Agent Selection**: Choose between Main Workflow or individual agents (ICP, Prospect, Research)
- **File Attachments**: Add URLs for company analysis
- **Session Management**: Save and load conversation sessions
- **Export Results**: Export conversations in Markdown or JSON format

### 📊 Workflow Testing
- **Main Workflow**: Complete end-to-end ICP creation and prospect discovery
- **ICP Agent**: Direct interaction for ICP creation and refinement
- **Prospect Agent**: Test prospect search with existing ICPs
- **Research Agent**: Perform targeted research on companies or topics

### 💾 Session Features
- Auto-save sessions with timestamps
- Load previous sessions to continue work
- Export results for documentation
- Clear conversation history

## Quick Start

### Option 1: Using the launcher script
```bash
python start_web.py
```

### Option 2: Direct launch
```bash
# Install gradio if not already installed
pip install gradio

# Run the web interface
python web_interface.py
```

The interface will be available at: `http://localhost:7860`

## Usage Guide

### 1. Main Workflow Testing
Select "Main Workflow" and follow the conversation:
```
1. Describe your business and ideal customers
2. Attach example company URLs (optional)
3. Review and refine the generated ICP
4. Approve to start prospect search
5. Review discovered prospects
```

### 2. Direct Agent Testing

#### ICP Agent
- Attach company URLs to analyze
- Describe your business context
- Receive detailed ICP analysis

#### Prospect Agent
- Requires an existing ICP (create via Main Workflow first)
- Searches for matching prospects
- Returns scored and ranked results

#### Research Agent
- Enter any research topic
- Receives summarized research with sources
- Great for competitive analysis

### 3. Session Management

#### Saving Sessions
1. Enter a session name
2. Click "Save Session"
3. Session includes full conversation history

#### Loading Sessions
1. Select from dropdown of saved sessions
2. Click "Load Session"
3. Continue where you left off

#### Exporting Results
1. Choose format (Markdown or JSON)
2. Click "Export"
3. Find exported files in `sessions/` directory

## Interface Components

### Left Panel (Main Area)
- **Conversation Display**: Shows full chat history
- **Message Input**: Enter your queries or descriptions
- **Attachments**: Add URLs for analysis
- **Status Bar**: Shows current workflow step and progress

### Right Panel (Controls)
- **Agent Type**: Select interaction mode
- **Session Management**: New/Save/Load operations
- **Export Options**: Download conversation data

## Tips for Testing

### Testing ICP Creation
1. Start with Main Workflow
2. Provide clear business description
3. Attach 2-3 example company URLs
4. Test refinement by requesting changes

### Testing Prospect Search
1. Complete ICP creation first
2. Wait for prospect search to complete
3. Review scoring and ranking
4. Export results for analysis

### Testing Feedback Loops
1. When ICP is presented, request specific changes:
   - "Focus more on enterprise companies"
   - "Add technology stack requirements"
   - "Adjust company size criteria"
2. Observe how the system refines based on feedback

### Testing Research Capabilities
1. Use Research Agent directly
2. Try queries like:
   - "AI startups in healthcare"
   - "B2B SaaS pricing strategies"
   - "Enterprise software trends 2024"

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
   ```bash
   pip install -r requirements.txt
   ```

2. **API Key Errors**: Check `.env` file contains all required keys:
   - `GOOGLE_API_KEY`
   - `HDW_API_TOKEN`
   - `EXA_API_KEY`
   - `FIRECRAWL_API_KEY`

3. **Session Not Found**: Sessions are stored in `sessions/` directory
   - Check directory permissions
   - Ensure write access

4. **Slow Response**: External API calls may take time
   - HDW searches can take 10-30 seconds
   - Prospect scoring involves LLM calls
   - Check API rate limits

## Advanced Usage

### Custom Workflows
Modify `web_interface.py` to add:
- Custom agent interactions
- Additional UI components
- New export formats
- Integration with other tools

### Debugging
- Check console output for detailed logs
- Enable debug mode in `Config`
- Review API response caching

## Architecture Notes

The web interface:
- Wraps existing `ADKAgentOrchestrator`
- Maintains conversation state
- Handles async operations gracefully
- Provides real-time status updates

All agent logic remains in the original implementation, ensuring consistency between CLI and web interfaces.