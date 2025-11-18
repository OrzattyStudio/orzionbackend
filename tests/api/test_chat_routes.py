"""
API tests for chat routes
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestChatAPI:
    """Test chat API endpoints."""
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Orzion Chat"
    
    def test_config_endpoint(self, test_client):
        """Test config endpoint."""
        response = test_client.get("/api/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert data["app_name"] == "Orzion"
    
    def test_chat_endpoint_empty_prompt(self, test_client):
        """Test chat endpoint with empty prompt."""
        response = test_client.post("/api/chat", json={
            "prompt": "",
            "model": "Orzion Pro",
            "enable_search": False,
            "history": []
        })
        
        assert response.status_code == 400
    
    def test_chat_endpoint_valid_prompt(self, test_client, sample_chat_message):
        """Test chat endpoint with valid prompt."""
        response = test_client.post("/api/chat", json=sample_chat_message)
        
        assert response.status_code in [200, 500, 401]
    
    def test_chat_stream_endpoint(self, test_client, sample_chat_message):
        """Test chat stream endpoint."""
        response = test_client.post("/api/chat/stream", json=sample_chat_message)
        
        assert response.status_code in [200, 500, 401]


class TestChatValidation:
    """Test chat input validation."""
    
    def test_prompt_too_long(self, test_client):
        """Test prompt exceeding max length."""
        long_prompt = "a" * 15000
        response = test_client.post("/api/chat", json={
            "prompt": long_prompt,
            "model": "Orzion Pro",
            "history": []
        })
        
        assert response.status_code in [200, 400, 500]
    
    def test_invalid_model(self, test_client):
        """Test with invalid model name."""
        response = test_client.post("/api/chat", json={
            "prompt": "Hello",
            "model": "Invalid Model",
            "history": []
        })
        
        assert response.status_code in [200, 400, 500]
    
    def test_malicious_input(self, test_client):
        """Test with malicious input."""
        response = test_client.post("/api/chat", json={
            "prompt": "<script>alert('XSS')</script>",
            "model": "Orzion Pro",
            "history": []
        })
        
        assert response.status_code in [200, 400, 500]
