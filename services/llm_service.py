import httpx
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timedelta
from config import config
from system_prompts import get_system_prompt
from services.security_logger import SecurityLogger

class CircuitBreaker:
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
    circuit_breakers: Dict[str, CircuitBreaker] = {}
    
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
        """Get the API configuration for the specified model."""
        configs = {
            "Orzion Pro": {
                "url": config.ORZION_PRO_URL,
                "key": config.ORZION_PRO_KEY,
                "model": config.ORZION_PRO_MODEL
            },
            "Orzion Turbo": {
                "url": config.ORZION_TURBO_URL,
                "key": config.ORZION_TURBO_KEY,
                "model": config.ORZION_TURBO_MODEL,
                "model_secondary": config.ORZION_TURBO_MODEL_SECONDARY
            },
            "Orzion Mini": {
                "url": config.ORZION_MINI_URL,
                "key": config.ORZION_MINI_KEY,
                "model": config.ORZION_MINI_MODEL,
                "model_secondary": config.ORZION_MINI_MODEL_SECONDARY
            }
        }
        return configs.get(model_name, configs["Orzion Pro"])
    
    @staticmethod
    async def get_chat_completion_stream(
        model_name: str,
        messages: list,
        search_context: Optional[str] = None,
        special_mode: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Get streaming chat completion from OpenRouter."""
        
        # DeepResearch mode
        if special_mode == "deepresearch":
            yield "🔬 **Modo Deep Research activado**\n\n"
            async for chunk in LLMService._deepresearch_stream(messages, search_context):
                yield chunk
            return
        
        # DeepThinking mode (faster response)
        if special_mode == "deepthinking":
            yield "⚡ **Modo Deep Thinking activado**\n\n"
        
        model_config = LLMService.get_model_config(model_name)
        
        if not model_config.get('key'):
            yield f"Error de configuración: La API key para {model_name} no está configurada."
            return
        
        # Todos los modelos usan flujo normal (single model)
        async for chunk in LLMService._single_model_stream(model_config, messages, search_context, model_name, special_mode):
            yield chunk
    
    @staticmethod
    async def _deepresearch_stream(messages: list, search_context: Optional[str]) -> AsyncGenerator[str, None]:
        """Stream from DeepResearch model - fallback to Pro if not configured."""
        
        # Check if DeepResearch is configured
        if not config.MODEL_RESEARCH or not config.MODEL_RESEARCH_KEY:
            print("⚠️ [DeepResearch] Not configured, falling back to Pro")
            yield "🔬 **Modo Deep Research** (usando Orzion Pro)\n\n"
            
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
                print(f"\n🔬 [DeepResearch] Enviando request...")
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
                        yield "⚠️ Deep Research no disponible, usando Orzion Pro...\n\n"
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
            yield "⚠️ Error en Deep Research, usando Orzion Pro...\n\n"
            model_config = LLMService.get_model_config("Orzion Pro")
            async for chunk in LLMService._single_model_stream(model_config, messages, search_context, "Orzion Pro", "deepresearch"):
                yield chunk
    
    @staticmethod
    async def _dual_model_stream(model_config: Dict, messages: list, search_context: Optional[str], special_mode: Optional[str]) -> AsyncGenerator[str, None]:
        """Combine responses from both Pro models."""
        system_prompt = get_system_prompt("Orzion Pro", search_context)
        
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        headers = {
            "Authorization": f"Bearer {model_config['key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://orzion.app",
            "X-Title": "Orzion Pro Dual"
        }
        
        # Define timeout once for both requests
        timeout = httpx.Timeout(45.0, connect=10.0, read=45.0, write=10.0)
        
        # Obtener respuesta del primer modelo
        response1 = ""
        payload1 = {
            "model": model_config["model"],
            "messages": full_messages,
            "stream": False,
            "temperature": 0.7 if special_mode != "deepthinking" else 0.9
        }
        
        # En Deep Thinking, mostrar estado mientras piensa
        if special_mode == "deepthinking":
            yield "[THINKING_START]"
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                print(f"\n🔵 [Pro Model 1] {model_config['model']}")
                resp1 = await client.post(
                    model_config["url"],
                    json=payload1,
                    headers=headers
                )
                if resp1.status_code == 200:
                    data1 = resp1.json()
                    response1 = data1["choices"][0]["message"]["content"]
                    
                    # En Deep Thinking, enviar el razonamiento del primer modelo
                    if special_mode == "deepthinking" and response1:
                        # Asegurar que response1 es string
                        thinking_text = str(response1) if not isinstance(response1, str) else response1
                        yield f"[THINKING_CONTENT]{thinking_text}[/THINKING_CONTENT]"
        except Exception as e:
            print(f"🔴 Error en modelo 1: {e}")
        
        if special_mode == "deepthinking":
            yield "[THINKING_END]"
        
        # Obtener respuesta del segundo modelo (Comet API)
        response2 = ""
        
        # Usar Comet API si está configurado
        secondary_url = model_config.get("url_secondary", model_config["url"])
        secondary_key = model_config.get("key_secondary", model_config["key"])
        
        payload2 = {
            "model": model_config["model_secondary"],
            "messages": full_messages + [{"role": "assistant", "content": response1}] if response1 else full_messages,
            "stream": True,
            "temperature": 0.8 if special_mode != "deepthinking" else 1.0,
            "max_tokens": 4000
        }
        
        # Headers para Comet API
        headers_secondary = {
            "Authorization": f"Bearer {secondary_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                print(f"\n🔵 [Pro Model 2 - Comet] {model_config['model_secondary']}")
                print(f"🔵 URL: {secondary_url}")
                
                async with client.stream(
                    "POST",
                    secondary_url,
                    json=payload2,
                    headers=headers_secondary
                ) as response:
                    
                    if response.status_code != 200:
                        # Solo usar response1 como fallback si no es Deep Thinking
                        if response1 and special_mode != "deepthinking":
                            for char in response1:
                                yield char
                        return
                    
                    # Stream SOLO la respuesta del segundo modelo
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
            print(f"🔴 Error en modelo 2: {e}")
            # Solo usar response1 como fallback en caso de error
            if response1 and special_mode != "deepthinking":
                for char in response1:
                    yield char
    
    @staticmethod
    async def _single_model_stream(model_config: Dict, messages: list, search_context: Optional[str], model_name: str, special_mode: Optional[str]) -> AsyncGenerator[str, None]:
        """Stream from a single model."""
        system_prompt = get_system_prompt(model_name, search_context)
        
        full_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages
        
        # Use main configuration for all models
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
        
        # Solo para OpenRouter añadir headers adicionales
        if "openrouter" in api_url:
            headers["HTTP-Referer"] = "https://orzion.app"
            headers["X-Title"] = "Orzion Chat"
        
        try:
            timeout = httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                print(f"\n🔵 [{model_name}] Enviando request (streaming)...")
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
                        
                        # Check if it's a rate limit error from OpenRouter
                        if response.status_code == 429 and "rate limit exceeded" in error_decoded.lower():
                            print(f"⚠️ [{model_name}] Rate limit alcanzado en OpenRouter")
                            yield "⚠️ **Límite de solicitudes alcanzado**\n\n"
                            yield "El modelo actual ha alcanzado su límite diario gratuito en OpenRouter.\n"
                            yield "Por favor:\n"
                            yield "1. Agrega créditos en OpenRouter para desbloquear más solicitudes\n"
                            yield "2. Usa otro modelo (Orzion Mini tiene límites diferentes)\n"
                            yield "3. Espera hasta que se resetee el límite diario\n\n"
                            yield f"El límite se reseteará automáticamente en unas horas."
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
            error_msg = "⏱️ Timeout: El modelo tardó demasiado en responder. Por favor, intenta de nuevo."
            print(f"🔴 [{model_name}] Timeout error")
            yield error_msg
        except httpx.ConnectError:
            error_msg = "🔌 Error de conexión: No se pudo conectar con el servicio. Verifica tu conexión."
            print(f"🔴 [{model_name}] Connection error")
            yield error_msg
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            print(f"🔴 [{model_name}] Exception: {error_msg}")
            yield error_msg
    
    @staticmethod
    async def get_chat_completion(
        model_name: str,
        messages: list,
        search_context: Optional[str] = None,
        special_mode: Optional[str] = None
    ) -> str:
        """Get chat completion from OpenRouter without streaming."""
        full_response = ""
        async for chunk in LLMService.get_chat_completion_stream(model_name, messages, search_context, special_mode):
            full_response += chunk
        return full_response
