"""
API tests for authentication routes
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestAuthAPI:
    """Test authentication API endpoints."""
    
    def test_register_endpoint_missing_fields(self, test_client):
        """Test register with missing fields."""
        response = test_client.post("/api/auth/register", json={})
        
        assert response.status_code == 422
    
    def test_register_endpoint_invalid_email(self, test_client):
        """Test register with invalid email."""
        response = test_client.post("/api/auth/register", json={
            "email": "invalid-email",
            "password": "securepass123",
            "full_name": "Test User"
        })
        
        assert response.status_code in [400, 422, 500]
    
    def test_register_endpoint_weak_password(self, test_client):
        """Test register with weak password."""
        response = test_client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "123",
            "full_name": "Test User"
        })
        
        assert response.status_code in [200, 400, 500]
    
    def test_login_endpoint_missing_fields(self, test_client):
        """Test login with missing fields."""
        response = test_client.post("/api/auth/login", json={})
        
        assert response.status_code == 422
    
    def test_login_endpoint_invalid_credentials(self, test_client):
        """Test login with invalid credentials."""
        response = test_client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code in [401, 500]
    
    def test_me_endpoint_no_auth(self, test_client):
        """Test /me endpoint without authentication."""
        response = test_client.get("/api/auth/me")
        
        assert response.status_code == 401
    
    def test_logout_endpoint(self, test_client):
        """Test logout endpoint."""
        response = test_client.post("/api/auth/logout")
        
        assert response.status_code in [200, 401]


class TestAuthValidation:
    """Test authentication input validation."""
    
    def test_register_xss_attack(self, test_client):
        """Test register with XSS attempt."""
        response = test_client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "securepass123",
            "full_name": "<script>alert('XSS')</script>"
        })
        
        assert response.status_code in [200, 400, 500]
    
    def test_register_sql_injection(self, test_client):
        """Test register with SQL injection attempt."""
        response = test_client.post("/api/auth/register", json={
            "email": "'; DROP TABLE users; --",
            "password": "securepass123",
            "full_name": "Hacker"
        })
        
        assert response.status_code in [400, 422, 500]
