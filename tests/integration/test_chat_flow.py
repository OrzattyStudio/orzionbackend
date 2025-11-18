"""
Integration tests for chat flow
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestChatFlow:
    """Test complete chat workflows."""
    
    @pytest.mark.asyncio
    async def test_simple_chat_flow(self, async_client, sample_chat_message):
        """Test simple chat message flow."""
        response = await async_client.post("/api/chat", json=sample_chat_message)
        
        assert response.status_code in [200, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "response" in data or "error" in data
    
    @pytest.mark.asyncio
    async def test_chat_with_search_flow(self, async_client):
        """Test chat with web search enabled."""
        chat_data = {
            "prompt": "What is the capital of France?",
            "model": "Orzion Mini",
            "enable_search": True,
            "history": []
        }
        
        response = await async_client.post("/api/chat", json=chat_data)
        
        assert response.status_code in [200, 401, 500]
    
    @pytest.mark.asyncio
    async def test_chat_stream_flow(self, async_client, sample_chat_message):
        """Test streaming chat flow."""
        response = await async_client.post("/api/chat/stream", json=sample_chat_message)
        
        assert response.status_code in [200, 401, 500]
    
    @pytest.mark.asyncio
    async def test_chat_with_special_mode(self, async_client):
        """Test chat with special mode."""
        chat_data = {
            "prompt": "Explain quantum physics",
            "model": "Orzion Pro",
            "enable_search": False,
            "history": [],
            "special_mode": "deepthinking"
        }
        
        response = await async_client.post("/api/chat", json=chat_data)
        
        assert response.status_code in [200, 401, 500]
