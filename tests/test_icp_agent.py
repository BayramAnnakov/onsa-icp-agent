"""Test ICP Agent functionality."""

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

from agents.icp_agent import ICPAgent
from models import ICP, ICPCriteria, Conversation, MessageRole
from utils.config import Config
from utils.cache import CacheManager, CacheConfig


class TestICPAgent:
    """Test suite for ICP Agent."""
    
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
    def icp_agent(self, config, cache_manager):
        """Create ICP agent for testing."""
        return ICPAgent(config=config, cache_manager=cache_manager)
    
    def test_agent_initialization(self, icp_agent):
        """Test ICP agent initialization."""
        assert icp_agent.agent_name == "ICP Agent"
        assert "Creates and refines Ideal Customer Profiles" in icp_agent.agent_description
        assert isinstance(icp_agent.active_icps, dict)
        assert len(icp_agent.active_icps) == 0
    
    def test_get_capabilities(self, icp_agent):
        """Test ICP agent capabilities."""
        capabilities = icp_agent.get_capabilities()
        
        expected_capabilities = [
            "create_icp_from_business_info",
            "refine_icp_with_feedback", 
            "analyze_source_materials",
            "validate_icp_criteria",
            "export_icp",
            "collaborate_with_research_agent"
        ]
        
        for capability in expected_capabilities:
            assert capability in capabilities
    
    @pytest.mark.asyncio
    async def test_create_icp_from_business_info(self, icp_agent):
        """Test ICP creation from business information."""
        business_info = {
            "business_name": "TechCorp Solutions",
            "business_description": "B2B SaaS platform for project management",
            "target_market": "Technology companies with 50-500 employees",
            "product_description": "Cloud-based project management software with AI features",
            "current_customers": ["Software companies", "Tech startups", "Digital agencies"],
            "geographic_focus": "North America, Europe",
            "budget_range": "$10k-$100k annually"
        }
        
        with patch.object(icp_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "icp_name": "Mid-Market Technology Companies",
                "description": "Technology companies seeking advanced project management solutions",
                "company_criteria": {
                    "company_size": {
                        "weight": 0.9,
                        "target_value": "50-500 employees",
                        "description": "Mid-market companies with structured teams"
                    },
                    "industry": {
                        "weight": 0.8,
                        "target_value": "Technology, Software, Digital Services",
                        "description": "Technology-focused businesses"
                    },
                    "revenue": {
                        "weight": 0.7,
                        "target_value": "$5M-$50M",
                        "description": "Established revenue base for software investments"
                    }
                },
                "person_criteria": {
                    "job_title": {
                        "weight": 0.9,
                        "target_value": "CTO, VP Engineering, Project Manager",
                        "description": "Technical decision makers"
                    },
                    "seniority": {
                        "weight": 0.8,
                        "target_value": "Senior, Director, VP level",
                        "description": "Senior level with budget authority"
                    }
                },
                "industries": ["Technology", "Software", "SaaS"],
                "target_roles": ["CTO", "VP Engineering", "Project Manager", "Head of Operations"]
            })
            
            icp = await icp_agent.create_icp_from_business_info(business_info)
            
            # Verify ICP was created
            assert isinstance(icp, ICP)
            assert icp.name == "Mid-Market Technology Companies"
            assert len(icp.company_criteria) > 0
            assert len(icp.person_criteria) > 0
            assert "Technology" in icp.industries
            assert "CTO" in icp.target_roles
            
            # Verify ICP was stored
            assert icp.id in icp_agent.active_icps
            assert icp_agent.active_icps[icp.id] == icp
    
    @pytest.mark.asyncio
    async def test_refine_icp_with_feedback(self, icp_agent):
        """Test ICP refinement with user feedback."""
        # Create initial ICP
        initial_icp = ICP(
            id="test-icp-1",
            name="Initial ICP",
            description="Test ICP for refinement",
            company_criteria={
                "company_size": ICPCriteria(
                    weight=0.8,
                    target_value="100-1000 employees",
                    description="Mid to large companies"
                )
            },
            person_criteria={},
            industries=["Technology"],
            target_roles=["CTO"]
        )
        
        icp_agent.active_icps[initial_icp.id] = initial_icp
        
        feedback = {
            "feedback_type": "refine_criteria",
            "changes": {
                "company_size": "50-500 employees",
                "add_industry": "Financial Services",
                "add_role": "VP Engineering"
            },
            "reasoning": "Need to focus on smaller companies and expand to fintech"
        }
        
        with patch.object(icp_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "icp_name": "Refined Tech & Fintech ICP",
                "description": "Technology and financial services companies seeking solutions",
                "company_criteria": {
                    "company_size": {
                        "weight": 0.9,
                        "target_value": "50-500 employees",
                        "description": "Mid-market companies"
                    }
                },
                "person_criteria": {
                    "job_title": {
                        "weight": 0.8,
                        "target_value": "CTO, VP Engineering",
                        "description": "Technical leadership"
                    }
                },
                "industries": ["Technology", "Financial Services"],
                "target_roles": ["CTO", "VP Engineering"]
            })
            
            refined_icp = await icp_agent.refine_icp_with_feedback(initial_icp.id, feedback)
            
            # Verify refinement
            assert isinstance(refined_icp, ICP)
            assert refined_icp.name == "Refined Tech & Fintech ICP"
            assert "Financial Services" in refined_icp.industries
            assert "VP Engineering" in refined_icp.target_roles
            
            # Verify feedback was recorded
            assert len(refined_icp.feedback_history) > 0
            assert refined_icp.feedback_history[0]["feedback_type"] == "refine_criteria"
    
    @pytest.mark.asyncio
    async def test_analyze_source_materials(self, icp_agent):
        """Test analysis of source materials for ICP insights."""
        source_materials = [
            {
                "type": "website",
                "url": "https://example.com/customers",
                "content": "Our customers include Fortune 500 technology companies..."
            },
            {
                "type": "case_study",
                "title": "TechCorp Success Story",
                "content": "How TechCorp increased efficiency by 40% using our platform..."
            }
        ]
        
        with patch.object(icp_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = json.dumps({
                "insights": [
                    {
                        "insight_type": "customer_profile",
                        "description": "Primary customers are Fortune 500 technology companies",
                        "confidence": 0.9,
                        "supporting_evidence": "Website customer section mentions Fortune 500 tech companies"
                    },
                    {
                        "insight_type": "value_proposition",
                        "description": "Platform provides significant efficiency improvements",
                        "confidence": 0.8,
                        "supporting_evidence": "Case study shows 40% efficiency increase"
                    }
                ],
                "recommended_criteria": {
                    "company_size": "Large enterprise (Fortune 500)",
                    "industry": "Technology",
                    "pain_points": ["Efficiency", "Process optimization"]
                }
            })
            
            insights = await icp_agent.analyze_source_materials(source_materials)
            
            # Verify insights
            assert "insights" in insights
            assert len(insights["insights"]) == 2
            assert insights["insights"][0]["insight_type"] == "customer_profile"
            assert insights["insights"][0]["confidence"] == 0.9
            assert "recommended_criteria" in insights
    
    @pytest.mark.asyncio
    async def test_validate_icp_criteria(self, icp_agent):
        """Test ICP criteria validation."""
        icp = ICP(
            id="test-icp-validation",
            name="Test ICP",
            description="ICP for validation testing",
            company_criteria={
                "company_size": ICPCriteria(
                    weight=0.8,
                    target_value="100-1000 employees",
                    description="Mid to large companies"
                ),
                "revenue": ICPCriteria(
                    weight=1.2,  # Invalid weight > 1.0
                    target_value="$10M+",
                    description="High revenue companies"
                )
            },
            person_criteria={
                "job_title": ICPCriteria(
                    weight=0.9,
                    target_value="",  # Empty target value
                    description="Senior technical roles"
                )
            },
            industries=[],  # Empty industries list
            target_roles=["CTO", "VP Engineering"]
        )
        
        validation_result = await icp_agent.validate_icp_criteria(icp)
        
        # Verify validation found issues
        assert not validation_result["is_valid"]
        assert len(validation_result["errors"]) > 0
        assert any("weight" in error.lower() for error in validation_result["errors"])
        assert any("target_value" in error.lower() for error in validation_result["errors"])
        assert any("industries" in error.lower() for error in validation_result["errors"])
    
    def test_export_icp(self, icp_agent):
        """Test ICP export functionality."""
        icp = ICP(
            id="test-icp-export",
            name="Export Test ICP",
            description="ICP for export testing",
            company_criteria={
                "company_size": ICPCriteria(
                    weight=0.8,
                    target_value="100-1000 employees",
                    description="Mid to large companies"
                )
            },
            person_criteria={
                "job_title": ICPCriteria(
                    weight=0.9,
                    target_value="CTO, VP Engineering",
                    description="Technical leadership"
                )
            },
            industries=["Technology", "SaaS"],
            target_roles=["CTO", "VP Engineering"]
        )
        
        icp_agent.active_icps[icp.id] = icp
        
        # Test JSON export
        exported_json = icp_agent.export_icp(icp.id, format="json")
        assert isinstance(exported_json, str)
        
        # Verify JSON contains key fields
        import json
        icp_data = json.loads(exported_json)
        assert icp_data["name"] == "Export Test ICP"
        assert "company_criteria" in icp_data
        assert "person_criteria" in icp_data
        assert "industries" in icp_data
        
        # Test dict export
        exported_dict = icp_agent.export_icp(icp.id, format="dict")
        assert isinstance(exported_dict, dict)
        assert exported_dict["name"] == "Export Test ICP"
    
    @pytest.mark.asyncio
    async def test_a2a_message_handling(self, icp_agent):
        """Test A2A protocol message handling."""
        from agents.base_agent import A2AMessage
        
        # Test ICP creation request via A2A
        message = A2AMessage(
            id="msg-001",
            sender_agent="user-interface",
            recipient_agent="icp-agent",
            message_type="create_icp_request",
            content={
                "business_info": {
                    "business_name": "TestCorp",
                    "business_description": "SaaS platform",
                    "target_market": "SMB technology companies"
                }
            }
        )
        
        with patch.object(icp_agent, 'create_icp_from_business_info') as mock_create:
            mock_icp = ICP(
                id="mock-icp-id",
                name="Mock ICP",
                description="Mock ICP for testing",
                company_criteria={},
                person_criteria={},
                industries=["Technology"],
                target_roles=["CTO"]
            )
            mock_create.return_value = mock_icp
            
            response = await icp_agent.handle_a2a_message(message)
            
            assert response.success is True
            assert "data" in response.data
            assert response.data["data"]["icp_id"] == "mock-icp-id"
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conversation_management(self, icp_agent):
        """Test conversation and query processing."""
        query = "Create an ICP for a B2B SaaS company targeting marketing departments"
        
        with patch.object(icp_agent, 'generate_with_gemini') as mock_gemini:
            mock_gemini.return_value = "I'll help you create an ICP for your B2B SaaS company. Based on your description..."
            
            conversation = await icp_agent.process_query(query)
            
            assert isinstance(conversation, Conversation)
            assert len(conversation.messages) >= 2  # User query + agent response
            assert conversation.messages[0].role == MessageRole.USER
            assert conversation.messages[0].content == query
            assert conversation.messages[-1].role == MessageRole.ASSISTANT
    
    def test_icp_storage_and_retrieval(self, icp_agent):
        """Test ICP storage and retrieval methods."""
        icp = ICP(
            id="storage-test-icp",
            name="Storage Test ICP",
            description="ICP for storage testing",
            company_criteria={},
            person_criteria={},
            industries=["Technology"],
            target_roles=["CTO"]
        )
        
        # Test storage
        icp_agent.active_icps[icp.id] = icp
        assert icp.id in icp_agent.active_icps
        
        # Test retrieval
        retrieved_icp = icp_agent.get_icp(icp.id)
        assert retrieved_icp is not None
        assert retrieved_icp.id == icp.id
        assert retrieved_icp.name == icp.name
        
        # Test non-existent ICP
        non_existent = icp_agent.get_icp("non-existent-id")
        assert non_existent is None
        
        # Test list ICPs
        all_icps = icp_agent.list_icps()
        assert isinstance(all_icps, list)
        assert len(all_icps) == 1
        assert all_icps[0].id == icp.id


def run_icp_agent_tests():
    """Run ICP Agent tests."""
    print("🎯 Testing ICP Agent")
    print("=" * 50)
    
    try:
        # Test basic initialization
        config = Config.load_from_file("config.yaml")
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        cache_manager = CacheManager(cache_config)
        
        agent = ICPAgent(config=config, cache_manager=cache_manager)
        print("✅ ICP Agent initialization successful")
        print(f"Agent name: {agent.agent_name}")
        print(f"Capabilities: {len(agent.get_capabilities())}")
        
        # Test capabilities
        capabilities = agent.get_capabilities()
        print(f"✅ Agent capabilities: {capabilities}")
        
        # Test ICP storage
        test_icp = ICP(
            id="test-icp-manual",
            name="Manual Test ICP",
            description="ICP created for manual testing",
            company_criteria={},
            person_criteria={},
            industries=["Technology"],
            target_roles=["CTO"]
        )
        
        agent.active_icps[test_icp.id] = test_icp
        retrieved = agent.get_icp(test_icp.id)
        assert retrieved is not None
        print("✅ ICP storage and retrieval working")
        
        # Test export
        exported = agent.export_icp(test_icp.id, format="dict")
        assert isinstance(exported, dict)
        print("✅ ICP export functionality working")
        
        print("\n🎉 ICP Agent basic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ ICP Agent test failed: {e}")
        return False


if __name__ == "__main__":
    run_icp_agent_tests()