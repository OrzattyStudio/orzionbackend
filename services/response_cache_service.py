"""
Response Cache Service - Caches LLM responses to reduce API calls

Implements in-memory caching with TTL (24 hours default).
Cache key: (user_id, model_name, normalized_prompt)

Cache hits do NOT increment provider quotas.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import hashlib
import json


class ResponseCacheService:
    """
    Service for caching LLM responses.
    
    Features:
    - In-memory storage (dict-based)
    - 24h TTL by default
    - Automatic cache invalidation
    - Normalized prompt keys (lowercase, stripped whitespace)
    """
    
    # In-memory cache storage
    # Format: {cache_key: {"response": str, "expires_at": datetime, "created_at": datetime}}
    _cache: Dict[str, Dict[str, Any]] = {}
    
    # Default TTL: 24 hours
    DEFAULT_TTL_SECONDS = 24 * 60 * 60
    
    @staticmethod
    def _normalize_prompt(prompt: str) -> str:
        """
        Normalize prompt for consistent cache keys.
        
        - Convert to lowercase
        - Strip extra whitespace
        - Remove leading/trailing whitespace
        """
        return " ".join(prompt.lower().strip().split())
    
    @staticmethod
    def _generate_cache_key(user_id: str, model_name: str, messages: list) -> str:
        """
        Generate cache key from user_id, model_name, and messages.
        
        Uses MD5 hash of the normalized conversation to keep keys short.
        """
        # Extract just the user messages (ignore system prompts and assistant messages)
        user_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Handle multimodal content
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    content = " ".join(text_parts)
                user_messages.append(content)
        
        # Normalize and combine all user messages
        normalized = ResponseCacheService._normalize_prompt(" ".join(user_messages))
        
        # Generate hash
        cache_data = f"{user_id}:{model_name}:{normalized}"
        cache_hash = hashlib.md5(cache_data.encode()).hexdigest()
        
        return f"cache_{cache_hash}"
    
    @staticmethod
    def _clean_expired_cache():
        """Remove expired cache entries (automatic cleanup)."""
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, value in ResponseCacheService._cache.items()
            if value.get("expires_at") and value["expires_at"] < now
        ]
        
        for key in expired_keys:
            del ResponseCacheService._cache[key]
        
        if expired_keys:
            print(f"🧹 Cleaned {len(expired_keys)} expired cache entries")
    
    @staticmethod
    async def get_cached_response(
        user_id: str,
        model_name: str,
        messages: list
    ) -> Optional[str]:
        """
        Get cached response if available and not expired.
        
        Returns:
            Cached response text, or None if not found/expired
        """
        # Clean expired entries first
        ResponseCacheService._clean_expired_cache()
        
        cache_key = ResponseCacheService._generate_cache_key(user_id, model_name, messages)
        
        if cache_key in ResponseCacheService._cache:
            cache_entry = ResponseCacheService._cache[cache_key]
            expires_at = cache_entry.get("expires_at")
            
            # Check if expired
            if expires_at and expires_at > datetime.now(timezone.utc):
                print(f"✅ Cache HIT for {model_name} (user: {user_id[:8]}...)")
                return cache_entry.get("response")
            else:
                # Expired, remove from cache
                del ResponseCacheService._cache[cache_key]
                print(f"⏰ Cache EXPIRED for {model_name} (user: {user_id[:8]}...)")
        
        print(f"❌ Cache MISS for {model_name} (user: {user_id[:8]}...)")
        return None
    
    @staticmethod
    async def cache_response(
        user_id: str,
        model_name: str,
        messages: list,
        response: str,
        ttl_seconds: Optional[int] = None
    ):
        """
        Cache a response with TTL.
        
        Args:
            user_id: User ID
            model_name: Model name
            messages: Message list
            response: Response text to cache
            ttl_seconds: Time to live in seconds (default: 24h)
        """
        if ttl_seconds is None:
            ttl_seconds = ResponseCacheService.DEFAULT_TTL_SECONDS
        
        cache_key = ResponseCacheService._generate_cache_key(user_id, model_name, messages)
        now = datetime.now(timezone.utc)
        
        ResponseCacheService._cache[cache_key] = {
            "response": response,
            "created_at": now,
            "expires_at": now + timedelta(seconds=ttl_seconds),
            "user_id": user_id,
            "model_name": model_name
        }
        
        print(f"💾 Cached response for {model_name} (user: {user_id[:8]}..., TTL: {ttl_seconds}s)")
    
    @staticmethod
    def clear_cache():
        """Clear all cached responses."""
        count = len(ResponseCacheService._cache)
        ResponseCacheService._cache.clear()
        print(f"🗑️ Cleared {count} cache entries")
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get cache statistics."""
        # Clean expired first
        ResponseCacheService._clean_expired_cache()
        
        now = datetime.now(timezone.utc)
        total_entries = len(ResponseCacheService._cache)
        
        # Count entries by model
        model_counts = {}
        for entry in ResponseCacheService._cache.values():
            model = entry.get("model_name", "unknown")
            model_counts[model] = model_counts.get(model, 0) + 1
        
        return {
            "total_entries": total_entries,
            "entries_by_model": model_counts,
            "memory_usage_kb": len(str(ResponseCacheService._cache)) / 1024
        }
