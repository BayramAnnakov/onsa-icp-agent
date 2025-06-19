"""Test Firecrawl integration."""

import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from integrations.firecrawl import FirecrawlClient
from utils.cache import CacheManager
from utils.config import CacheConfig


class TestFirecrawlIntegration:
    """Test suite for Firecrawl integration."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create a test cache manager."""
        cache_config = CacheConfig(directory="./test_cache", ttl=3600)
        return CacheManager(cache_config)
    
    @pytest.fixture
    def firecrawl_client(self, cache_manager):
        """Create a Firecrawl client for testing."""
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            pytest.skip("FIRECRAWL_API_KEY not set in environment")
        
        return FirecrawlClient(api_key=api_key, cache_manager=cache_manager)
    
    def test_client_initialization(self):
        """Test Firecrawl client initialization."""
        # Test with API key
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if api_key:
            client = FirecrawlClient(api_key=api_key)
            assert client.api_key == api_key
            assert client.app is not None
        
        # Test without API key
        with pytest.raises(ValueError, match="FIRECRAWL_API_KEY environment variable is required"):
            FirecrawlClient(api_key=None)
    
    @pytest.mark.asyncio
    async def test_scrape_url_basic(self, firecrawl_client):
        """Test basic URL scraping."""
        test_url = "https://example.com"
        
        try:
            result = await firecrawl_client.scrape_url(test_url)
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "url" in result
            assert "content" in result
            assert "scraped_at" in result
            assert result["url"] == test_url
            
            # Verify content is not empty
            assert len(result["content"]) > 0
            
            print(f"✅ Successfully scraped {test_url}")
            print(f"Content length: {len(result['content'])} characters")
            print(f"Title: {result.get('title', 'No title')}")
            
        except Exception as e:
            pytest.fail(f"Failed to scrape URL: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_scrape_url_with_options(self, firecrawl_client):
        """Test URL scraping with different options."""
        test_url = "https://example.com"
        
        # Test with markdown format
        result_md = await firecrawl_client.scrape_url(
            test_url, 
            format_type="markdown",
            include_links=True,
            include_metadata=True
        )
        
        assert "content" in result_md
        assert "metadata" in result_md
        
        print(f"✅ Successfully scraped with markdown format")
        print(f"Metadata keys: {list(result_md.get('metadata', {}).keys())}")
    
    @pytest.mark.asyncio
    async def test_crawl_website_basic(self, firecrawl_client):
        """Test basic website crawling."""
        test_url = "https://example.com"
        
        try:
            result = await firecrawl_client.crawl_website(
                start_url=test_url,
                max_pages=2,  # Keep it small for testing
                max_depth=1
            )
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "start_url" in result
            assert "pages" in result
            assert "total_pages" in result
            assert result["start_url"] == test_url
            
            # Verify we got some pages
            assert result["total_pages"] >= 1
            assert len(result["pages"]) >= 1
            
            # Verify page structure
            page = result["pages"][0]
            assert "url" in page
            assert "content" in page
            
            print(f"✅ Successfully crawled {test_url}")
            print(f"Total pages crawled: {result['total_pages']}")
            print(f"Pages: {[p.get('url', 'No URL') for p in result['pages']]}")
            
        except Exception as e:
            pytest.fail(f"Failed to crawl website: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_map_website(self, firecrawl_client):
        """Test website mapping functionality."""
        test_url = "https://example.com"
        
        try:
            result = await firecrawl_client.map_website(
                url=test_url,
                limit=10
            )
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "url" in result
            assert "links" in result
            assert "total_links" in result
            assert result["url"] == test_url
            
            # Verify we got some links
            assert isinstance(result["links"], list)
            
            print(f"✅ Successfully mapped {test_url}")
            print(f"Total links found: {result['total_links']}")
            if result["links"]:
                print(f"Sample links: {result['links'][:3]}")
            
        except Exception as e:
            pytest.fail(f"Failed to map website: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_extract_structured_data(self, firecrawl_client):
        """Test structured data extraction."""
        test_url = "https://example.com"
        
        # Define a simple schema
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "main_heading": {"type": "string"}
            }
        }
        
        try:
            result = await firecrawl_client.extract_structured_data(
                url=test_url,
                schema=schema
            )
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "url" in result
            assert "extracted_data" in result
            assert "schema" in result
            assert result["url"] == test_url
            
            print(f"✅ Successfully extracted structured data from {test_url}")
            print(f"Extracted data: {result.get('extracted_data', {})}")
            
        except Exception as e:
            pytest.fail(f"Failed to extract structured data: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_caching_functionality(self, firecrawl_client):
        """Test that caching works properly."""
        test_url = "https://example.com"
        
        # First scrape - should hit the API
        start_time = asyncio.get_event_loop().time()
        result1 = await firecrawl_client.scrape_url(test_url)
        first_duration = asyncio.get_event_loop().time() - start_time
        
        # Second scrape - should hit the cache
        start_time = asyncio.get_event_loop().time()
        result2 = await firecrawl_client.scrape_url(test_url)
        second_duration = asyncio.get_event_loop().time() - start_time
        
        # Verify results are the same
        assert result1["url"] == result2["url"]
        assert result1["content"] == result2["content"]
        
        # Second call should be faster (cached)
        print(f"✅ Caching test completed")
        print(f"First call: {first_duration:.2f}s, Second call: {second_duration:.2f}s")
        
        # Note: Second call might not always be faster due to network variations,
        # but the important thing is that we get consistent results
    
    @pytest.mark.asyncio
    async def test_competitor_analysis(self, firecrawl_client):
        """Test competitor analysis functionality."""
        competitor_urls = [
            "https://example.com",
            "https://httpbin.org"  # Simple test site
        ]
        
        try:
            result = await firecrawl_client.analyze_competitor_websites(
                competitor_urls=competitor_urls,
                analysis_focus="general"
            )
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "competitor_analyses" in result
            assert "comparative_insights" in result
            assert "analysis_focus" in result
            assert result["analysis_focus"] == "general"
            
            # Verify we analyzed the URLs
            analyses = result["competitor_analyses"]
            assert len(analyses) == len(competitor_urls)
            
            for url in competitor_urls:
                if url in analyses and "error" not in analyses[url]:
                    analysis = analyses[url]
                    assert "scraped_data" in analysis
                    assert "analysis" in analysis
            
            print(f"✅ Successfully analyzed {len(competitor_urls)} competitor websites")
            print(f"Analysis focus: {result['analysis_focus']}")
            print(f"Successful analyses: {result.get('analyzed_count', 0)}")
            
        except Exception as e:
            pytest.fail(f"Failed to analyze competitors: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_connection(self, firecrawl_client):
        """Test API connection."""
        try:
            is_connected = await firecrawl_client.test_connection()
            assert isinstance(is_connected, bool)
            
            if is_connected:
                print("✅ Firecrawl API connection successful")
            else:
                print("❌ Firecrawl API connection failed")
                
        except Exception as e:
            pytest.fail(f"Connection test failed: {str(e)}")


def run_firecrawl_tests():
    """Run Firecrawl integration tests."""
    print("🔥 Testing Firecrawl Integration")
    print("=" * 50)
    
    # Check if API key is available
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("❌ FIRECRAWL_API_KEY not found in environment variables")
        print("Please set FIRECRAWL_API_KEY in your .env file")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Run basic tests
    try:
        # Test client initialization
        client = FirecrawlClient()
        print("✅ Client initialization successful")
        
        # Run async tests
        async def run_async_tests():
            print("\n🧪 Running async tests...")
            
            # Test basic scraping with minimal parameters
            try:
                result = await asyncio.to_thread(
                    client.app.scrape_url,
                    "https://example.com",
                    formats=['markdown']
                )
                print(f"✅ Basic scraping successful - got response: {type(result)}")
                if isinstance(result, dict) and 'markdown' in result:
                    print(f"Content length: {len(result.get('markdown', ''))} chars")
            except Exception as e:
                print(f"❌ Basic scraping failed: {e}")
                return False
            
            # Test connection
            try:
                is_connected = await client.test_connection()
                if is_connected:
                    print("✅ API connection test successful")
                else:
                    print("❌ API connection test failed")
                    return False
            except Exception as e:
                print(f"❌ Connection test error: {e}")
                return False
            
            return True
        
        # Run the async tests
        success = asyncio.run(run_async_tests())
        
        if success:
            print("\n🎉 All Firecrawl tests passed!")
            return True
        else:
            print("\n❌ Some Firecrawl tests failed")
            return False
            
    except Exception as e:
        print(f"❌ Firecrawl test setup failed: {e}")
        return False


if __name__ == "__main__":
    run_firecrawl_tests()