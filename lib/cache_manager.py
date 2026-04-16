#!/usr/bin/env python3
"""
Cache Manager - Intelligent caching for expensive operations
"""

import json
import hashlib
import time
import pickle
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import logging


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int
    last_accessed: datetime
    size_bytes: int


class CacheManager:
    """
    Intelligent caching layer for expensive operations

    Features:
    - TTL-based expiration
    - LRU eviction
    - Memory usage limits
    - Persistent cache (optional)
    - Hit/miss tracking
    """

    def __init__(
        self,
        max_size_mb: float = 100.0,
        default_ttl_seconds: int = 300,
        persistent: bool = False,
        cache_dir: str = ".jules/cache",
    ):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl_seconds
        self.persistent = persistent
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger("cache-manager")

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

        # Load persistent cache
        if self.persistent:
            self._load_persistent_cache()

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        # Create deterministic hash
        key_data = {"prefix": prefix, "args": args, "kwargs": sorted(kwargs.items())}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return f"{prefix}:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self.stats["misses"] += 1
                return None

            # Check expiration
            if datetime.now() > entry.expires_at:
                del self._cache[key]
                self.stats["expirations"] += 1
                self.stats["misses"] += 1
                return None

            # Update access metadata
            entry.access_count += 1
            entry.last_accessed = datetime.now()

            self.stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set value in cache"""
        with self._lock:
            ttl = ttl_seconds or self.default_ttl

            # Calculate size
            try:
                size = len(pickle.dumps(value))
            except Exception:
                size = 1024  # Default estimate

            # Check if we need to evict
            current_size = self._get_current_size()
            if current_size + size > self.max_size_bytes:
                self._evict_lru(int(self.max_size_bytes * 0.1))  # Evict 10%

            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=ttl),
                access_count=0,
                last_accessed=datetime.now(),
                size_bytes=size,
            )

            self._cache[key] = entry

            # Persist if enabled
            if self.persistent:
                self._persist_entry(key, entry)

            return True

    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

                # Delete persistent file
                if self.persistent:
                    cache_file = self.cache_dir / f"{key}.cache"
                    if cache_file.exists():
                        cache_file.unlink()

                return True
            return False

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()

            if self.persistent:
                for f in self.cache_dir.glob("*.cache"):
                    f.unlink()

    def get_or_compute(
        self, key: str, compute_func: Callable, ttl_seconds: Optional[int] = None
    ) -> Any:
        """
        Get from cache or compute and store

        This is the primary method for using the cache
        """
        # Try cache first
        value = self.get(key)
        if value is not None:
            return value

        # Compute
        try:
            value = compute_func()
            self.set(key, value, ttl_seconds)
            return value
        except Exception:
            # Return None on computation failure
            return None

    def cached(self, ttl_seconds: Optional[int] = None, key_prefix: str = ""):
        """Decorator for caching function results"""

        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # Generate key
                key = self._generate_key(key_prefix or func.__name__, *args, **kwargs)

                # Try cache
                result = self.get(key)
                if result is not None:
                    return result

                # Compute and cache
                result = func(*args, **kwargs)
                self.set(key, result, ttl_seconds)
                return result

            wrapper._cache_manager = self
            return wrapper

        return decorator

    def _get_current_size(self) -> int:
        """Get current cache size in bytes"""
        return sum(e.size_bytes for e in self._cache.values())

    def _evict_lru(self, bytes_to_free: int):
        """Evict least recently used entries"""
        if not self._cache:
            return

        # Sort by last accessed
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].last_accessed)

        freed = 0
        for key, entry in sorted_entries:
            if freed >= bytes_to_free:
                break

            del self._cache[key]
            freed += entry.size_bytes
            self.stats["evictions"] += 1

            # Delete persistent file
            if self.persistent:
                cache_file = self.cache_dir / f"{key}.cache"
                if cache_file.exists():
                    cache_file.unlink()

    def _persist_entry(self, key: str, entry: CacheEntry):
        """Persist cache entry to disk"""
        try:
            cache_file = self.cache_dir / f"{key}.cache"
            with open(cache_file, "wb") as f:
                pickle.dump(entry, f)
        except Exception as e:
            self.logger.warning(f"Failed to persist cache entry: {e}")

    def _load_persistent_cache(self):
        """Load persistent cache from disk"""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        entry = pickle.load(f)

                    # Check if expired
                    if datetime.now() <= entry.expires_at:
                        self._cache[entry.key] = entry
                    else:
                        cache_file.unlink()
                except Exception:
                    # Remove corrupted file
                    cache_file.unlink()
        except Exception as e:
            self.logger.warning(f"Failed to load persistent cache: {e}")

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self._lock:
            total = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total if total > 0 else 0

            return {
                "entries": len(self._cache),
                "size_bytes": self._get_current_size(),
                "size_mb": round(self._get_current_size() / 1024 / 1024, 2),
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "hit_rate": round(hit_rate, 4),
                "evictions": self.stats["evictions"],
                "expirations": self.stats["expirations"],
                "max_size_mb": round(self.max_size_bytes / 1024 / 1024, 2),
            }

    def get_cache_info(self) -> List[Dict]:
        """Get information about cache entries"""
        with self._lock:
            return [
                {
                    "key": k[:50] + "..." if len(k) > 50 else k,
                    "size_kb": round(e.size_bytes / 1024, 2),
                    "access_count": e.access_count,
                    "expires_in": str(e.expires_at - datetime.now()),
                }
                for k, e in self._cache.items()
            ]


# Specialized caches


def create_github_cache() -> CacheManager:
    """Create cache optimized for GitHub API responses"""
    return CacheManager(
        max_size_mb=50,
        default_ttl_seconds=60,  # Short TTL for freshness
        persistent=False,  # Don't persist API responses
    )


def create_validation_cache() -> CacheManager:
    """Create cache for validation results"""
    return CacheManager(
        max_size_mb=20,
        default_ttl_seconds=300,
        persistent=True,  # Persist validation results
    )


def create_pr_info_cache() -> CacheManager:
    """Create cache for PR information"""
    return CacheManager(
        max_size_mb=30,
        default_ttl_seconds=30,  # Very short TTL for PR status
        persistent=False,
    )


if __name__ == "__main__":
    # Test
    cache = CacheManager(max_size_mb=10, default_ttl_seconds=2)

    # Test basic operations
    cache.set("key1", "value1")
    print(f"Get key1: {cache.get('key1')}")
    print(f"Get key2 (miss): {cache.get('key2')}")

    # Test TTL
    time.sleep(3)
    print(f"Get key1 after TTL: {cache.get('key1')}")

    # Test get_or_compute
    def expensive_compute():
        print("Computing...")
        return "computed_value"

    result = cache.get_or_compute("computed", expensive_compute)
    print(f"First call: {result}")

    result = cache.get_or_compute("computed", expensive_compute)
    print(f"Second call (cached): {result}")

    # Test stats
    print(f"\nCache stats: {cache.get_stats()}")
