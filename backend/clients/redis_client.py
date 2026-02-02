"""
Redis client for caching, session management, and rate limiting.
Optimized for high-volume usage (10K-100K concurrent users).
"""

import os
import json
import hashlib
from typing import Optional, Any
import redis
from functools import wraps
import time

class RedisClient:
    """Redis client with connection pooling and helper methods."""
    
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.db = int(os.getenv("REDIS_DB", "0"))
        self.password = os.getenv("REDIS_PASSWORD", None) or None
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
        
        # TTL settings
        self.ttl_sessions = int(os.getenv("CACHE_TTL_SESSIONS", "1800"))  # 30 min
        self.ttl_conversations = int(os.getenv("CACHE_TTL_CONVERSATIONS", "600"))  # 10 min
        self.ttl_llm_responses = int(os.getenv("CACHE_TTL_LLM_RESPONSES", "3600"))  # 1 hour
        
        # Rate limiting settings
        self.rate_limit_rpm = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
        self.rate_limit_burst = int(os.getenv("RATE_LIMIT_BURST", "10"))
        
        # Create connection pool
        self.pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            max_connections=self.max_connections,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        
        self.client = redis.Redis(connection_pool=self.pool)
    
    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return self.client.ping()
        except Exception as e:
            print(f"Redis connection error: {e}")
            return False
    
    # ============================================
    # Generic Cache Operations
    # ============================================
    
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        try:
            return self.client.get(key)
        except Exception as e:
            print(f"Redis GET error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        try:
            if ttl:
                return self.client.setex(key, ttl, value)
            else:
                return self.client.set(key, value)
        except Exception as e:
            print(f"Redis SET error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            print(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            print(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    # ============================================
    # Conversation Context Caching
    # ============================================
    
    def cache_conversation(self, conversation_id: int, messages: list) -> bool:
        """Cache conversation messages."""
        key = f"conv:{conversation_id}:messages"
        try:
            value = json.dumps(messages)
            return self.set(key, value, self.ttl_conversations)
        except Exception as e:
            print(f"Error caching conversation {conversation_id}: {e}")
            return False
    
    def get_cached_conversation(self, conversation_id: int) -> Optional[list]:
        """Get cached conversation messages."""
        key = f"conv:{conversation_id}:messages"
        try:
            cached = self.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            print(f"Error retrieving cached conversation {conversation_id}: {e}")
            return None
    
    def invalidate_conversation(self, conversation_id: int) -> bool:
        """Remove conversation from cache."""
        key = f"conv:{conversation_id}:messages"
        return self.delete(key)
    
    # ============================================
    # LLM Response Caching
    # ============================================
    
    def cache_llm_response(self, prompt: str, context: str, response: str) -> bool:
        """Cache LLM response for identical queries."""
        cache_key = self._generate_llm_cache_key(prompt, context)
        key = f"llm:response:{cache_key}"
        try:
            return self.set(key, response, self.ttl_llm_responses)
        except Exception as e:
            print(f"Error caching LLM response: {e}")
            return False
    
    def get_cached_llm_response(self, prompt: str, context: str) -> Optional[str]:
        """Get cached LLM response if available."""
        cache_key = self._generate_llm_cache_key(prompt, context)
        key = f"llm:response:{cache_key}"
        return self.get(key)
    
    def _generate_llm_cache_key(self, prompt: str, context: str) -> str:
        """Generate cache key for LLM response."""
        combined = f"{prompt}:{context}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    # ============================================
    # Rate Limiting
    # ============================================
    
    def check_rate_limit(self, identifier: str, endpoint: str = "api") -> tuple[bool, int]:
        """
        Check if request is within rate limit.
        Returns: (allowed: bool, remaining_requests: int)
        """
        current_minute = int(time.time() // 60)
        key = f"rate:{identifier}:{endpoint}:{current_minute}"
        
        try:
            current_count = self.client.incr(key)
            
            # Set expiry on first request
            if current_count == 1:
                self.client.expire(key, 60)
            
            # Check limit with burst allowance
            limit = self.rate_limit_rpm + self.rate_limit_burst
            allowed = current_count <= limit
            remaining = max(0, limit - current_count)
            
            return allowed, remaining
        except Exception as e:
            print(f"Rate limit check error: {e}")
            # Fail open - allow request if Redis is down
            return True, self.rate_limit_rpm
    
    def get_rate_limit_info(self, identifier: str, endpoint: str = "api") -> dict:
        """Get current rate limit status."""
        current_minute = int(time.time() // 60)
        key = f"rate:{identifier}:{endpoint}:{current_minute}"
        
        try:
            current_count = int(self.client.get(key) or 0)
            limit = self.rate_limit_rpm + self.rate_limit_burst
            
            return {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "used": current_count,
                "reset_in_seconds": 60 - (int(time.time()) % 60)
            }
        except Exception as e:
            print(f"Rate limit info error: {e}")
            return {
                "limit": self.rate_limit_rpm,
                "remaining": self.rate_limit_rpm,
                "used": 0,
                "reset_in_seconds": 60
            }
    
    # ============================================
    # Statistics & Monitoring
    # ============================================
    
    def get_stats(self) -> dict:
        """Get Redis statistics."""
        try:
            info = self.client.info()
            return {
                "connected": True,
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "used_memory": info.get("used_memory_human", "0"),
                "connected_clients": info.get("connected_clients", 0),
                "total_keys": self.client.dbsize(),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            print(f"Error getting Redis stats: {e}")
            return {"connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, info: dict) -> float:
        """Calculate cache hit rate percentage."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
    
    def close(self):
        """Close Redis connection pool."""
        try:
            self.pool.disconnect()
        except Exception as e:
            print(f"Error closing Redis connection: {e}")


# Global Redis client instance
redis_client = RedisClient()


# ============================================
# Decorator for caching function results
# ============================================

def cache_result(ttl: int = 600, key_prefix: str = "func"):
    """
    Decorator to cache function results in Redis.
    
    Usage:
        @cache_result(ttl=3600, key_prefix="user")
        def get_user_data(user_id: int):
            # expensive operation
            return data
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
            
            # Try to get from cache
            cached = redis_client.get(f"cache:{cache_key_hash}")
            if cached:
                try:
                    return json.loads(cached)
                except:
                    pass
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            try:
                redis_client.set(
                    f"cache:{cache_key_hash}",
                    json.dumps(result),
                    ttl
                )
            except:
                pass  # Don't fail if caching fails
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
            
            # Try to get from cache
            cached = redis_client.get(f"cache:{cache_key_hash}")
            if cached:
                try:
                    return json.loads(cached)
                except:
                    pass
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            try:
                redis_client.set(
                    f"cache:{cache_key_hash}",
                    json.dumps(result),
                    ttl
                )
            except:
                pass
            
            return result
        
        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
