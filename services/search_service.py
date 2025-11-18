import httpx
import asyncio
from typing import Optional
from config import config
from services.security_logger import SecurityLogger

class SearchService:
    @staticmethod
    async def retry_with_backoff(
        func,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0
    ):
        correlation_id = SecurityLogger.generate_correlation_id()
        
        for attempt in range(max_retries):
            try:
                return await func()
            except httpx.TimeoutException as e:
                if attempt == max_retries - 1:
                    SecurityLogger.log_api_error(
                        api_name="google_search",
                        error_message=f"Timeout after {max_retries} retries",
                        correlation_id=correlation_id
                    )
                    raise
                
                delay = min(base_delay * (2 ** attempt), max_delay)
                print(f"⚠️ [Google Search] Timeout on attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    SecurityLogger.log_api_error(
                        api_name="google_search",
                        error_message=f"Rate limit exceeded",
                        status_code=429,
                        correlation_id=correlation_id
                    )
                    raise
                
                if e.response.status_code >= 500:
                    if attempt == max_retries - 1:
                        SecurityLogger.log_api_error(
                            api_name="google_search",
                            error_message=f"Server error {e.response.status_code}",
                            status_code=e.response.status_code,
                            correlation_id=correlation_id
                        )
                        raise
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    print(f"⚠️ [Google Search] Server error on attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    SecurityLogger.log_api_error(
                        api_name="google_search",
                        error_message=f"Client error {e.response.status_code}",
                        status_code=e.response.status_code,
                        correlation_id=correlation_id
                    )
                    raise
            
            except Exception as e:
                if attempt == max_retries - 1:
                    SecurityLogger.log_api_error(
                        api_name="google_search",
                        error_message=str(e),
                        correlation_id=correlation_id
                    )
                    raise
                
                delay = min(base_delay * (2 ** attempt), max_delay)
                print(f"⚠️ [Google Search] Error on attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        raise Exception(f"Failed after {max_retries} retries")
    
    @staticmethod
    async def search_web(query: str, num_results: int = 5) -> Optional[str]:
        """Search the web using Google Custom Search API with retry logic."""
        if not config.GOOGLE_API_KEY or not config.GOOGLE_CX:
            print("⚠️ Google Search API credentials not configured")
            return "⚠️ La búsqueda web no está configurada. Se necesitan GOOGLE_API_KEY y GOOGLE_CX en los secrets."
        
        async def perform_search():
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": config.GOOGLE_API_KEY,
                "cx": config.GOOGLE_CX,
                "q": query,
                "num": num_results
            }
            
            print(f"🔍 Realizando búsqueda web: {query}")
            
            timeout = httpx.Timeout(15.0, connect=5.0, read=15.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        
        try:
            data = await SearchService.retry_with_backoff(perform_search)
            
            if "items" not in data or not data["items"]:
                print(f"⚠️ No se encontraron resultados para: {query}")
                return f"No se encontraron resultados de búsqueda para: {query}"
            
            search_results = []
            for i, item in enumerate(data["items"][:num_results], 1):
                title = item.get("title", "Sin título")
                snippet = item.get("snippet", "Sin descripción")
                link = item.get("link", "")
                
                search_results.append(
                    f"{i}. **{title}**\n   {snippet}\n   Fuente: {link}\n"
                )
            
            formatted_results = "\n".join(search_results)
            print(f"✅ Se encontraron {len(data['items'])} resultados de búsqueda")
            
            return f"## Resultados de búsqueda web para: '{query}'\n\n{formatted_results}"
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Error HTTP en búsqueda web: {e.response.status_code}"
            if e.response.status_code == 403:
                error_msg += " - Verifica que tu GOOGLE_API_KEY sea válida y tenga permisos."
            elif e.response.status_code == 429:
                error_msg += " - Has excedido el límite de búsquedas diarias."
            print(f"❌ {error_msg}")
            return f"Error al realizar la búsqueda: {error_msg}"
            
        except httpx.TimeoutException:
            error_msg = "Timeout: La búsqueda tardó demasiado tiempo"
            print(f"❌ {error_msg}")
            return f"Error al realizar la búsqueda: {error_msg}"
            
        except Exception as e:
            error_msg = f"Error al realizar la búsqueda web: {str(e)}"
            print(f"❌ {error_msg}")
            return f"Error al realizar la búsqueda: {error_msg}"
