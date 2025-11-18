from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import httpx
import base64
from config import config
from middleware.auth_middleware import AuthMiddleware

router = APIRouter()

class ImageRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "1:1"  # Options: 1:1, 3:4, 4:3, 9:16, 16:9
    number_of_images: Optional[int] = 1  # 1-4 images

@router.post("/generate-image")
async def generate_image(
    request: ImageRequest,
    req: Request
):
    """Generate an image using Gemini 2.5 Flash Image (Nano Banana) - FREE tier available."""
    user_id = "anonymous"
    
    # Get user from cookies
    try:
        user = await AuthMiddleware.get_current_user(req)
        if user:
            user_id = user['id']
    except Exception as e:
        print(f"⚠️ Could not get user: {e}")
        user_id = "anonymous"
    
    # Check if Google Gemini API key is configured (supports both keys for compatibility)
    gemini_key = getattr(config, 'GOOGLE_IMAGEN_KEY', None) or config.GOOGLE_GEMINI_KEY
    if not gemini_key:
        return {
            "success": False,
            "error": "Generación de imágenes no configurada. Por favor agrega GOOGLE_GEMINI_KEY o GOOGLE_IMAGEN_KEY.",
            "images": []
        }
    
    # Gemini 2.5 Flash Image (Nano Banana) endpoint - FREE tier: 500 requests/day
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"
    
    # Note: Gemini 2.5 Flash Image only generates ONE image per request
    # The number_of_images parameter is not supported by this model
    if request.number_of_images and request.number_of_images > 1:
        print(f"⚠️ Warning: Gemini 2.5 Flash only supports 1 image per request. Requested: {request.number_of_images}")
    
    # Build the request payload for Gemini API
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": request.prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "imageConfig": {
                "aspectRatio": request.aspect_ratio
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": gemini_key
    }
    
    try:
        async with httpx.AsyncClient() as client:
            print(f"🎨 Generating image with Gemini 2.5 Flash (Nano Banana) for user {user_id}: {request.prompt[:50]}...")
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            # Extract images from Gemini response
            if "candidates" in data and len(data["candidates"]) > 0:
                images = []
                
                for candidate in data["candidates"]:
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            # Check for inline_data (image)
                            if "inlineData" in part:
                                mime_type = part["inlineData"].get("mimeType", "image/png")
                                image_data = part["inlineData"]["data"]
                                
                                # Convert to data URL for frontend display
                                image_url = f"data:{mime_type};base64,{image_data}"
                                images.append({
                                    "url": image_url,
                                    "base64": image_data
                                })
                
                if images:
                    print(f"✅ Generated {len(images)} image(s) successfully with Nano Banana")
                    return {
                        "success": True,
                        "images": images,
                        "prompt": request.prompt,
                        "message": f"Imagen generada exitosamente (Gemini 2.5 Flash - Gratis)"
                    }
                else:
                    print(f"⚠️ No images found in response: {data}")
                    return {
                        "success": False,
                        "error": "No se pudo generar la imagen. Intenta con un prompt diferente.",
                        "images": []
                    }
            else:
                print(f"⚠️ Unexpected response format: {data}")
                return {
                    "success": False,
                    "error": "Respuesta inesperada del servidor. Intenta de nuevo.",
                    "images": []
                }
                
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        print(f"❌ Gemini API error: {error_detail}")
        
        # Handle quota exceeded errors specifically
        if e.response.status_code == 429:
            return {
                "success": False,
                "error": "Has superado la cuota gratuita de generación de imágenes del día (500 imágenes/día). La cuota se restablecerá en 24 horas. Alternativamente, puedes habilitar billing en Google AI Studio para continuar.",
                "images": []
            }
        
        return {
            "success": False,
            "error": f"Error al generar imagen: {error_detail[:200]}",
            "images": []
        }
    except Exception as e:
        print(f"❌ Image generation error: {str(e)}")
        return {
            "success": False,
            "error": f"Error al generar imagen: {str(e)}",
            "images": []
        }
