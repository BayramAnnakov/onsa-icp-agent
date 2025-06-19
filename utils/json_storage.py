"""JSON storage utility for handling large JSON data."""

import json
import os
import hashlib
import gzip
from typing import Any, Dict, Optional, Union, List
from datetime import datetime
from pathlib import Path
import structlog

logger = structlog.get_logger()


class JSONStorage:
    """
    Utility for storing and retrieving large JSON data.
    
    Features:
    - Automatic compression for large files
    - Hash-based file naming for deduplication
    - Metadata tracking
    - Size limits and validation
    """
    
    def __init__(
        self,
        base_path: str = "./data/json_storage",
        compress_threshold: int = 1024 * 1024,  # 1MB
        max_size: int = 100 * 1024 * 1024,  # 100MB
    ):
        """
        Initialize JSON storage.
        
        Args:
            base_path: Base directory for storing JSON files
            compress_threshold: Size threshold for compression (bytes)
            max_size: Maximum allowed file size (bytes)
        """
        self.base_path = Path(base_path)
        self.compress_threshold = compress_threshold
        self.max_size = max_size
        
        # Create directories
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "data").mkdir(exist_ok=True)
        (self.base_path / "metadata").mkdir(exist_ok=True)
        
        logger.info(
            "JSON storage initialized",
            base_path=str(self.base_path),
            compress_threshold=compress_threshold,
            max_size=max_size
        )
    
    def save(
        self,
        data: Any,
        key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save JSON data to storage.
        
        Args:
            data: Data to save (must be JSON serializable)
            key: Optional key for the data (auto-generated if not provided)
            metadata: Optional metadata to store with the data
            
        Returns:
            Storage key for retrieving the data
        """
        try:
            # Convert data to JSON string
            json_str = json.dumps(data, indent=2, default=self._json_encoder)
            json_bytes = json_str.encode('utf-8')
            
            # Check size
            if len(json_bytes) > self.max_size:
                raise ValueError(f"Data too large: {len(json_bytes)} bytes (max: {self.max_size})")
            
            # Generate key if not provided
            if not key:
                content_hash = hashlib.sha256(json_bytes).hexdigest()[:16]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                key = f"{timestamp}_{content_hash}"
            
            # Determine if compression is needed
            compress = len(json_bytes) > self.compress_threshold
            
            # Save data
            if compress:
                file_path = self.base_path / "data" / f"{key}.json.gz"
                with gzip.open(file_path, 'wb') as f:
                    f.write(json_bytes)
            else:
                file_path = self.base_path / "data" / f"{key}.json"
                with open(file_path, 'w') as f:
                    f.write(json_str)
            
            # Save metadata
            meta = {
                "key": key,
                "size": len(json_bytes),
                "compressed": compress,
                "created_at": datetime.now().isoformat(),
                "content_type": type(data).__name__,
                "custom_metadata": metadata or {}
            }
            
            meta_path = self.base_path / "metadata" / f"{key}.meta.json"
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
            
            logger.info(
                "JSON data saved",
                key=key,
                size=len(json_bytes),
                compressed=compress
            )
            
            return key
            
        except Exception as e:
            logger.error("Error saving JSON data", error=str(e))
            raise
    
    def load(self, key: str) -> Any:
        """
        Load JSON data from storage.
        
        Args:
            key: Storage key
            
        Returns:
            The stored data
        """
        try:
            # Check for compressed version first
            compressed_path = self.base_path / "data" / f"{key}.json.gz"
            uncompressed_path = self.base_path / "data" / f"{key}.json"
            
            if compressed_path.exists():
                with gzip.open(compressed_path, 'rb') as f:
                    json_str = f.read().decode('utf-8')
            elif uncompressed_path.exists():
                with open(uncompressed_path, 'r') as f:
                    json_str = f.read()
            else:
                raise FileNotFoundError(f"No data found for key: {key}")
            
            data = json.loads(json_str)
            
            logger.info("JSON data loaded", key=key)
            return data
            
        except Exception as e:
            logger.error("Error loading JSON data", key=key, error=str(e))
            raise
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a stored JSON."""
        meta_path = self.base_path / "metadata" / f"{key}.meta.json"
        
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                return json.load(f)
        return None
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        compressed_path = self.base_path / "data" / f"{key}.json.gz"
        uncompressed_path = self.base_path / "data" / f"{key}.json"
        return compressed_path.exists() or uncompressed_path.exists()
    
    def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """List all keys in storage."""
        keys = []
        
        for file_path in (self.base_path / "data").glob("*.json*"):
            key = file_path.stem
            if key.endswith('.json'):
                key = key[:-5]  # Remove .json
            
            if pattern is None or pattern in key:
                keys.append(key)
        
        return sorted(keys)
    
    def delete(self, key: str) -> bool:
        """Delete a stored JSON."""
        deleted = False
        
        # Delete data files
        for suffix in ['.json', '.json.gz']:
            file_path = self.base_path / "data" / f"{key}{suffix}"
            if file_path.exists():
                file_path.unlink()
                deleted = True
        
        # Delete metadata
        meta_path = self.base_path / "metadata" / f"{key}.meta.json"
        if meta_path.exists():
            meta_path.unlink()
        
        if deleted:
            logger.info("JSON data deleted", key=key)
        
        return deleted
    
    def get_size(self, key: str) -> Optional[int]:
        """Get the size of stored data."""
        meta = self.get_metadata(key)
        return meta['size'] if meta else None
    
    def cleanup_old(self, days: int = 7) -> int:
        """Clean up old stored JSONs."""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for key in self.list_keys():
            meta = self.get_metadata(key)
            if meta:
                created_at = datetime.fromisoformat(meta['created_at'])
                if created_at < cutoff_date:
                    if self.delete(key):
                        deleted_count += 1
        
        logger.info(
            "Cleaned up old JSON data",
            deleted_count=deleted_count,
            days_old=days
        )
        
        return deleted_count
    
    def _json_encoder(self, obj):
        """Custom JSON encoder for non-serializable objects."""
        # Handle dataclasses
        if hasattr(obj, '__dict__'):
            if hasattr(obj, '__dataclass_fields__'):
                # It's a dataclass
                return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
            elif hasattr(obj, '__dict__') and callable(getattr(obj, '__dict__')):
                # Has custom __dict__ method
                return obj.__dict__()
            else:
                # Regular object
                return obj.__dict__
        
        # Handle datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Handle Path
        if isinstance(obj, Path):
            return str(obj)
        
        # Default
        return str(obj)


# Global instance for convenience
_json_storage = None


def get_json_storage() -> JSONStorage:
    """Get or create global JSON storage instance."""
    global _json_storage
    if _json_storage is None:
        _json_storage = JSONStorage()
    return _json_storage


def save_large_json(data: Any, key: Optional[str] = None, **kwargs) -> str:
    """Convenience function to save large JSON data."""
    return get_json_storage().save(data, key, **kwargs)


def load_large_json(key: str) -> Any:
    """Convenience function to load large JSON data."""
    return get_json_storage().load(key)