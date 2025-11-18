"""
Unit tests for SecurityMiddleware
"""
import pytest
from unittest.mock import patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from middleware.security_middleware import SecurityMiddleware


class TestSecurityMiddleware:
    """Test SecurityMiddleware functionality."""
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        input_text = "Hello World"
        result = SecurityMiddleware.sanitize_input(input_text)
        assert result == "Hello World"
    
    def test_sanitize_input_xss_attack(self):
        """Test XSS attack prevention."""
        malicious_input = "<script>alert('XSS')</script>"
        result = SecurityMiddleware.sanitize_input(malicious_input)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    def test_sanitize_input_sql_injection(self):
        """Test SQL injection characters are escaped."""
        sql_input = "' OR '1'='1"
        result = SecurityMiddleware.sanitize_input(sql_input)
        assert result is not None
        assert len(result) > 0
    
    def test_sanitize_input_max_length(self):
        """Test max length enforcement."""
        long_input = "a" * 15000
        result = SecurityMiddleware.sanitize_input(long_input, max_length=10000)
        assert len(result) == 10000
    
    def test_sanitize_input_null_bytes(self):
        """Test null byte removal."""
        input_with_null = "Hello\x00World"
        result = SecurityMiddleware.sanitize_input(input_with_null)
        assert "\x00" not in result
        assert "HelloWorld" in result
    
    def test_sanitize_input_empty_string(self):
        """Test empty string handling."""
        result = SecurityMiddleware.sanitize_input("")
        assert result == ""
    
    def test_sanitize_input_none(self):
        """Test None handling."""
        result = SecurityMiddleware.sanitize_input("")
        assert result == ""
    
    def test_sanitize_input_html_entities(self):
        """Test HTML entity escaping."""
        html_input = '<div class="test">Content & more</div>'
        result = SecurityMiddleware.sanitize_input(html_input)
        assert "&lt;div" in result
        assert "&gt;" in result
        assert "&amp;" in result
        assert "class=" in result or "class=&quot;" in result


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_basic(self):
        """Test basic rate limit checking with mock."""
        user_id = 1
        model = "Orzion Pro"
        
        with patch('middleware.security_middleware.LimitService.check_rate_limit') as mock_check:
            mock_check.return_value = (True, None)
            
            allowed, message = await SecurityMiddleware.check_rate_limit(
                user_id, model, max_requests=5, time_window_hours=1
            )
            
            assert allowed is True
            assert message is None
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test rate limit exceeded scenario with mock."""
        from datetime import datetime, timedelta
        user_id = 2
        model = "Orzion Mini"
        
        with patch('middleware.security_middleware.LimitService.check_rate_limit') as mock_check:
            mock_check.return_value = (False, "Límite de requests excedido")
            
            allowed, message = await SecurityMiddleware.check_rate_limit(
                user_id, model, max_requests=5, time_window_hours=1
            )
            
            assert allowed is False
            assert message is not None
            assert "límite" in message.lower() or "limit" in message.lower()
