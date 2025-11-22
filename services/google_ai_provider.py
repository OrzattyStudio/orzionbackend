"""
Primary LLM Provider - Handles API calls to primary AI service

Supports streaming responses, multimodal messages, and proper error handling
for primary provider's API format.
"""
import httpx
import json
from typing import AsyncGenerator, Dict, List, Any, Optional
from config import config
from services.security_logger import SecurityLogger


class GoogleAIProvider:
    """
    Primary LLM Provider for API calls.
    
    Handles:
    - Message format conversion (OpenAI-style → provider format)
    - Streaming responses
    - Error handling and quota detection
    - Proxy support
    """
    
    # Model mapping: Orzion names → Google model names
    MODEL_MAPPING = {
        "Orzion Pro": config.GOOGLE_AI_STUDIO_PRO_MODEL,
        "Orzion Turbo": config.GOOGLE_AI_STUDIO_TURBO_MODEL,
        "Orzion Mini": config.GOOGLE_AI_STUDIO_MINI_MODEL
    }
    
    # API key mapping
    KEY_MAPPING = {
        "Orzion Pro": config.GOOGLE_AI_STUDIO_KEY_PRO,
        "Orzion Turbo": config.GOOGLE_AI_STUDIO_KEY_TURBO,
        "Orzion Mini": config.GOOGLE_AI_STUDIO_KEY_MINI
    }
    
    @staticmethod
    def _convert_messages_to_google_format(messages: List[Dict]) -> tuple[Optional[str], List[Dict]]:
        """
        Convert OpenAI-style messages to Google AI format.
        
        Google format separates system instruction from conversation history:
        - systemInstruction: str (optional)
        - contents: List[{role: "user"|"model", parts: [{text: str}]}]
        
        Args:
            messages: OpenAI-style messages [{role: "system"|"user"|"assistant", content: str}]
        
        Returns:
            (system_instruction, contents)
        """
        system_instruction = None
        contents = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            
            # Extract system message
            if role == "system":
                if system_instruction is None:
                    system_instruction = content
                else:
                    # Append to existing system instruction
                    system_instruction += f"\n\n{content}"
                continue
            
            # Convert role names: "assistant" → "model"
            google_role = "model" if role == "assistant" else "user"
            
            # Handle multimodal content (text + images)
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part.get("type") == "text":
                        parts.append({"text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        # Google supports inline images, but we'll skip for now
                        # (requires base64 encoding and mime type)
                        print(f"⚠️ Image content not yet supported in Google AI provider")
                
                if parts:
                    contents.append({"role": google_role, "parts": parts})
            else:
                # Simple text message
                contents.append({
                    "role": google_role,
                    "parts": [{"text": content}]
                })
        
        return system_instruction, contents
    
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
        Stream chat completion from Google AI Studio.
        
        Args:
            model_name: Orzion model name (e.g., "Orzion Pro")
            messages: OpenAI-style messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
        
        Yields:
            Text chunks from the response
        """
        # Get API key
        api_key = GoogleAIProvider.KEY_MAPPING.get(model_name)
        if not api_key:
            yield f"Error: Google AI Studio API key not configured for {model_name}"
            return
        
        # Get Google model name
        google_model = GoogleAIProvider.MODEL_MAPPING.get(model_name)
        if not google_model:
            yield f"Error: Unknown model {model_name}"
            return
        
        # Convert messages to Google format
        system_instruction, contents = GoogleAIProvider._convert_messages_to_google_format(messages)
        
        # Build API URL for streaming
        # Format: https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={key}
        url = f"{config.GOOGLE_AI_STUDIO_BASE_URL}/{google_model}:streamGenerateContent?alt=sse&key={api_key}"
        
        # Build request payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40
            }
        }
        
        # Add system instruction if present
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        correlation_id = SecurityLogger.generate_correlation_id()
        
        try:
            # Create httpx client (proxy support optional)
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    
                    # Parse SSE stream
                    async for line in response.aiter_lines():
                        if not line or line.startswith(":"):
                            continue
                        
                        # SSE format: "data: {json}"
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            
                            try:
                                data = json.loads(data_str)
                                
                                # Extract text from candidates
                                if "candidates" in data:
                                    for candidate in data["candidates"]:
                                        if "content" in candidate:
                                            parts = candidate["content"].get("parts", [])
                                            for part in parts:
                                                if "text" in part:
                                                    yield part["text"]
                            except json.JSONDecodeError:
                                continue
        
        except httpx.HTTPStatusError as e:
            error_msg = f"Google AI API error: {e.response.status_code}"
            
            # Detect quota exceeded errors
            if e.response.status_code == 429:
                error_msg = "Google AI quota exceeded (429). Falling back to OpenRouter..."
            
            SecurityLogger.log_api_error(
                api_name=f"google_ai_{model_name}",
                error_message=error_msg,
                status_code=e.response.status_code,
                correlation_id=correlation_id
            )
            
            # Re-raise to trigger fallback
            raise
        
        except Exception as e:
            error_msg = f"Google AI error: {str(e)}"
            SecurityLogger.log_api_error(
                api_name=f"google_ai_{model_name}",
                error_message=error_msg,
                correlation_id=correlation_id
            )
            raise
    
    @staticmethod
    async def chat_completion(
        model_name: str,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 8000
    ) -> str:
        """
        Non-streaming chat completion from Google AI Studio.
        
        Args:
            model_name: Orzion model name (e.g., "Orzion Pro")
            messages: OpenAI-style messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
        
        Returns:
            Complete response text
        """
        chunks = []
        async for chunk in GoogleAIProvider.chat_completion_stream(
            model_name, messages, temperature, max_tokens
        ):
            chunks.append(chunk)
        
        return "".join(chunks)
    
    @staticmethod
    def is_available(model_name: str) -> bool:
        """Check if Google AI Studio is configured for the given model."""
        api_key = GoogleAIProvider.KEY_MAPPING.get(model_name)
        return bool(api_key)
