import pytest
import sys
import os
from httpx import AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from app import app
from services.limit_service import RateLimitService, rate_limiter
from services.llm_service import LLMService


class TestSecurity:
    """Integration tests for security features."""
    
    @pytest.mark.asyncio
    async def test_security_headers_present(self, async_client):
        """Test that security headers are present in responses."""
        response = await async_client.get("/")
        
        assert response.status_code == 200
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        
        assert "Referrer-Policy" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "Permissions-Policy" in response.headers
    
    @pytest.mark.asyncio
    async def test_csp_header_configuration(self, async_client):
        """Test that Content Security Policy header is properly configured."""
        response = await async_client.get("/")
        
        csp = response.headers.get("Content-Security-Policy", "")
        
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_security_info(self, async_client):
        """Test that health endpoint returns security-related information."""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "config_ok" in data
        assert "database_ok" in data
        assert "circuit_breakers" in data
    
    @pytest.mark.asyncio
    async def test_rate_limiting_functionality(self):
        """Test that rate limiting works correctly."""
        user_id = "test_user_123"
        model = "Orzion Pro"
        
        limiter = RateLimitService()
        
        allowed, message = await limiter.check_rate_limit(user_id, model)
        assert allowed is True
        assert message is None
        
        for i in range(limiter.limits[model]["requests_per_hour"]):
            allowed, message = await limiter.check_rate_limit(user_id, model)
        
        allowed, message = await limiter.check_rate_limit(user_id, model)
        assert allowed is False
        assert message is not None
        assert "limit exceeded" in message.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limit_different_users(self):
        """Test that rate limits are per-user."""
        limiter = RateLimitService()
        user1 = "user_1"
        user2 = "user_2"
        model = "Orzion Mini"
        
        allowed1, _ = await limiter.check_rate_limit(user1, model)
        allowed2, _ = await limiter.check_rate_limit(user2, model)
        
        assert allowed1 is True
        assert allowed2 is True
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker opens after threshold failures."""
        from services.llm_service import CircuitBreaker
        
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        
        assert breaker.can_attempt() is True
        assert breaker.is_open is False
        
        breaker.record_failure()
        assert breaker.can_attempt() is True
        
        breaker.record_failure()
        assert breaker.can_attempt() is True
        
        breaker.record_failure()
        assert breaker.is_open is True
        assert breaker.can_attempt() is False
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovers after timeout."""
        from services.llm_service import CircuitBreaker
        from datetime import datetime, timedelta
        
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
        
        breaker.record_failure()
        breaker.record_failure()
        
        assert breaker.is_open is True
        
        breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=1)
        
        assert breaker.can_attempt() is True
        assert breaker.is_open is False
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_success_resets(self):
        """Test circuit breaker resets on success."""
        from services.llm_service import CircuitBreaker
        
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        
        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.is_open is False
    
    @pytest.mark.asyncio
    async def test_xss_protection_in_responses(self, async_client):
        """Test that responses include XSS protection."""
        response = await async_client.get("/api/config")
        
        assert "X-XSS-Protection" in response.headers
        
        data = response.json()
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_cors_headers_present(self, async_client):
        """Test that CORS headers are present."""
        response = await async_client.get("/api/config")
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_health_check_with_degraded_status(self, async_client):
        """Test health check returns degraded status when components fail."""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] in ["healthy", "degraded"]
        
        if data["status"] == "degraded":
            assert not data["config_ok"] or not data["database_ok"]
