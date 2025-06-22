"""Caching utilities for API responses and data."""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from pathlib import Path
import diskcache as dc
import structlog

from .config import CacheConfig


class CacheManager:
    """
    Disk-based cache manager with TTL support.
    
    Provides caching for API responses to prevent redundant calls
    and save costs, especially important for external APIs.
    """
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.logger = structlog.get_logger().bind(component="cache")
        
        # Ensure cache directory exists
        Path(config.directory).mkdir(parents=True, exist_ok=True)
        
        # Initialize disk cache
        self._cache = dc.Cache(
            directory=config.directory,
            size_limit=self._parse_size(config.max_size)
        )
        
        self.logger.info(
            "Cache manager initialized",
            directory=config.directory,
            ttl=config.ttl,
            max_size=config.max_size
        )
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string (e.g., '1GB', '500MB') to bytes."""
        size_str = size_str.upper()
        
        if size_str.endswith('GB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
        elif size_str.endswith('MB'):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith('KB'):
            return int(float(size_str[:-2]) * 1024)
        else:
            return int(size_str)
    
    def _generate_key(self, key: str, namespace: str = "default") -> str:
        """Generate a cache key with namespace."""
        return f"{namespace}:{key}"
    
    def _generate_hash_key(self, data: Dict[str, Any], namespace: str = "default") -> str:
        """Generate a hash-based cache key from data."""
        data_str = json.dumps(data, sort_keys=True)
        hash_key = hashlib.md5(data_str.encode()).hexdigest()
        return self._generate_key(hash_key, namespace)
    
    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._generate_key(key, namespace)
        
        try:
            cached_item = self._cache.get(cache_key)
            
            if cached_item is None:
                return None
            
            # Ensure cached_item is a dictionary
            if not isinstance(cached_item, dict):
                self.logger.warning("Cache item is not a dictionary", key=cache_key, type=type(cached_item).__name__)
                return None
            
            # Check if item has expired
            if 'expires_at' in cached_item:
                expires_at = datetime.fromisoformat(cached_item['expires_at'])
                if datetime.now() > expires_at:
                    self._cache.delete(cache_key)
                    self.logger.debug("Cache item expired", key=cache_key)
                    return None
            
            self.logger.debug("Cache hit", key=cache_key)
            return cached_item.get('data')
            
        except Exception as e:
            self.logger.error("Error getting from cache", key=cache_key, error=str(e))
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = "default"
    ) -> bool:
        """Set value in cache with TTL."""
        cache_key = self._generate_key(key, namespace)
        ttl = ttl or self.config.ttl
        
        try:
            cached_item = {
                'data': value,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(seconds=ttl)).isoformat()
            }
            
            self._cache.set(cache_key, cached_item)
            self.logger.debug("Cache set", key=cache_key, ttl=ttl)
            return True
            
        except Exception as e:
            self.logger.error("Error setting cache", key=cache_key, error=str(e))
            return False
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete value from cache."""
        cache_key = self._generate_key(key, namespace)
        
        try:
            result = self._cache.delete(cache_key)
            self.logger.debug("Cache delete", key=cache_key, found=result)
            return result
            
        except Exception as e:
            self.logger.error("Error deleting from cache", key=cache_key, error=str(e))
            return False
    
    def clear_namespace(self, namespace: str) -> int:
        """Clear all items from a specific namespace."""
        count = 0
        prefix = f"{namespace}:"
        
        try:
            for key in list(self._cache):
                if key.startswith(prefix):
                    self._cache.delete(key)
                    count += 1
            
            self.logger.info("Cleared cache namespace", namespace=namespace, count=count)
            return count
            
        except Exception as e:
            self.logger.error("Error clearing namespace", namespace=namespace, error=str(e))
            return 0
    
    def clear_all(self) -> bool:
        """Clear all cache items."""
        try:
            self._cache.clear()
            self.logger.info("Cleared all cache")
            return True
            
        except Exception as e:
            self.logger.error("Error clearing all cache", error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            return {
                'size': len(self._cache),
                'volume': self._cache.volume(),
                'directory': str(self._cache.directory),
                'hit_count': getattr(self._cache, 'hit_count', 0),
                'miss_count': getattr(self._cache, 'miss_count', 0)
            }
        except Exception as e:
            self.logger.error("Error getting cache stats", error=str(e))
            return {}
    
    def cache_api_response(
        self,
        api_name: str,
        endpoint: str,
        params: Dict[str, Any],
        response: Any,
        ttl: Optional[int] = None
    ) -> str:
        """Cache an API response with a generated key."""
        cache_data = {
            'api_name': api_name,
            'endpoint': endpoint,
            'params': params
        }
        
        cache_key = self._generate_hash_key(cache_data, f"api_{api_name}")
        self.set(cache_key, response, ttl, f"api_{api_name}")
        
        return cache_key
    
    def get_cached_api_response(
        self,
        api_name: str,
        endpoint: str,
        params: Dict[str, Any]
    ) -> Optional[Any]:
        """Get cached API response."""
        cache_data = {
            'api_name': api_name,
            'endpoint': endpoint,
            'params': params
        }
        
        cache_key = self._generate_hash_key(cache_data, f"api_{api_name}")
        return self.get(cache_key, f"api_{api_name}")
    
    def cache_gemini_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]],
        response: str,
        ttl: Optional[int] = None
    ) -> str:
        """Cache a Gemini AI response."""
        cache_data = {
            'prompt': prompt,
            'context': context or {}
        }
        
        cache_key = self._generate_hash_key(cache_data, "gemini")
        self.set(cache_key, response, ttl, "gemini")
        
        return cache_key
    
    def get_cached_gemini_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Get cached Gemini AI response."""
        cache_data = {
            'prompt': prompt,
            'context': context or {}
        }
        
        cache_key = self._generate_hash_key(cache_data, "gemini")
        return self.get(cache_key, "gemini")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cache.close()