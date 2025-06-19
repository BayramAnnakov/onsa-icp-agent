# Integration Tests

This directory contains comprehensive integration tests for all external API services used in the multi-agent sales lead generation system.

## Test Structure

### Integration Tests (External APIs)
- `test_firecrawl_integration.py` - Tests for Firecrawl SDK integration
- `test_hdw_integration.py` - Tests for HorizonDataWave API integration  
- `test_exa_integration.py` - Tests for Exa Websets API integration
- `run_integration_tests.py` - Main test runner for all integrations

### Agent Tests
- `test_base_agent.py` - Tests for BaseAgent core functionality
- `test_icp_agent.py` - Tests for ICP Agent functionality
- `test_research_agent.py` - Tests for Research Agent functionality  
- `test_prospect_agent.py` - Tests for Prospect Agent functionality
- `test_agents.py` - Main test runner for all agents

## Prerequisites

### Environment Variables
Ensure all API keys are set in your `.env` file:

```bash
GOOGLE_API_KEY=your_google_api_key_here
HDW_API_TOKEN=your_horizon_data_wave_api_token  
EXA_API_KEY=your_exa_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

### Dependencies
Install required packages:

```bash
pip install -r requirements.txt
```

Additional test dependencies:
```bash
pip install pytest pytest-asyncio
```

## Running Tests

### Run All Integration Tests
```bash
cd tests
python run_integration_tests.py
```

### Run Quick Smoke Tests
```bash
python run_integration_tests.py --smoke
```

### Run Specific Service Tests
```bash
# Firecrawl only
python run_integration_tests.py --service firecrawl

# HorizonDataWave only  
python run_integration_tests.py --service hdw

# Exa Websets only
python run_integration_tests.py --service exa
```

### Run Agent Tests
```bash
# All agents
python test_agents.py

# Quick smoke tests
python test_agents.py --smoke

# Specific agent tests
python test_agents.py --agent base
python test_agents.py --agent icp  
python test_agents.py --agent research
python test_agents.py --agent prospect

# Integration test (all agents working together)
python test_agents.py --integration
```

### Run Individual Test Files
```bash
# Run with pytest
pytest test_firecrawl_integration.py -v
pytest test_hdw_integration.py -v
pytest test_exa_integration.py -v

# Run directly
python test_firecrawl_integration.py
python test_hdw_integration.py
python test_exa_integration.py
```

## Test Coverage

### Firecrawl Integration Tests
- ✅ Client initialization and authentication
- ✅ Basic URL scraping with different formats
- ✅ Website crawling with parameters
- ✅ Website mapping for URL discovery
- ✅ Structured data extraction with schemas
- ✅ Competitor analysis workflows
- ✅ Caching functionality validation
- ✅ Connection and API health checks

### HorizonDataWave Integration Tests
- ✅ Client initialization with API token
- ✅ Cache management and configuration
- ✅ LinkedIn company search functionality
- ✅ Header generation and request ID handling
- ✅ Deterministic caching features
- ✅ Rate limiting and API usage tracking
- ✅ Profile search capabilities (if available)

### Exa Websets Integration Tests
- ✅ API client and extractor initialization
- ✅ Webset creation with enrichments
- ✅ Webset status monitoring and completion
- ✅ Webset item listing and retrieval
- ✅ General company extraction workflows
- ✅ People/contact extraction 
- ✅ Data parsing and validation methods

### Agent Tests Coverage

#### BaseAgent Tests
- ✅ Agent initialization and configuration
- ✅ Google Gemini LLM integration
- ✅ A2A protocol message handling
- ✅ FastAPI endpoint creation
- ✅ Cache manager integration
- ✅ Conversation management
- ✅ Abstract method implementation

#### ICP Agent Tests
- ✅ ICP creation from business information
- ✅ ICP refinement with user feedback
- ✅ Source material analysis
- ✅ ICP criteria validation
- ✅ ICP export functionality
- ✅ Storage and retrieval operations
- ✅ A2A communication handling

#### Research Agent Tests
- ✅ Website crawling and content extraction
- ✅ LinkedIn profile analysis
- ✅ Company page analysis
- ✅ Document insight extraction
- ✅ Competitive analysis workflows
- ✅ Industry research capabilities
- ✅ URL validation and security

#### Prospect Agent Tests
- ✅ Prospect search functionality
- ✅ Prospect scoring and ranking
- ✅ Prospect filtering and validation
- ✅ Report generation
- ✅ Search session management
- ✅ Multi-source data integration
- ✅ ICP-based prospect matching

## Expected Behavior

### Success Indicators
- ✅ All clients initialize without errors
- ✅ API keys are properly validated
- ✅ Basic API calls return expected data structures
- ✅ Caching mechanisms work correctly
- ✅ Error handling is graceful

### Common Issues

#### Authentication Errors
```
❌ FIRECRAWL_API_KEY not found in environment variables
❌ HDW_API_TOKEN not found in .env file  
❌ EXA_API_KEY environment variable or api_key parameter required
```
**Solution**: Verify API keys are correctly set in `.env` file

#### Rate Limiting
```
⚠️ Rate limit reached, sleeping for X seconds
⚠️ API request failed due to rate limiting
```
**Solution**: Tests include built-in delays and retry logic

#### Network/API Issues
```
❌ Connection test failed: timeout
⚠️ API service temporarily unavailable
```
**Solution**: These are often temporary - retry after a few minutes

#### Dependency Issues
```
ImportError: firecrawl-py is required. Install with: pip install firecrawl-py
```
**Solution**: Run `pip install -r requirements.txt`

## Test Development

### Adding New Tests
1. Create test methods in the appropriate test file
2. Use proper fixtures for client initialization
3. Include error handling for API failures
4. Add caching validation where applicable
5. Update this README with new test coverage

### Test Guidelines
- Tests should be idempotent (can run multiple times)
- Use small data sets for faster execution
- Include both positive and negative test cases
- Mock external dependencies where appropriate
- Add proper logging and error messages

### Debugging Tests
```bash
# Run with verbose output
python run_integration_tests.py --service firecrawl

# Run single test method
pytest test_firecrawl_integration.py::TestFirecrawlIntegration::test_scrape_url_basic -v -s
```

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  run: |
    cd tests
    python run_integration_tests.py --smoke
  env:
    GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
    HDW_API_TOKEN: ${{ secrets.HDW_API_TOKEN }}
    EXA_API_KEY: ${{ secrets.EXA_API_KEY }}
    FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
```

**Note**: Use smoke tests in CI to avoid extensive API usage and costs.