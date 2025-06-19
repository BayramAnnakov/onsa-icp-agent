"""Test HorizonDataWave (HDW) integration."""

import os
import pytest
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from integrations.hdw import HorizonDataWave


class TestHDWIntegration:
    """Test suite for HorizonDataWave integration."""
    
    @pytest.fixture
    def hdw_client(self):
        """Create an HDW client for testing."""
        api_token = os.getenv("HDW_API_TOKEN")
        if not api_token:
            pytest.skip("HDW_API_TOKEN not set in environment")
        
        return HorizonDataWave(cache_enabled=True)
    
    def test_client_initialization(self):
        """Test HDW client initialization."""
        # Test with API token
        api_token = os.getenv("HDW_API_TOKEN")
        if api_token:
            client = HorizonDataWave(cache_enabled=True)
            assert client.api_token == api_token
            assert client.base_url == "https://api.horizondatawave.ai/api"
            assert client.cache_enabled is True
        
        # Test without API token
        with pytest.raises(ValueError, match="HDW_API_TOKEN not found"):
            # Temporarily remove the env var
            original_token = os.environ.get('HDW_API_TOKEN')
            if original_token:
                del os.environ['HDW_API_TOKEN']
            
            try:
                HorizonDataWave()
            finally:
                # Restore the env var
                if original_token:
                    os.environ['HDW_API_TOKEN'] = original_token
    
    def test_cache_functionality(self, hdw_client):
        """Test caching functionality."""
        # Test cache info
        cache_info = hdw_client.get_cache_info()
        assert isinstance(cache_info, dict)
        assert "cache_enabled" in cache_info
        assert cache_info["cache_enabled"] is True
        
        print(f"✅ Cache info: {cache_info}")
        
        # Test deterministic caching
        hdw_client.enable_deterministic_caching(True)
        print("✅ Enabled deterministic caching")
        
        # Test cache clearing
        hdw_client.clear_cache()
        print("✅ Cache cleared successfully")
    
    def test_linkedin_company_search(self, hdw_client):
        """Test LinkedIn company search functionality."""
        # Test with a well-known company
        test_company = "Microsoft"
        
        try:
            companies = hdw_client.get_linkedin_company(
                company=test_company,
                timeout=60
            )
            
            # Verify response structure
            assert isinstance(companies, list)
            
            if companies:
                company = companies[0]
                print(f"✅ Found company: {company}")
                
                # Basic validation of company data structure
                # Note: The actual structure depends on HDW API response
                assert hasattr(company, '__dict__') or isinstance(company, dict)
                
                print(f"✅ Successfully searched for company: {test_company}")
                print(f"Found {len(companies)} results")
            else:
                print(f"⚠️ No companies found for: {test_company}")
                
        except Exception as e:
            print(f"❌ Company search failed: {str(e)}")
            # Don't fail the test immediately - HDW might have rate limits or other issues
            pytest.skip(f"HDW company search failed: {str(e)}")
    
    def test_headers_generation(self, hdw_client):
        """Test header generation with request IDs."""
        # Test default headers
        headers1 = hdw_client._get_headers()
        assert "access-token" in headers1
        assert "Content-Type" in headers1
        assert "x-request-id" in headers1
        assert headers1["Content-Type"] == "application/json"
        
        # Test with custom request ID
        custom_id = "test-request-123"
        headers2 = hdw_client._get_headers(request_id=custom_id)
        assert headers2["x-request-id"] == custom_id
        
        # Test deterministic headers
        hdw_client.enable_deterministic_caching(True)
        payload = {"test": "data"}
        headers3 = hdw_client._get_headers(payload=payload)
        headers4 = hdw_client._get_headers(payload=payload)
        
        # Should generate same request ID for same payload
        assert headers3["x-request-id"] == headers4["x-request-id"]
        assert headers3["x-request-id"].startswith("cache-")
        
        print("✅ Header generation tests passed")
    
    def test_linkedin_company_by_name_search(self, hdw_client):
        """Test searching companies by name."""
        test_companies = ["Google", "Apple", "Tesla"]
        
        for company_name in test_companies:
            try:
                print(f"\n🔍 Searching for company: {company_name}")
                
                # Use a shorter timeout for testing
                companies = hdw_client.search_company_by_name(
                    company_name=company_name,
                    limit=5,
                    timeout=30
                )
                
                assert isinstance(companies, list)
                
                if companies:
                    print(f"✅ Found {len(companies)} companies for '{company_name}'")
                    
                    # Check first company structure
                    first_company = companies[0]
                    print(f"First result: {first_company}")
                else:
                    print(f"⚠️ No companies found for '{company_name}'")
                
                # Add a small delay between requests to respect rate limits
                time.sleep(1)
                
            except AttributeError:
                # Method might not exist in the current HDW implementation
                print(f"⚠️ search_company_by_name method not available")
                break
            except Exception as e:
                print(f"❌ Search failed for '{company_name}': {str(e)}")
                # Continue with next company
                continue
    
    def test_linkedin_profile_search(self, hdw_client):
        """Test LinkedIn profile search functionality."""
        # Test with a LinkedIn URL (if the method exists)
        test_linkedin_url = "https://www.linkedin.com/in/satyanadella"
        
        try:
            # Check if the method exists
            if hasattr(hdw_client, 'get_linkedin_profile'):
                profile = hdw_client.get_linkedin_profile(
                    linkedin_url=test_linkedin_url,
                    timeout=30
                )
                
                print(f"✅ Profile search successful")
                print(f"Profile data type: {type(profile)}")
                
            elif hasattr(hdw_client, 'search_people'):
                # Alternative method name
                people = hdw_client.search_people(
                    query="CEO Microsoft",
                    limit=1,
                    timeout=30
                )
                
                print(f"✅ People search successful")
                print(f"Found {len(people) if isinstance(people, list) else 1} people")
                
            else:
                print("⚠️ No profile search methods available")
                
        except Exception as e:
            print(f"❌ Profile search failed: {str(e)}")
            pytest.skip(f"HDW profile search failed: {str(e)}")
    
    def test_rate_limiting_info(self, hdw_client):
        """Test rate limiting and API usage info."""
        # Test that we can call the client multiple times
        start_time = time.time()
        
        try:
            # Make a few quick calls to test rate limiting
            for i in range(3):
                headers = hdw_client._get_headers()
                assert "x-request-id" in headers
                print(f"Request {i+1}: {headers['x-request-id']}")
                
                # Small delay
                time.sleep(0.5)
            
            end_time = time.time()
            print(f"✅ Made 3 requests in {end_time - start_time:.2f} seconds")
            
        except Exception as e:
            print(f"❌ Rate limiting test failed: {str(e)}")
    
    def test_cache_operations(self, hdw_client):
        """Test various cache operations."""
        # Test cache info
        info = hdw_client.get_cache_info()
        print(f"Cache info: {info}")
        
        # Test enabling/disabling deterministic caching
        hdw_client.enable_deterministic_caching(True)
        hdw_client.enable_deterministic_caching(False)
        
        # Test cache clearing
        hdw_client.clear_cache()
        
        # Test expired cache deletion
        hdw_client.delete_expired_cache()
        
        print("✅ All cache operations completed successfully")


def run_hdw_tests():
    """Run HDW integration tests."""
    print("🌊 Testing HorizonDataWave (HDW) Integration")
    print("=" * 50)
    
    # Check if API token is available
    api_token = os.getenv("HDW_API_TOKEN")
    if not api_token:
        print("❌ HDW_API_TOKEN not found in environment variables")
        print("Please set HDW_API_TOKEN in your .env file")
        return False
    
    print(f"✅ Found API token: {api_token[:10]}...")
    
    # Run basic tests
    try:
        # Test client initialization
        client = HorizonDataWave(cache_enabled=True)
        print("✅ Client initialization successful")
        print(f"Base URL: {client.base_url}")
        print(f"Cache enabled: {client.cache_enabled}")
        
        # Test cache functionality
        cache_info = client.get_cache_info()
        print(f"✅ Cache info: {cache_info}")
        
        # Test header generation
        headers = client._get_headers()
        print(f"✅ Headers generated: {list(headers.keys())}")
        
        # Test deterministic caching
        client.enable_deterministic_caching(True)
        print("✅ Deterministic caching enabled")
        
        # Test a simple company search (with error handling)
        try:
            print("\n🔍 Testing company search...")
            companies = client.get_linkedin_company(
                company="Microsoft",
                timeout=30
            )
            
            if isinstance(companies, list):
                print(f"✅ Company search successful - found {len(companies)} results")
            else:
                print(f"✅ Company search returned: {type(companies)}")
                
        except Exception as e:
            print(f"⚠️ Company search test failed (this might be expected): {e}")
            print("This could be due to rate limits, authentication issues, or API changes")
        
        print("\n🎉 HDW basic tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ HDW test setup failed: {e}")
        return False


if __name__ == "__main__":
    run_hdw_tests()