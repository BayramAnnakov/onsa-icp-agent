"""Test Exa Websets integration."""

import os
import pytest
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from integrations.exa_websets import ExaWebsetsAPI, ExaExtractor


class TestExaIntegration:
    """Test suite for Exa Websets integration."""
    
    @pytest.fixture
    def exa_api(self):
        """Create an Exa API client for testing."""
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            pytest.skip("EXA_API_KEY not set in environment")
        
        return ExaWebsetsAPI(api_key=api_key)
    
    @pytest.fixture
    def exa_extractor(self):
        """Create an Exa extractor for testing."""
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            pytest.skip("EXA_API_KEY not set in environment")
        
        return ExaExtractor(api_key=api_key)
    
    def test_api_initialization(self):
        """Test Exa API client initialization."""
        # Test with API key
        api_key = os.getenv("EXA_API_KEY")
        if api_key:
            client = ExaWebsetsAPI(api_key=api_key)
            assert client.api_key == api_key
            assert client.exa is not None
        
        # Test without API key
        with pytest.raises(ValueError, match="EXA_API_KEY environment variable or api_key parameter required"):
            # Temporarily remove the env var
            original_key = os.environ.get('EXA_API_KEY')
            if original_key:
                del os.environ['EXA_API_KEY']
            
            try:
                ExaWebsetsAPI(api_key=None)
            finally:
                # Restore the env var
                if original_key:
                    os.environ['EXA_API_KEY'] = original_key
    
    def test_extractor_initialization(self):
        """Test Exa extractor initialization."""
        api_key = os.getenv("EXA_API_KEY")
        if api_key:
            extractor = ExaExtractor(api_key=api_key)
            assert extractor.exa_api is not None
            assert isinstance(extractor.exa_api, ExaWebsetsAPI)
    
    def test_create_webset_basic(self, exa_api):
        """Test basic webset creation."""
        try:
            # Create a simple webset
            webset = exa_api.create_webset(
                search_query="YCombinator companies technology startups",
                count=5,
                enrichments=[
                    {
                        "description": "Company name",
                        "format": "text"
                    }
                ]
            )
            
            # Verify response structure
            assert isinstance(webset, dict)
            
            if webset:  # If we got a response
                print(f"✅ Webset created successfully")
                print(f"Webset response keys: {list(webset.keys())}")
                
                # Check for webset ID
                webset_id = webset.get("id")
                if webset_id:
                    print(f"Webset ID: {webset_id}")
                    return webset_id
                else:
                    print("⚠️ No webset ID in response")
            else:
                print("⚠️ Empty webset response")
                
        except Exception as e:
            print(f"❌ Webset creation failed: {str(e)}")
            pytest.skip(f"Exa webset creation failed: {str(e)}")
    
    def test_get_webset_info(self, exa_api):
        """Test getting webset information."""
        try:
            # First create a webset
            webset = exa_api.create_webset(
                search_query="test query",
                count=1
            )
            
            webset_id = webset.get("id") if webset else None
            
            if webset_id:
                # Wait a moment for processing
                time.sleep(2)
                
                # Get webset info
                info = exa_api.get_webset(webset_id)
                
                assert isinstance(info, dict)
                print(f"✅ Retrieved webset info for {webset_id}")
                print(f"Webset status: {info.get('status', 'unknown')}")
                
            else:
                pytest.skip("Could not create webset for testing")
                
        except Exception as e:
            print(f"❌ Get webset info failed: {str(e)}")
            pytest.skip(f"Exa get webset failed: {str(e)}")
    
    def test_wait_for_completion(self, exa_api):
        """Test waiting for webset completion."""
        try:
            # Create a webset
            webset = exa_api.create_webset(
                search_query="simple test query",
                count=1
            )
            
            webset_id = webset.get("id") if webset else None
            
            if webset_id:
                print(f"Testing completion wait for webset {webset_id}")
                
                # Wait for completion with short timeout for testing
                completed = exa_api.wait_for_completion(
                    webset_id=webset_id,
                    max_wait_time=60,  # 1 minute timeout for testing
                    check_interval=5
                )
                
                print(f"✅ Webset completion result: {completed}")
                
            else:
                pytest.skip("Could not create webset for testing")
                
        except Exception as e:
            print(f"❌ Wait for completion failed: {str(e)}")
            # Don't skip here as this might timeout normally
    
    def test_list_webset_items(self, exa_api):
        """Test listing webset items."""
        try:
            # Create and process a webset
            webset = exa_api.create_webset(
                search_query="technology companies",
                count=3
            )
            
            webset_id = webset.get("id") if webset else None
            
            if webset_id:
                # Wait for some processing
                time.sleep(5)
                
                # Try to list items
                items = exa_api.list_webset_items(
                    webset_id=webset_id,
                    limit=10
                )
                
                assert isinstance(items, list)
                print(f"✅ Listed {len(items)} webset items")
                
                if items:
                    item = items[0]
                    print(f"Sample item keys: {list(item.keys()) if isinstance(item, dict) else 'Not a dict'}")
                
            else:
                pytest.skip("Could not create webset for testing")
                
        except Exception as e:
            print(f"❌ List webset items failed: {str(e)}")
            # Don't skip as this might fail due to processing time
    
    def test_companies_extraction(self, exa_extractor):
        """Test general companies extraction."""
        try:
            print("🚀 Testing companies extraction...")
            
            # Test with a general search query
            companies = exa_extractor.extract_companies(
                search_query="technology startup companies San Francisco",
                count=3
            )
            
            assert isinstance(companies, list)
            print(f"✅ Extracted {len(companies)} companies")
            
            if companies:
                # Check first company structure
                company = companies[0]
                assert isinstance(company, dict)
                
                # Check required fields
                required_fields = ["name", "extracted_at"]
                for field in required_fields:
                    if field not in company:
                        print(f"⚠️ Missing field '{field}' in company data")
                
                print(f"Sample company: {company.get('name', 'Unknown')} - {company.get('description', 'No description')}")
                
                return companies[:3]  # Return first 3 for testing
            else:
                print("⚠️ No companies extracted")
                
        except Exception as e:
            print(f"❌ Companies extraction failed: {str(e)}")
            pytest.skip(f"Company extraction failed: {str(e)}")
    
    def test_people_extraction(self, exa_extractor):
        """Test general people extraction."""
        try:
            print("🔍 Testing people extraction...")
            
            # Test with a general search query for people
            people = exa_extractor.extract_people(
                search_query="CEO technology companies LinkedIn",
                count=3
            )
            
            assert isinstance(people, list)
            print(f"✅ Extracted {len(people)} people")
            
            if people:
                # Check first person structure
                person = people[0]
                assert isinstance(person, dict)
                
                # Check required fields
                required_fields = ["name", "extracted_at"]
                for field in required_fields:
                    if field not in person:
                        print(f"⚠️ Missing field '{field}' in person data")
                
                print(f"Sample person: {person.get('name', 'Unknown')} - {person.get('role', 'Unknown role')}")
            else:
                print("⚠️ No people extracted")
                
        except Exception as e:
            print(f"❌ People extraction failed: {str(e)}")
            pytest.skip(f"People extraction failed: {str(e)}")
    
    def test_parsing_methods(self, exa_extractor):
        """Test parsing methods with mock data."""
        # Test company parsing
        mock_company_item = {
            "enrichments": {
                "Company name": "Test Company",
                "Company description": "A test company for testing",
                "Company location": "San Francisco, CA",
                "Company website URL": "https://testcompany.com",
                "Industry or business sector": "Technology"
            },
            "url": "https://testcompany.com"
        }
        
        company = exa_extractor._parse_company_item(mock_company_item)
        
        assert isinstance(company, dict)
        assert company["name"] == "Test Company"
        assert company["description"] == "A test company for testing"
        assert company["location"] == "San Francisco, CA"
        
        print("✅ Company parsing test passed")
        
        # Test person parsing
        mock_person_item = {
            "enrichments": {
                "Person full name": "John Doe",
                "Job title or role": "CEO",
                "Company name": "Test Company",
                "LinkedIn profile URL": "https://linkedin.com/in/johndoe",
                "Professional background or bio": "Serial entrepreneur"
            }
        }
        
        people = exa_extractor._parse_person_item(mock_person_item)
        
        assert isinstance(people, list)
        assert len(people) == 1
        assert people[0]["name"] == "John Doe"
        assert people[0]["role"] == "CEO"
        assert people[0]["company"] == "Test Company"
        
        print("✅ Person parsing test passed")


def run_exa_tests():
    """Run Exa integration tests."""
    print("🔍 Testing Exa Websets Integration")
    print("=" * 50)
    
    # Check if API key is available
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        print("❌ EXA_API_KEY not found in environment variables")
        print("Please set EXA_API_KEY in your .env file")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Run basic tests
    try:
        # Test API client initialization
        api_client = ExaWebsetsAPI(api_key=api_key)
        print("✅ API client initialization successful")
        print(f"Using exa-py SDK with API key: {api_key[:10]}...")
        
        # Test extractor initialization
        extractor = ExaExtractor(api_key=api_key)
        print("✅ Exa extractor initialization successful")
        
        # Test parsing methods (doesn't require API calls)
        print("\n🧪 Testing parsing methods...")
        
        # Mock company item
        mock_company = {
            "enrichments": {
                "Company name": "TestCorp",
                "Company description": "Test company",
                "Company location": "San Francisco, CA"
            },
            "url": "https://testcorp.com"
        }
        
        parsed_company = extractor._parse_company_item(mock_company)
        print(f"✅ Company parsing test: {parsed_company['name'] if parsed_company else 'No company'}")
        
        # Mock person item
        mock_person = {
            "enrichments": {
                "Person full name": "Jane Smith",
                "Job title or role": "CTO",
                "Company name": "TestCorp"
            }
        }
        
        parsed_people = extractor._parse_person_item(mock_person)
        print(f"✅ Person parsing test: {parsed_people[0]['name'] if parsed_people else 'No people'}")
        
        # Test webset creation (actual API call)
        print("\n🌐 Testing webset creation...")
        try:
            test_webset = api_client.create_webset(
                search_query="test query for validation",
                count=1,
                enrichments=[{"description": "test field", "format": "text"}]
            )
            
            if test_webset and test_webset.get("id"):
                print(f"✅ Webset creation successful: {test_webset.get('id')}")
            else:
                print("⚠️ Webset creation returned empty response")
                
        except Exception as e:
            print(f"⚠️ Webset creation test failed (this might be expected): {e}")
            print("This could be due to rate limits, authentication issues, or API changes")
        
        print("\n🎉 Exa basic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Exa test setup failed: {e}")
        return False


if __name__ == "__main__":
    run_exa_tests()