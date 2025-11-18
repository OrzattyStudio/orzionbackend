"""
Unit tests for LLMService
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from services.llm_service import LLMService


class TestLLMService:
    """Test LLMService functionality."""
    
    def test_get_model_config_pro(self):
        """Test getting Orzion Pro model configuration."""
        config = LLMService.get_model_config("Orzion Pro")
        
        assert config is not None
        assert "url" in config
        assert "key" in config
        assert "model" in config
        assert "model_secondary" in config
    
    def test_get_model_config_turbo(self):
        """Test getting Orzion Turbo model configuration."""
        config = LLMService.get_model_config("Orzion Turbo")
        
        assert config is not None
        assert "url" in config
        assert "model" in config
    
    def test_get_model_config_mini(self):
        """Test getting Orzion Mini model configuration."""
        config = LLMService.get_model_config("Orzion Mini")
        
        assert config is not None
        assert "url" in config
        assert "model" in config
    
    def test_get_model_config_invalid(self):
        """Test getting invalid model configuration defaults to Pro."""
        config = LLMService.get_model_config("Invalid Model")
        
        assert config is not None
        assert config == LLMService.get_model_config("Orzion Pro")
    
    @pytest.mark.asyncio
    async def test_chat_completion_stream_no_key(self):
        """Test stream with missing API key shows error."""
        messages = [{"role": "user", "content": "Hello"}]
        
        chunks = []
        async for chunk in LLMService.get_chat_completion_stream(
            "Orzion Pro", messages, None, None
        ):
            chunks.append(chunk)
            break
        
        assert len(chunks) > 0
