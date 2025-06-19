"""Test Prospect Agent functionality."""

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

from agents.prospect_agent import ProspectAgent
from models import ICP, ICPCriteria, Prospect, ProspectScore, Company, Person, Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager, CacheConfig


class TestProspectAgent:
    """Test suite for Prospect Agent."""
    
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
    def prospect_agent(self, config, cache_manager):
        """Create Prospect agent for testing."""
        return ProspectAgent(config=config, cache_manager=cache_manager)
    
    @pytest.fixture
    def sample_icp(self):
        """Create sample ICP for testing."""
        return ICP(
            id="test-icp-1",
            name="Mid-Market Technology Companies",
            description="Technology companies seeking project management solutions",
            company_criteria={
                "company_size": ICPCriteria(
                    weight=0.9,
                    target_value="50-500 employees",
                    description="Mid-market companies"
                ),
                "industry": ICPCriteria(
                    weight=0.8,
                    target_value="Technology, Software, SaaS",
                    description="Technology-focused businesses"
                ),
                "revenue": ICPCriteria(
                    weight=0.7,
                    target_value="$5M-$50M",
                    description="Established revenue base"
                )
            },
            person_criteria={
                "job_title": ICPCriteria(
                    weight=0.9,
                    target_value="CTO, VP Engineering, Engineering Manager",
                    description="Technical decision makers"
                ),
                "seniority": ICPCriteria(
                    weight=0.8,
                    target_value="Senior, Director, VP level",
                    description="Senior level with budget authority"
                )
            },
            industries=["Technology", "Software", "SaaS"],
            target_roles=["CTO", "VP Engineering", "Engineering Manager"]
        )
    
    def test_agent_initialization(self, prospect_agent):
        """Test Prospect agent initialization."""
        assert prospect_agent.agent_name == "Prospect Agent"
        assert "Searches, scores, and ranks potential leads" in prospect_agent.agent_description
        assert isinstance(prospect_agent.active_prospects, dict)
        assert isinstance(prospect_agent.search_sessions, dict)
        assert prospect_agent.scorer is not None
        assert prospect_agent.horizondatawave_client is None  # Not initialized yet
        assert prospect_agent.exa_client is None  # Not initialized yet
    
    def test_get_capabilities(self, prospect_agent):
        """Test Prospect agent capabilities."""
        capabilities = prospect_agent.get_capabilities()
        
        expected_capabilities = [
            "search_prospects",
            "score_prospects",
            "rank_prospects",
            "filter_prospects",
            "prospect_insights",
            "search_companies",
            "search_people",
            "generate_prospect_report"
        ]
        
        for capability in expected_capabilities:
            assert capability in capabilities
    
    @pytest.mark.asyncio
    async def test_search_prospects(self, prospect_agent, sample_icp):
        """Test prospect searching functionality."""
        search_params = {
            "count": 10,
            "sources": ["horizondatawave", "exa"],
            "filters": {
                "location": "United States",
                "exclude_companies": ["Excluded Corp"]
            }
        }
        
        # Mock external API clients
        mock_hdw_companies = [
            {
                "name": "TechCorp Solutions",
                "industry": "Software",
                "size": "150 employees",
                "revenue": "$15M",
                "location": "San Francisco, CA",
                "website": "https://techcorp.com"
            },
            {
                "name": "DataFlow Inc",
                "industry": "SaaS",
                "size": "75 employees", 
                "revenue": "$8M",
                "location": "Austin, TX",
                "website": "https://dataflow.com"
            }
        ]
        
        mock_exa_people = [
            {
                "name": "John Smith",
                "role": "CTO",
                "company": "TechCorp Solutions",
                "linkedin_url": "https://linkedin.com/in/johnsmith",
                "bio": "Experienced CTO with 10+ years in enterprise software"
            },
            {
                "name": "Sarah Johnson",
                "role": "VP Engineering",
                "company": "DataFlow Inc",
                "linkedin_url": "https://linkedin.com/in/sarahjohnson",
                "bio": "Engineering leader focused on scaling SaaS platforms"
            }
        ]
        
        with patch.object(prospect_agent, '_search_companies_hdw') as mock_search_companies:
            mock_search_companies.return_value = mock_hdw_companies
            
            with patch.object(prospect_agent, '_search_people_exa') as mock_search_people:
                mock_search_people.return_value = mock_exa_people
                
                prospects = await prospect_agent.search_prospects(sample_icp, search_params)
                
                # Verify prospect search results
                assert isinstance(prospects, list)
                assert len(prospects) > 0
                
                # Check first prospect structure
                first_prospect = prospects[0]
                assert isinstance(first_prospect, Prospect)
                assert first_prospect.company is not None
                assert first_prospect.person is not None
                assert first_prospect.icp_id == sample_icp.id
                
                # Verify prospect was stored
                assert first_prospect.id in prospect_agent.active_prospects
    
    @pytest.mark.asyncio
    async def test_score_prospects(self, prospect_agent, sample_icp):
        """Test prospect scoring functionality."""
        # Create test prospects
        company1 = Company(
            id="comp-1",
            name="TechCorp Solutions",
            industry="Software",
            size="150 employees",
            revenue="$15M",
            location="San Francisco, CA",
            website="https://techcorp.com"
        )
        
        person1 = Person(
            id="person-1",
            name="John Smith",
            job_title="CTO",
            company_id="comp-1",
            linkedin_url="https://linkedin.com/in/johnsmith",
            seniority_level="C-level"
        )
        
        prospect1 = Prospect(
            id="prospect-1",
            company=company1,
            person=person1,
            icp_id=sample_icp.id
        )
        
        company2 = Company(
            id="comp-2",
            name="SmallStartup",
            industry="Technology",
            size="10 employees",
            revenue="$500K",
            location="Remote",
            website="https://smallstartup.com"
        )
        
        person2 = Person(
            id="person-2",
            name="Jane Doe",
            job_title="Software Engineer",
            company_id="comp-2",
            seniority_level="Individual Contributor"
        )
        
        prospect2 = Prospect(
            id="prospect-2",
            company=company2,
            person=person2,
            icp_id=sample_icp.id
        )
        
        prospects = [prospect1, prospect2]
        
        scored_prospects = await prospect_agent.score_prospects(prospects, sample_icp)
        
        # Verify scoring results
        assert len(scored_prospects) == 2
        
        # Verify scores were calculated
        for prospect in scored_prospects:
            assert prospect.score is not None
            assert isinstance(prospect.score, ProspectScore)
            assert 0 <= prospect.score.total_score <= 1.0
            assert prospect.score.company_score is not None
            assert prospect.score.person_score is not None
        
        # Verify better fitting prospect (prospect1) has higher score than prospect2
        prospect1_score = next(p for p in scored_prospects if p.id == "prospect-1").score.total_score
        prospect2_score = next(p for p in scored_prospects if p.id == "prospect-2").score.total_score
        assert prospect1_score > prospect2_score
    
    @pytest.mark.asyncio
    async def test_rank_prospects(self, prospect_agent, sample_icp):
        """Test prospect ranking functionality."""
        # Create prospects with different scores
        prospects = []
        for i in range(5):
            company = Company(
                id=f"comp-{i}",
                name=f"Company {i}",
                industry="Technology",
                size="100 employees"
            )
            
            person = Person(
                id=f"person-{i}",
                name=f"Person {i}",
                job_title="CTO",
                company_id=f"comp-{i}"
            )
            
            prospect = Prospect(
                id=f"prospect-{i}",
                company=company,
                person=person,
                icp_id=sample_icp.id,
                score=ProspectScore(
                    total_score=0.9 - (i * 0.1),  # Decreasing scores
                    company_score=0.8 - (i * 0.1),
                    person_score=0.9 - (i * 0.1),
                    criteria_scores={}
                )
            )
            prospects.append(prospect)
        
        # Test ranking
        ranking_params = {
            "sort_by": "total_score",
            "limit": 3,
            "min_score": 0.6
        }
        
        ranked_prospects = await prospect_agent.rank_prospects(prospects, ranking_params)
        
        # Verify ranking results
        assert len(ranked_prospects) == 3  # Limited to top 3
        
        # Verify prospects are sorted by score (highest first)
        for i in range(len(ranked_prospects) - 1):
            current_score = ranked_prospects[i].score.total_score
            next_score = ranked_prospects[i + 1].score.total_score
            assert current_score >= next_score
        
        # Verify all prospects meet minimum score requirement
        for prospect in ranked_prospects:
            assert prospect.score.total_score >= 0.6
    
    @pytest.mark.asyncio
    async def test_filter_prospects(self, prospect_agent):
        """Test prospect filtering functionality."""
        # Create test prospects with different characteristics
        prospects = [
            Prospect(
                id="prospect-1",
                company=Company(
                    id="comp-1",
                    name="TechCorp",
                    industry="Software",
                    size="200 employees",
                    location="San Francisco, CA"
                ),
                person=Person(
                    id="person-1",
                    name="John Smith",
                    job_title="CTO",
                    company_id="comp-1",
                    seniority_level="C-level"
                ),
                icp_id="icp-1",
                score=ProspectScore(total_score=0.85, company_score=0.8, person_score=0.9, criteria_scores={})
            ),
            Prospect(
                id="prospect-2", 
                company=Company(
                    id="comp-2",
                    name="DataCorp",
                    industry="SaaS",
                    size="50 employees",
                    location="Austin, TX"
                ),
                person=Person(
                    id="person-2",
                    name="Jane Doe",
                    job_title="VP Engineering",
                    company_id="comp-2",
                    seniority_level="VP"
                ),
                icp_id="icp-1",
                score=ProspectScore(total_score=0.75, company_score=0.7, person_score=0.8, criteria_scores={})
            ),
            Prospect(
                id="prospect-3",
                company=Company(
                    id="comp-3",
                    name="SmallCorp",
                    industry="Technology",
                    size="15 employees",
                    location="Remote"
                ),
                person=Person(
                    id="person-3",
                    name="Bob Wilson",
                    job_title="Software Engineer",
                    company_id="comp-3",
                    seniority_level="Individual Contributor"
                ),
                icp_id="icp-1",
                score=ProspectScore(total_score=0.45, company_score=0.4, person_score=0.5, criteria_scores={})
            )
        ]
        
        # Test different filter combinations
        filter_params = {
            "min_score": 0.7,
            "industries": ["Software", "SaaS"],
            "seniority_levels": ["C-level", "VP"],
            "locations": ["San Francisco, CA", "Austin, TX"]
        }
        
        filtered_prospects = await prospect_agent.filter_prospects(prospects, filter_params)
        
        # Verify filtering results
        assert len(filtered_prospects) == 2  # Should exclude prospect-3
        
        # Verify all filtered prospects meet criteria
        for prospect in filtered_prospects:
            assert prospect.score.total_score >= 0.7
            assert prospect.company.industry in ["Software", "SaaS"]
            assert prospect.person.seniority_level in ["C-level", "VP"]
            assert prospect.company.location in ["San Francisco, CA", "Austin, TX"]
    
    @pytest.mark.asyncio
    async def test_generate_prospect_report(self, prospect_agent, sample_icp):
        """Test prospect report generation."""
        # Create sample prospects for report
        prospects = [
            Prospect(
                id="prospect-1",
                company=Company(
                    id="comp-1",
                    name="TechCorp Solutions",
                    industry="Software",
                    size="150 employees"
                ),
                person=Person(
                    id="person-1",
                    name="John Smith",
                    job_title="CTO",
                    company_id="comp-1"
                ),
                icp_id=sample_icp.id,
                score=ProspectScore(total_score=0.85, company_score=0.8, person_score=0.9, criteria_scores={})
            ),
            Prospect(
                id="prospect-2",
                company=Company(
                    id="comp-2",
                    name="DataFlow Inc",
                    industry="SaaS",
                    size="75 employees"
                ),
                person=Person(
                    id="person-2",
                    name="Sarah Johnson",
                    job_title="VP Engineering",
                    company_id="comp-2"
                ),
                icp_id=sample_icp.id,
                score=ProspectScore(total_score=0.75, company_score=0.7, person_score=0.8, criteria_scores={})
            )
        ]
        
        report_params = {
            "include_summary": True,
            "include_individual_scores": True,
            "include_recommendations": True,
            "format": "structured"
        }
        
        with patch.object(prospect_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "report_summary": {
                    "total_prospects": 2,
                    "average_score": 0.8,
                    "top_prospect": "TechCorp Solutions - John Smith",
                    "score_distribution": {
                        "high_quality": 1,
                        "medium_quality": 1,
                        "low_quality": 0
                    }
                },
                "individual_analyses": [
                    {
                        "prospect_id": "prospect-1",
                        "company_name": "TechCorp Solutions",
                        "person_name": "John Smith",
                        "overall_score": 0.85,
                        "strengths": [
                            "Strong technical leadership role",
                            "Company size fits ICP perfectly",
                            "Industry alignment excellent"
                        ],
                        "concerns": [
                            "No recent activity data available"
                        ],
                        "engagement_recommendations": [
                            "Focus on technical challenges in scaling",
                            "Highlight enterprise-grade features"
                        ]
                    }
                ],
                "recommendations": {
                    "immediate_actions": [
                        "Prioritize outreach to TechCorp Solutions",
                        "Prepare technical demo for CTOs"
                    ],
                    "search_refinements": [
                        "Expand search to include VP of Technology roles",
                        "Consider companies in 100-200 employee range"
                    ]
                }
            })
            
            report = await prospect_agent.generate_prospect_report(prospects, sample_icp, report_params)
            
            # Verify report structure
            assert "report_summary" in report
            assert "individual_analyses" in report
            assert "recommendations" in report
            
            # Verify summary data
            summary = report["report_summary"]
            assert summary["total_prospects"] == 2
            assert summary["average_score"] == 0.8
            assert "score_distribution" in summary
            
            # Verify individual analyses
            assert len(report["individual_analyses"]) > 0
            first_analysis = report["individual_analyses"][0]
            assert "strengths" in first_analysis
            assert "concerns" in first_analysis
            assert "engagement_recommendations" in first_analysis
    
    @pytest.mark.asyncio
    async def test_prospect_insights(self, prospect_agent):
        """Test prospect insights generation."""
        prospects = [
            Prospect(
                id="prospect-1",
                company=Company(id="comp-1", name="TechCorp", industry="Software", size="150 employees"),
                person=Person(id="person-1", name="John Smith", job_title="CTO", company_id="comp-1"),
                icp_id="icp-1",
                score=ProspectScore(total_score=0.85, company_score=0.8, person_score=0.9, criteria_scores={})
            )
        ]
        
        with patch.object(prospect_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "quality_insights": {
                    "high_quality_count": 1,
                    "average_score": 0.85,
                    "score_distribution": {"0.8-1.0": 1}
                },
                "industry_patterns": {
                    "Software": {"count": 1, "avg_score": 0.85}
                },
                "role_patterns": {
                    "CTO": {"count": 1, "avg_score": 0.85}
                },
                "recommendations": [
                    "Strong alignment with software industry CTOs",
                    "Consider expanding to similar technical leadership roles"
                ]
            })
            
            insights = await prospect_agent.prospect_insights(prospects)
            
            # Verify insights structure
            assert "quality_insights" in insights
            assert "industry_patterns" in insights
            assert "role_patterns" in insights
            assert "recommendations" in insights
    
    @pytest.mark.asyncio
    async def test_a2a_message_handling(self, prospect_agent, sample_icp):
        """Test A2A protocol message handling."""
        from agents.base_agent import A2AMessage
        
        # Test prospect search request via A2A
        message = A2AMessage(
            id="msg-prospect-001",
            sender_agent="icp-agent",
            recipient_agent="prospect-agent",
            message_type="search_prospects_request",
            content={
                "icp_id": sample_icp.id,
                "search_params": {
                    "count": 5,
                    "sources": ["horizondatawave"]
                }
            }
        )
        
        with patch.object(prospect_agent, 'search_prospects') as mock_search:
            mock_prospects = [
                Prospect(
                    id="mock-prospect-1",
                    company=Company(id="comp-1", name="MockCorp"),
                    person=Person(id="person-1", name="Mock Person"),
                    icp_id=sample_icp.id
                )
            ]
            mock_search.return_value = mock_prospects
            
            response = await prospect_agent.handle_a2a_message(message)
            
            assert response.success is True
            assert "prospects" in response.data
            assert len(response.data["prospects"]) == 1
            mock_search.assert_called_once()
    
    def test_search_session_management(self, prospect_agent):
        """Test search session management."""
        session_id = "test-session-1"
        session_data = {
            "icp_id": "icp-1",
            "search_params": {"count": 10},
            "created_at": "2024-01-15T10:00:00Z",
            "total_prospects_found": 0
        }
        
        # Create session
        prospect_agent.search_sessions[session_id] = session_data
        
        # Test session retrieval
        retrieved_session = prospect_agent.get_search_session(session_id)
        assert retrieved_session is not None
        assert retrieved_session["icp_id"] == "icp-1"
        
        # Test session update
        prospect_agent.update_search_session(session_id, {"total_prospects_found": 15})
        updated_session = prospect_agent.get_search_session(session_id)
        assert updated_session["total_prospects_found"] == 15
        
        # Test non-existent session
        non_existent = prospect_agent.get_search_session("non-existent")
        assert non_existent is None


def run_prospect_agent_tests():
    """Run Prospect Agent tests."""
    print("🎯 Testing Prospect Agent")
    print("=" * 50)
    
    try:
        # Test basic initialization
        config = Config.load_from_file("config.yaml")
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        cache_manager = CacheManager(cache_config)
        
        agent = ProspectAgent(config=config, cache_manager=cache_manager)
        print("✅ Prospect Agent initialization successful")
        print(f"Agent name: {agent.agent_name}")
        print(f"Capabilities: {len(agent.get_capabilities())}")
        print(f"Scorer initialized: {agent.scorer is not None}")
        
        # Test capabilities
        capabilities = agent.get_capabilities()
        print(f"✅ Agent capabilities: {capabilities}")
        
        # Test search session management
        session_id = "test-session"
        session_data = {
            "icp_id": "test-icp",
            "search_params": {"count": 5},
            "created_at": "2024-01-15T10:00:00Z"
        }
        
        agent.search_sessions[session_id] = session_data
        retrieved = agent.get_search_session(session_id)
        assert retrieved is not None
        print("✅ Search session management working")
        
        # Test prospect storage
        from models import Company, Person, Prospect
        
        test_company = Company(
            id="test-company",
            name="Test Company",
            industry="Technology"
        )
        
        test_person = Person(
            first_name="Test",
            last_name="Person", 
            title="CTO"
        )
        
        from models import ProspectScore
        
        test_score = ProspectScore(
            total_score=0.8,
            company_score=0.7,
            person_score=0.9,
            criteria_scores={}
        )
        
        test_prospect = Prospect(
            id="test-prospect",
            company=test_company,
            person=test_person,
            score=test_score,
            source="test_source",
            icp_id="test-icp"
        )
        
        agent.active_prospects[test_prospect.id] = test_prospect
        retrieved_prospect = agent.get_prospect(test_prospect.id)
        assert retrieved_prospect is not None
        print("✅ Prospect storage and retrieval working")
        
        print("\n🎉 Prospect Agent basic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Prospect Agent test failed: {e}")
        return False


if __name__ == "__main__":
    run_prospect_agent_tests()