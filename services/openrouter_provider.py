"""
Fallback LLM Provider - Handles automatic backup API calls

Extracted from LLMService to provide a clean provider abstraction.
Supports streaming responses and proper error handling.
"""
import httpx
import json
from typing import AsyncGenerator, Dict, List, Any, Optional
from config import config
from services.security_logger import SecurityLogger


class OpenRouterProvider:
    """
    Fallback LLM Provider for automatic backup API calls.
    
    Handles:
    - Streaming responses
    - Error handling
    - Proxy support
    - Multiple model support
    """
    
    # Model configuration mapping
    MODEL_CONFIG = {
        "Orzion Pro": {
            "url": config.ORZION_PRO_URL,
            "key": config.ORZION_PRO_KEY,
            "model": config.ORZION_PRO_MODEL
        },
        "Orzion Turbo": {
            "url": config.ORZION_TURBO_URL,
            "key": config.ORZION_TURBO_KEY,
            "model": config.ORZION_TURBO_MODEL
        },
        "Orzion Mini": {
            "url": config.ORZION_MINI_URL,
            "key": config.ORZION_MINI_KEY,
            "model": config.ORZION_MINI_MODEL
        }
    }
    
    @staticmethod
    def _get_proxy_config() -> Optional[Dict[str, str]]:
        """Get proxy configuration if set in config."""
        proxies = {}
        if config.HTTP_PROXY:
            proxies["http://"] = config.HTTP_PROXY
        if config.HTTPS_PROXY:
            proxies["https://"] = config.HTTPS_PROXY
        return proxies if proxies else None
    
    @staticmethod
    async def chat_completion_stream(
        model_name: str,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 8000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from OpenRouter.
        
        Args:
            model_name: Orzion model name (e.g., "Orzion Pro")
            messages: OpenAI-style messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
        
        Yields:
            Text chunks from the response
        """
        model_config = OpenRouterProvider.MODEL_CONFIG.get(model_name)
        if not model_config:
            yield f"Error: Unknown model {model_name}"
            return
        
        api_key = model_config.get("key")
        if not api_key:
            yield f"Error: OpenRouter API key not configured for {model_name}"
            return
        
        url = model_config.get("url")
        model = model_config.get("model")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://orzionai.com",
            "X-Title": "Orzion AI"
        }
        
        correlation_id = SecurityLogger.generate_correlation_id()
        
        try:
            # Create httpx client (proxy support optional)
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line or line.startswith(":"):
                            continue
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                            
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content")
                                    
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenRouter API error: {e.response.status_code}"
            
            SecurityLogger.log_api_error(
                api_name=f"openrouter_{model_name}",
                error_message=error_msg,
                status_code=e.response.status_code,
                correlation_id=correlation_id
            )
            
            yield f"\n\n[Error: {error_msg}]"
        
        except Exception as e:
            error_msg = f"OpenRouter error: {str(e)}"
            SecurityLogger.log_api_error(
                api_name=f"openrouter_{model_name}",
                error_message=error_msg,
                correlation_id=correlation_id
            )
            
            yield f"\n\n[Error: {error_msg}]"
    
    @staticmethod
    async def chat_completion(
        model_name: str,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 8000
    ) -> str:
        """
        Non-streaming chat completion from OpenRouter.
        
        Args:
            model_name: Orzion model name (e.g., "Orzion Pro")
            messages: OpenAI-style messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
        
        Returns:
            Complete response text
        """
        chunks = []
        async for chunk in OpenRouterProvider.chat_completion_stream(
            model_name, messages, temperature, max_tokens
        ):
            chunks.append(chunk)
        
        return "".join(chunks)
    
    @staticmethod
    def is_available(model_name: str) -> bool:
        """Check if OpenRouter is configured for the given model."""
        model_config = OpenRouterProvider.MODEL_CONFIG.get(model_name)
        if not model_config:
            return False
        
        api_key = model_config.get("key")
        return bool(api_key)
