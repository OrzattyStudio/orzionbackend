"""
Unit tests for RateLimitService
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from services.limit_service import RateLimitService


class TestRateLimitService:
    """Test RateLimitService functionality."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        limiter = RateLimitService()
        
        assert limiter.usage_cache == {}
        assert "Orzion Pro" in limiter.limits
        assert "Orzion Turbo" in limiter.limits
        assert "Orzion Mini" in limiter.limits
    
    def test_get_cache_key(self):
        """Test cache key generation."""
        limiter = RateLimitService()
        key = limiter._get_cache_key("user123", "Orzion Pro", "hour")
        
        assert key == "user123:Orzion Pro:hour"
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        """Test rate limit allows valid requests."""
        limiter = RateLimitService()
        allowed, message = await limiter.check_rate_limit("user1", "Orzion Pro")
        
        assert allowed is True
        assert message is None
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_hourly_exceeded(self):
        """Test hourly rate limit enforcement."""
        limiter = RateLimitService()
        user_id = "test_user_hourly"
        model = "Orzion Pro"
        
        hourly_limit = limiter.limits[model]["requests_per_hour"]
        
        for i in range(hourly_limit + 1):
            allowed, message = await limiter.check_rate_limit(user_id, model)
            
            if i < hourly_limit:
                assert allowed is True
            else:
                assert allowed is False
                assert message is not None
                assert "limit exceeded" in message.lower()
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_unknown_model(self):
        """Test unknown model always allowed."""
        limiter = RateLimitService()
        allowed, message = await limiter.check_rate_limit("user2", "Unknown Model")
        
        assert allowed is True
        assert message is None
    
    def test_cleanup_old_entries(self):
        """Test cleanup of expired cache entries."""
        from datetime import datetime, timedelta
        
        limiter = RateLimitService()
        
        limiter.usage_cache["old_key"] = {
            "count": 5,
            "expires_at": datetime.utcnow() - timedelta(hours=2)
        }
        limiter.usage_cache["new_key"] = {
            "count": 3,
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        }
        
        limiter._cleanup_old_entries()
        
        assert "old_key" not in limiter.usage_cache
        assert "new_key" in limiter.usage_cache
