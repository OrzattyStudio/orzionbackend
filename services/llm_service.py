"""
LLM Service - Main orchestration layer for AI chat completions

Provides:
- Automatic provider selection and fallback
- Response caching with 24h TTL
- Quota tracking and rate limiting
- Backward compatibility with existing code
"""
import httpx
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timedelta
from config import config
from system_prompts import get_system_prompt
from services.security_logger import SecurityLogger
from services.google_ai_provider import GoogleAIProvider
from services.openrouter_provider import OpenRouterProvider
from services.response_cache_service import ResponseCacheService
from services.provider_quota_service import ProviderQuotaService


class CircuitBreaker:
    """Circuit breaker pattern for API resilience."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.is_open = False
    
    def record_success(self):
        self.failure_count = 0
        self.is_open = False
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
    
    def can_attempt(self) -> bool:
        if not self.is_open:
            return True
        
        if self.last_failure_time:
            time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if time_since_failure >= self.recovery_timeout:
                self.is_open = False
                self.failure_count = 0
                return True
        
        return False


class LLMService:
    """
    Main orchestration service for AI-powered chat completions.
    
    Features:
    - Automatic provider selection and fallback
    - Response caching (24h TTL)
    - Smart quota tracking
    - Special modes (deepresearch, deepthinking)
    - Transparent backward compatibility
    """
    
    circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    # Model type mapping for quota tracking
    MODEL_TYPE_MAPPING = {
        "Orzion Pro": "pro",
        "Orzion Turbo": "turbo",
        "Orzion Mini": "mini"
    }
    
    @staticmethod
    def get_circuit_breaker(api_name: str) -> CircuitBreaker:
        if api_name not in LLMService.circuit_breakers:
            LLMService.circuit_breakers[api_name] = CircuitBreaker()
        return LLMService.circuit_breakers[api_name]
    
    @staticmethod
    async def retry_with_backoff(
        func,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        api_name: str = "unknown"
    ):
        """Retry function with exponential backoff."""
        correlation_id = SecurityLogger.generate_correlation_id()
        
        for attempt in range(max_retries):
            try:
                return await func()
            except httpx.TimeoutException as e:
                if attempt == max_retries - 1:
                    SecurityLogger.log_api_error(
                        api_name=api_name,
                        error_message=f"Timeout after {max_retries} retries",
                        correlation_id=correlation_id
                    )
                    raise
                
                delay = min(base_delay * (2 ** attempt), max_delay)
                print(f"⚠️ [{api_name}] Timeout on attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    if attempt == max_retries - 1:
                        SecurityLogger.log_api_error(
                            api_name=api_name,
                            error_message=f"Server error {e.response.status_code}",
                            status_code=e.response.status_code,
                            correlation_id=correlation_id
                        )
                        raise
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    print(f"⚠️ [{api_name}] Server error on attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    SecurityLogger.log_api_error(
                        api_name=api_name,
                        error_message=f"Client error {e.response.status_code}",
                        status_code=e.response.status_code,
                        correlation_id=correlation_id
                    )
                    raise
            
            except Exception as e:
                if attempt == max_retries - 1:
                    SecurityLogger.log_api_error(
                        api_name=api_name,
                        error_message=str(e),
                        correlation_id=correlation_id
                    )
                    raise
                
                delay = min(base_delay * (2 ** attempt), max_delay)
                print(f"⚠️ [{api_name}] Error on attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        raise Exception(f"Failed after {max_retries} retries")
    
    @staticmethod
    def get_model_config(model_name: str) -> Dict[str, Any]:
        """Get the API configuration for the specified model (legacy compatibility)."""
        configs = {
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
        return configs.get(model_name, configs["Orzion Pro"])
    
    @staticmethod
    async def _try_google_provider(
        model_name: str,
        messages: list,
        model_type: str
    ) -> AsyncGenerator[str, None]:
        """
        Try Google AI Studio provider first.
        
        Yields:
            Response chunks or raises exception on failure
        """
        # Check if Google is available for this model
        if not GoogleAIProvider.is_available(model_name):
            print(f"⚠️ Google AI Studio not configured for {model_name}, skipping...")
            raise Exception("Google AI not configured")
        
        # Check provider quota
        available, reason = await ProviderQuotaService.check_provider_available("google", model_type)
        if not available:
            print(f"⚠️ Google AI quota exhausted: {reason}")
            raise Exception(f"Google quota exhausted: {reason}")
        
        print(f"🔵 Trying Google AI Studio for {model_name}...")
        
        try:
            # Stream from Google
            async for chunk in GoogleAIProvider.chat_completion_stream(model_name, messages):
                yield chunk
            
            # Success - increment usage
            await ProviderQuotaService.increment_usage("google", model_type)
            print(f"✅ Google AI Studio response completed for {model_name}")
        
        except httpx.HTTPStatusError as e:
            # Check for quota errors
            if e.response.status_code == 429:
                print(f"🚫 Google AI Studio quota exceeded (429)")
                await ProviderQuotaService.mark_provider_exhausted("google", model_type, 429)
            raise
        
        except Exception as e:
            print(f"❌ Google AI Studio error: {str(e)}")
            raise
    
    @staticmethod
    async def _try_openrouter_provider(
        model_name: str,
        messages: list,
        model_type: str
    ) -> AsyncGenerator[str, None]:
        """
        Fallback to OpenRouter provider.
        
        Yields:
            Response chunks
        """
        # Check if OpenRouter is available
        if not OpenRouterProvider.is_available(model_name):
            print(f"⚠️ OpenRouter not configured for {model_name}")
            yield f"Error: Neither Google AI Studio nor OpenRouter is configured for {model_name}"
            return
        
        print(f"🟡 Falling back to OpenRouter for {model_name}...")
        
        try:
            # Stream from OpenRouter
            async for chunk in OpenRouterProvider.chat_completion_stream(model_name, messages):
                yield chunk
            
            # Success - increment usage
            await ProviderQuotaService.increment_usage("openrouter", model_type)
            print(f"✅ OpenRouter response completed for {model_name}")
        
        except Exception as e:
            print(f"❌ OpenRouter error: {str(e)}")
            yield f"\n\n[Error: {str(e)}]"
    
    @staticmethod
    async def get_chat_completion_stream(
        model_name: str,
        messages: list,
        search_context: Optional[str] = None,
        special_mode: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Get streaming chat completion with automatic Google → OpenRouter fallback.
        
        Args:
            model_name: Model name (Orzion Pro, Orzion Turbo, Orzion Mini)
            messages: Message list
            search_context: Optional search context to inject
            special_mode: Special mode (deepresearch, deepthinking)
            user_id: Optional user ID for caching
        
        Yields:
            Response chunks
        """
        # Handle special modes (use legacy implementation for now)
        if special_mode == "deepresearch":
            async for chunk in LLMService._deepresearch_stream(messages, search_context):
                yield chunk
            return
        
        if special_mode == "deepthinking":
            # Use legacy implementation for deep thinking
            model_config = LLMService.get_model_config(model_name)
            if model_config.get('key'):
                async for chunk in LLMService._single_model_stream(
                    model_config, messages, search_context, model_name, special_mode
                ):
                    yield chunk
            else:
                yield f"Error: {model_name} not configured"
            return
        
        # Check cache if user_id provided
        cached_response = None
        if user_id:
            cached_response = await ResponseCacheService.get_cached_response(
                user_id, model_name, messages
            )
            
            if cached_response:
                # Stream cached response
                for char in cached_response:
                    yield char
                return
        
        # Add system prompt to messages
        system_prompt = get_system_prompt(model_name, search_context)
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        # Get model type for quota tracking
        model_type = LLMService.MODEL_TYPE_MAPPING.get(model_name, "pro")
        
        # Try Google AI Studio first, fallback to OpenRouter
        response_chunks = []
        provider_used = None
        
        try:
            # Try Google first
            async for chunk in LLMService._try_google_provider(model_name, full_messages, model_type):
                response_chunks.append(chunk)
                yield chunk
            provider_used = "google"
        
        except Exception as google_error:
            print(f"⚠️ Google AI failed, falling back to OpenRouter: {google_error}")
            
            # Clear any partial response
            response_chunks.clear()
            
            # Fallback to OpenRouter
            async for chunk in LLMService._try_openrouter_provider(model_name, full_messages, model_type):
                response_chunks.append(chunk)
                yield chunk
            provider_used = "openrouter"
        
        # Cache the complete response if user_id provided
        if user_id and response_chunks:
            full_response = "".join(response_chunks)
            await ResponseCacheService.cache_response(
                user_id, model_name, messages, full_response
            )
    
    @staticmethod
    async def get_chat_completion(
        model_name: str,
        messages: list,
        search_context: Optional[str] = None,
        special_mode: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Get non-streaming chat completion.
        
        Args:
            model_name: Model name
            messages: Message list
            search_context: Optional search context
            special_mode: Special mode
            user_id: Optional user ID for caching
        
        Returns:
            Complete response text
        """
        full_response = ""
        async for chunk in LLMService.get_chat_completion_stream(
            model_name, messages, search_context, special_mode, user_id
        ):
            full_response += chunk
        return full_response
    
    # ============================================================================
    # LEGACY METHODS (for backward compatibility with special modes)
    # ============================================================================
    
    @staticmethod
    async def _deepresearch_stream(messages: list, search_context: Optional[str]) -> AsyncGenerator[str, None]:
        """Stream from DeepResearch model - fallback to Pro if not configured."""
        
        # Check if DeepResearch is configured
        if not config.MODEL_RESEARCH or not config.MODEL_RESEARCH_KEY:
            print("⚠️ [DeepResearch] Not configured, falling back to Pro")
            
            # Use Pro model instead
            model_config = LLMService.get_model_config("Orzion Pro")
            async for chunk in LLMService._single_model_stream(model_config, messages, search_context, "Orzion Pro", "deepresearch"):
                yield chunk
            return
        
        system_prompt = get_system_prompt("DeepResearch", search_context)
        
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        payload = {
            "model": config.MODEL_RESEARCH,
            "messages": full_messages,
            "stream": True,
            "temperature": 0.7
        }
        
        headers = {
            "Authorization": f"Bearer {config.MODEL_RESEARCH_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://orzion.app",
            "X-Title": "Orzion Deep Research"
        }
        
        try:
            timeout = httpx.Timeout(60.0, connect=10.0, read=60.0, write=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                print(f"\n🔬 [DeepResearch] Sending request...")
                print(f"🔬 Model: {config.MODEL_RESEARCH}")
                
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"🔴 [DeepResearch] Error {response.status_code}: {error_text.decode()}")
                        
                        # Fallback to Pro on error
                        model_config = LLMService.get_model_config("Orzion Pro")
                        async for chunk in LLMService._single_model_stream(model_config, messages, search_context, "Orzion Pro", "deepresearch"):
                            yield chunk
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            print(f"❌ [DeepResearch] Exception: {str(e)}")
            # Fallback to Pro
            model_config = LLMService.get_model_config("Orzion Pro")
            async for chunk in LLMService._single_model_stream(model_config, messages, search_context, "Orzion Pro", "deepresearch"):
                yield chunk
    
    @staticmethod
    async def _single_model_stream(model_config: Dict, messages: list, search_context: Optional[str], model_name: str, special_mode: Optional[str]) -> AsyncGenerator[str, None]:
        """Stream from a single model (legacy method for special modes)."""
        system_prompt = get_system_prompt(model_name, search_context)
        
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        api_url = model_config["url"]
        api_key = model_config["key"]
        model_id = model_config["model"]
        
        payload = {
            "model": model_id,
            "messages": full_messages,
            "stream": True,
            "temperature": 0.9 if special_mode == "deepthinking" else 0.7,
            "max_tokens": 4000
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        if "openrouter" in api_url:
            headers["HTTP-Referer"] = "https://orzion.app"
            headers["X-Title"] = "Orzion Chat"
        
        try:
            timeout = httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                print(f"\n🔵 [{model_name}] Sending request (streaming)...")
                print(f"🔵 URL: {api_url}")
                print(f"🔵 Model: {model_id}")
                
                async with client.stream(
                    "POST",
                    api_url,
                    json=payload,
                    headers=headers
                ) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_decoded = error_text.decode()
                        print(f"🔴 [{model_name}] Error response: {error_decoded}")
                        
                        if response.status_code == 429 and "rate limit exceeded" in error_decoded.lower():
                            print(f"⚠️ [{model_name}] Rate limit reached on OpenRouter")
                            yield "⚠️ **Rate limit reached**\n\n"
                            yield "The current model has reached its daily free limit on OpenRouter.\n"
                            yield "Please:\n"
                            yield "1. Add credits to OpenRouter to unlock more requests\n"
                            yield "2. Use another model (Orzion Mini has different limits)\n"
                            yield "3. Wait until the daily limit resets\n\n"
                            yield f"The limit will reset automatically in a few hours."
                        else:
                            yield f"Error: {response.status_code} - {error_decoded}"
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
                                    
        except httpx.TimeoutException:
            error_msg = "⏱️ Timeout: The model took too long to respond. Please try again."
            print(f"🔴 [{model_name}] Timeout error")
            yield error_msg
        except httpx.ConnectError:
            error_msg = "🔌 Connection error: Could not connect to service. Check your connection."
            print(f"🔴 [{model_name}] Connection error")
            yield error_msg
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            print(f"🔴 [{model_name}] Exception: {error_msg}")
            yield error_msg
