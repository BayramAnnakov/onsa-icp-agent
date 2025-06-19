"""Test Research Agent functionality."""

import os
import sys
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from agents.research_agent import ResearchAgent
from models import Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager, CacheConfig


class TestResearchAgent:
    """Test suite for Research Agent."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config.load_from_file("config.yaml")
    
    @pytest.fixture
    def cache_manager(self):
        """Create test cache manager."""
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        return CacheManager(cache_config)
    
    @pytest.fixture
    def research_agent(self, config, cache_manager):
        """Create Research agent for testing."""
        return ResearchAgent(config=config, cache_manager=cache_manager)
    
    def test_agent_initialization(self, research_agent):
        """Test Research agent initialization."""
        assert research_agent.agent_name == "Research Agent"
        assert "Fetches and analyzes web content" in research_agent.agent_description
        assert research_agent.web_scraping_enabled is True
        assert research_agent.firecrawl_client is None  # Not initialized yet
    
    def test_get_capabilities(self, research_agent):
        """Test Research agent capabilities."""
        capabilities = research_agent.get_capabilities()
        
        expected_capabilities = [
            "crawl_website",
            "analyze_linkedin_profile",
            "analyze_company_page",
            "extract_document_insights",
            "competitive_analysis",
            "industry_research",
            "customer_example_analysis"
        ]
        
        for capability in expected_capabilities:
            assert capability in capabilities
    
    @pytest.mark.asyncio
    async def test_crawl_website(self, research_agent):
        """Test website crawling functionality."""
        url = "https://example.com"
        crawl_params = {
            "max_pages": 5,
            "max_depth": 2,
            "include_patterns": ["/about", "/products"],
            "exclude_patterns": ["/blog"]
        }
        
        # Mock Firecrawl client
        mock_firecrawl = MagicMock()
        mock_firecrawl.crawl_website = AsyncMock(return_value={
            "start_url": url,
            "pages": [
                {
                    "url": "https://example.com",
                    "title": "Example Corp",
                    "content": "Example Corp is a leading technology company...",
                    "metadata": {"description": "Technology solutions provider"}
                },
                {
                    "url": "https://example.com/about",
                    "title": "About Us",
                    "content": "Founded in 2020, Example Corp serves enterprise clients...",
                    "metadata": {"description": "About Example Corp"}
                }
            ],
            "total_pages": 2,
            "crawl_completed_at": "2024-01-15T10:00:00Z"
        })
        
        research_agent.firecrawl_client = mock_firecrawl
        
        result = await research_agent.crawl_website(url, crawl_params)
        
        # Verify crawl results
        assert "pages" in result
        assert len(result["pages"]) == 2
        assert result["start_url"] == url
        assert result["total_pages"] == 2
        
        # Verify Firecrawl was called correctly
        mock_firecrawl.crawl_website.assert_called_once_with(
            start_url=url,
            max_pages=5,
            max_depth=2,
            include_patterns=["/about", "/products"],
            exclude_patterns=["/blog"]
        )
    
    @pytest.mark.asyncio
    async def test_analyze_linkedin_profile(self, research_agent):
        """Test LinkedIn profile analysis."""
        linkedin_url = "https://www.linkedin.com/in/johndoe"
        
        # Mock scraped content
        mock_profile_content = {
            "url": linkedin_url,
            "title": "John Doe - CTO at TechCorp",
            "content": """
            John Doe
            Chief Technology Officer at TechCorp
            San Francisco Bay Area
            
            Experience:
            CTO at TechCorp (2020-Present)
            - Leading engineering team of 50+ developers
            - Scaling platform to serve 1M+ users
            
            VP Engineering at StartupCorp (2018-2020)
            - Built engineering team from 5 to 30 people
            - Implemented DevOps practices
            
            Education:
            MS Computer Science, Stanford University
            """,
            "metadata": {"description": "CTO with 10+ years experience"}
        }
        
        with patch.object(research_agent, '_scrape_url') as mock_scrape:
            mock_scrape.return_value = mock_profile_content
            
            with patch.object(research_agent, 'generate_with_gemini') as mock_gemini:
                mock_gemini.return_value = json.dumps({
                    "name": "John Doe",
                    "current_title": "Chief Technology Officer",
                    "current_company": "TechCorp",
                    "location": "San Francisco Bay Area",
                    "experience_years": 10,
                    "education": ["MS Computer Science, Stanford University"],
                    "key_skills": ["Engineering Leadership", "Team Scaling", "DevOps"],
                    "profile_summary": "Experienced CTO with strong background in scaling engineering teams",
                    "decision_maker_indicators": [
                        "C-level executive",
                        "Leads 50+ person team",
                        "Platform scaling experience"
                    ],
                    "icp_fit_signals": {
                        "company_size": "Medium to Large (50+ engineers)",
                        "seniority": "C-level",
                        "technical_focus": "High",
                        "growth_stage": "Scaling"
                    }
                })
                
                analysis = await research_agent.analyze_linkedin_profile(linkedin_url)
                
                # Verify analysis results
                assert analysis["name"] == "John Doe"
                assert analysis["current_title"] == "Chief Technology Officer"
                assert analysis["current_company"] == "TechCorp"
                assert analysis["experience_years"] == 10
                assert "decision_maker_indicators" in analysis
                assert "icp_fit_signals" in analysis
                assert len(analysis["key_skills"]) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_company_page(self, research_agent):
        """Test company page analysis."""
        company_url = "https://techcorp.com"
        
        mock_company_content = {
            "url": company_url,
            "title": "TechCorp - Enterprise Software Solutions",
            "content": """
            TechCorp
            Enterprise Software Solutions
            
            About Us:
            TechCorp provides cloud-based software solutions for Fortune 500 companies.
            Founded in 2015, we serve over 500 enterprise clients worldwide.
            
            Our team of 200+ employees is headquartered in San Francisco.
            
            Products:
            - Enterprise Analytics Platform
            - Cloud Infrastructure Management
            - AI-Powered Business Intelligence
            
            Customers:
            - Fortune 500 companies
            - Technology leaders
            - Global enterprises
            """,
            "metadata": {
                "description": "Enterprise software solutions for Fortune 500 companies",
                "keywords": ["enterprise", "software", "cloud", "analytics"]
            }
        }
        
        with patch.object(research_agent, '_scrape_url') as mock_scrape:
            mock_scrape.return_value = mock_company_content
            
            with patch.object(research_agent, 'generate_with_gemini') as mock_gemini:
                mock_gemini.return_value = json.dumps({
                    "company_name": "TechCorp",
                    "industry": "Enterprise Software",
                    "company_size": "200+ employees",
                    "founded_year": 2015,
                    "headquarters": "San Francisco",
                    "customer_base": "Fortune 500 companies",
                    "products_services": [
                        "Enterprise Analytics Platform",
                        "Cloud Infrastructure Management",
                        "AI-Powered Business Intelligence"
                    ],
                    "target_market": "Fortune 500 companies, Global enterprises",
                    "business_model": "B2B SaaS",
                    "key_differentiators": [
                        "Fortune 500 focus",
                        "AI-powered solutions",
                        "Cloud-native platform"
                    ],
                    "icp_signals": {
                        "company_size": "Enterprise (Fortune 500)",
                        "industry_focus": "Technology, Enterprise",
                        "decision_makers": "C-level, IT leadership",
                        "budget_indicators": "Enterprise-level investments"
                    }
                })
                
                analysis = await research_agent.analyze_company_page(company_url)
                
                # Verify company analysis
                assert analysis["company_name"] == "TechCorp"
                assert analysis["industry"] == "Enterprise Software"
                assert analysis["company_size"] == "200+ employees"
                assert analysis["founded_year"] == 2015
                assert "products_services" in analysis
                assert "key_differentiators" in analysis
                assert "icp_signals" in analysis
                assert len(analysis["products_services"]) == 3
    
    @pytest.mark.asyncio
    async def test_competitive_analysis(self, research_agent):
        """Test competitive analysis functionality."""
        competitor_urls = [
            "https://competitor1.com",
            "https://competitor2.com",
            "https://competitor3.com"
        ]
        
        analysis_focus = "pricing_and_features"
        
        # Mock Firecrawl client for competitive analysis
        mock_firecrawl = MagicMock()
        mock_firecrawl.analyze_competitor_websites = AsyncMock(return_value={
            "competitor_analyses": {
                "https://competitor1.com": {
                    "scraped_data": {
                        "title": "Competitor 1 - Software Solutions",
                        "content": "Competitor 1 offers enterprise software starting at $50/user/month..."
                    },
                    "analysis": {
                        "pricing_signals": ["$50/user/month", "Enterprise plans available"],
                        "feature_mentions": ["Analytics", "Reporting", "API Access"]
                    }
                },
                "https://competitor2.com": {
                    "scraped_data": {
                        "title": "Competitor 2 - Business Platform",
                        "content": "Our platform includes advanced analytics and starts at $100/month..."
                    },
                    "analysis": {
                        "pricing_signals": ["$100/month", "Advanced analytics included"],
                        "feature_mentions": ["Advanced analytics", "Custom dashboards", "Integrations"]
                    }
                }
            },
            "comparative_insights": {
                "pricing_comparison": {
                    "pricing_range": "$50-$100 per user/month",
                    "common_models": "Per-user subscription"
                },
                "feature_comparison": {
                    "common_features": ["Analytics", "Reporting", "API Access"],
                    "differentiators": ["Advanced analytics", "Custom dashboards"]
                }
            },
            "analysis_focus": analysis_focus,
            "analyzed_count": 2
        })
        
        research_agent.firecrawl_client = mock_firecrawl
        
        result = await research_agent.competitive_analysis(competitor_urls, analysis_focus)
        
        # Verify competitive analysis results
        assert "competitor_analyses" in result
        assert "comparative_insights" in result
        assert result["analysis_focus"] == analysis_focus
        assert result["analyzed_count"] == 2
        
        # Verify specific competitor data
        comp1_analysis = result["competitor_analyses"]["https://competitor1.com"]
        assert "pricing_signals" in comp1_analysis["analysis"]
        assert "feature_mentions" in comp1_analysis["analysis"]
        
        # Verify comparative insights
        assert "pricing_comparison" in result["comparative_insights"]
        assert "feature_comparison" in result["comparative_insights"]
    
    @pytest.mark.asyncio
    async def test_industry_research(self, research_agent):
        """Test industry research functionality."""
        industry = "Enterprise Software"
        research_focus = "market_trends_and_growth"
        
        with patch.object(research_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "industry": industry,
                "research_focus": research_focus,
                "market_insights": {
                    "market_size": "$400B globally",
                    "growth_rate": "12% annually",
                    "key_trends": [
                        "AI integration in enterprise software",
                        "Shift to cloud-native solutions",
                        "Increased focus on data security"
                    ],
                    "market_drivers": [
                        "Digital transformation initiatives",
                        "Remote work adoption",
                        "Need for operational efficiency"
                    ]
                },
                "competitive_landscape": {
                    "market_leaders": ["Microsoft", "Salesforce", "Oracle"],
                    "emerging_players": ["Startup A", "Startup B"],
                    "market_concentration": "Fragmented with established leaders"
                },
                "customer_segments": [
                    {
                        "segment": "Large Enterprise",
                        "characteristics": "500+ employees, complex needs",
                        "pain_points": ["Integration complexity", "Scale requirements"]
                    },
                    {
                        "segment": "Mid-Market",
                        "characteristics": "50-500 employees, growth-focused",
                        "pain_points": ["Cost efficiency", "Rapid scaling"]
                    }
                ],
                "opportunities": [
                    "AI-powered automation solutions",
                    "Industry-specific vertical solutions",
                    "SMB market expansion"
                ]
            })
            
            research = await research_agent.industry_research(industry, research_focus)
            
            # Verify industry research results
            assert research["industry"] == industry
            assert research["research_focus"] == research_focus
            assert "market_insights" in research
            assert "competitive_landscape" in research
            assert "customer_segments" in research
            assert "opportunities" in research
            
            # Verify market insights
            market_insights = research["market_insights"]
            assert "market_size" in market_insights
            assert "growth_rate" in market_insights
            assert len(market_insights["key_trends"]) > 0
            
            # Verify customer segments
            assert len(research["customer_segments"]) == 2
            assert research["customer_segments"][0]["segment"] == "Large Enterprise"
    
    @pytest.mark.asyncio
    async def test_extract_document_insights(self, research_agent):
        """Test document insight extraction."""
        documents = [
            {
                "type": "case_study",
                "title": "TechCorp Success Story",
                "content": "TechCorp increased their operational efficiency by 40% after implementing our platform. The 500-person engineering team saw immediate benefits...",
                "metadata": {"source": "company_website", "date": "2024-01-01"}
            },
            {
                "type": "whitepaper",
                "title": "Enterprise Software Trends 2024",
                "content": "Our survey of 200 enterprise CTOs reveals that 85% are prioritizing AI integration in their software stack...",
                "metadata": {"source": "industry_report", "date": "2024-02-01"}
            }
        ]
        
        with patch.object(research_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "document_insights": [
                    {
                        "document_title": "TechCorp Success Story",
                        "document_type": "case_study",
                        "key_insights": [
                            "40% efficiency improvement achieved",
                            "500-person engineering team benefited",
                            "Immediate implementation benefits"
                        ],
                        "customer_profile": {
                            "company_size": "Large (500+ employees)",
                            "department": "Engineering",
                            "use_case": "Operational efficiency"
                        },
                        "value_propositions": [
                            "Operational efficiency improvement",
                            "Fast implementation",
                            "Scalable for large teams"
                        ]
                    },
                    {
                        "document_title": "Enterprise Software Trends 2024",
                        "document_type": "whitepaper",
                        "key_insights": [
                            "85% of CTOs prioritize AI integration",
                            "Survey covers 200 enterprise CTOs",
                            "AI is top enterprise software trend"
                        ],
                        "market_intelligence": {
                            "target_persona": "Enterprise CTOs",
                            "priority_features": "AI integration",
                            "market_trend": "AI adoption in enterprise"
                        }
                    }
                ],
                "consolidated_insights": {
                    "ideal_customer_indicators": [
                        "Large engineering teams (500+ people)",
                        "Enterprise CTOs as decision makers",
                        "Focus on operational efficiency",
                        "Interest in AI-powered solutions"
                    ],
                    "value_proposition_themes": [
                        "Operational efficiency",
                        "AI integration",
                        "Scalability for large teams"
                    ]
                }
            })
            
            insights = await research_agent.extract_document_insights(documents)
            
            # Verify document insights
            assert "document_insights" in insights
            assert "consolidated_insights" in insights
            assert len(insights["document_insights"]) == 2
            
            # Verify first document insight
            first_insight = insights["document_insights"][0]
            assert first_insight["document_title"] == "TechCorp Success Story"
            assert "customer_profile" in first_insight
            assert "value_propositions" in first_insight
            
            # Verify consolidated insights
            consolidated = insights["consolidated_insights"]
            assert "ideal_customer_indicators" in consolidated
            assert "value_proposition_themes" in consolidated
    
    @pytest.mark.asyncio
    async def test_a2a_message_handling(self, research_agent):
        """Test A2A protocol message handling."""
        from agents.base_agent import A2AMessage
        
        # Test website analysis request via A2A
        message = A2AMessage(
            id="msg-research-001",
            sender_agent="icp-agent",
            recipient_agent="research-agent",
            message_type="analyze_website_request",
            content={
                "url": "https://example.com",
                "analysis_type": "company_analysis"
            }
        )
        
        with patch.object(research_agent, 'analyze_company_page') as mock_analyze:
            mock_analyze.return_value = {
                "company_name": "Example Corp",
                "industry": "Technology",
                "company_size": "100+ employees"
            }
            
            response = await research_agent.handle_a2a_message(message)
            
            assert response.success is True
            assert "analysis_result" in response.data
            mock_analyze.assert_called_once_with("https://example.com")
    
    @pytest.mark.asyncio
    async def test_url_validation(self, research_agent):
        """Test URL validation functionality."""
        # Test valid URLs
        valid_urls = [
            "https://example.com",
            "https://www.linkedin.com/in/johndoe",
            "https://company.com/about"
        ]
        
        for url in valid_urls:
            assert research_agent._is_valid_url(url) is True
        
        # Test invalid URLs
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "javascript:alert('xss')",
            ""
        ]
        
        for url in invalid_urls:
            assert research_agent._is_valid_url(url) is False
    
    @pytest.mark.asyncio
    async def test_conversation_management(self, research_agent):
        """Test conversation and query processing."""
        query = "Analyze the website https://example.com and extract insights for our ICP"
        
        with patch.object(research_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = "I'll analyze the website https://example.com for you. Let me extract relevant insights..."
            
            conversation = await research_agent.process_query(query)
            
            assert isinstance(conversation, Conversation)
            assert len(conversation.messages) >= 2
            assert conversation.messages[0].role == MessageRole.USER
            assert conversation.messages[0].content == query
            assert conversation.messages[-1].role == MessageRole.ASSISTANT


def run_research_agent_tests():
    """Run Research Agent tests."""
    print("🔍 Testing Research Agent")
    print("=" * 50)
    
    try:
        # Test basic initialization
        config = Config.load_from_file("config.yaml")
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        cache_manager = CacheManager(cache_config)
        
        agent = ResearchAgent(config=config, cache_manager=cache_manager)
        print("✅ Research Agent initialization successful")
        print(f"Agent name: {agent.agent_name}")
        print(f"Capabilities: {len(agent.get_capabilities())}")
        print(f"Web scraping enabled: {agent.web_scraping_enabled}")
        
        # Test capabilities
        capabilities = agent.get_capabilities()
        print(f"✅ Agent capabilities: {capabilities}")
        
        # Test URL validation
        valid_url = "https://example.com"
        invalid_url = "not-a-url"
        assert agent._is_valid_url(valid_url) is True
        assert agent._is_valid_url(invalid_url) is False
        print("✅ URL validation working")
        
        print("\n🎉 Research Agent basic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Research Agent test failed: {e}")
        return False


if __name__ == "__main__":
    run_research_agent_tests()