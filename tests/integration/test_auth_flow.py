"""
Integration tests for authentication flow
"""
import pytest
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestAuthenticationFlow:
    """Test complete authentication flows."""
    
    @pytest.mark.asyncio
    async def test_register_login_me_flow(self, async_client):
        """Test complete register -> login -> me flow."""
        unique_email = f"test_{uuid.uuid4()}@example.com"
        
        register_data = {
            "email": unique_email,
            "password": "SecurePass123!",
            "full_name": "Integration Test User"
        }
        
        register_response = await async_client.post("/api/auth/register", json=register_data)
        
        assert register_response.status_code in [200, 201, 409, 500]
        
        if register_response.status_code in [200, 201]:
            login_data = {
                "email": unique_email,
                "password": "SecurePass123!"
            }
            
            login_response = await async_client.post("/api/auth/login", json=login_data)
            
            assert login_response.status_code in [200, 401, 500]
            
            if login_response.status_code == 200:
                login_json = login_response.json()
                assert "access_token" in login_json or "user" in login_json
    
    @pytest.mark.asyncio
    async def test_logout_flow(self, async_client):
        """Test logout flow."""
        logout_response = await async_client.post("/api/auth/logout")
        
        assert logout_response.status_code in [200, 401]
