"""
Image Generation Routes - Google Imagen 3.0 (primary) with FLUX fallback

Provides image generation using:
1. Google AI Studio imagen-3.0 (primary, free tier: 50 img/day)
2. FLUX-schnell via HuggingFace (fallback)

Integrated with quota system to track per-user usage.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import httpx
import base64
from config import config
from middleware.auth_middleware import AuthMiddleware
from services.limit_service import RateLimitService
from services.provider_quota_service import ProviderQuotaService

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
    """
    Generate an image using Google Imagen 3.0 (primary) or FLUX (fallback).
    
    Flow:
    1. Check user quotas (Google AI: 1 img/day)
    2. Try Google Imagen 3.0 first
    3. Fallback to FLUX if Google fails or quota exceeded
    """
    user_id = "anonymous"
    
    # Get user from cookies
    try:
        user = await AuthMiddleware.get_current_user(req)
        if user:
            user_id = user['id']
    except Exception as e:
        print(f"⚠️ Could not get user: {e}")
        user_id = "anonymous"
    
    # Check Google AI quota if user is authenticated
    google_quota_ok = True
    if user_id != "anonymous":
        google_quota_ok, quota_error = await RateLimitService.check_google_ai_quota(user_id, "Image")
        if not google_quota_ok:
            print(f"⚠️ Google AI image quota exceeded for user {user_id}: {quota_error}")
    
    # Try Google Imagen 3.0 first (if quota available and configured)
    if google_quota_ok and config.GOOGLE_AI_STUDIO_KEY_IMAGE:
        try:
            result = await _generate_with_google_imagen(
                request.prompt,
                request.aspect_ratio,
                request.number_of_images,
                user_id
            )
            
            if result["success"]:
                # Increment quota for successful generation
                if user_id != "anonymous":
                    await RateLimitService.increment_google_ai_usage(user_id, "Image")
                    await ProviderQuotaService.increment_usage("google", "image")
                
                return result
            else:
                print(f"⚠️ Google Imagen failed: {result.get('error')}")
                # Continue to FLUX fallback
        
        except Exception as e:
            print(f"⚠️ Google Imagen exception: {str(e)}")
            # Continue to FLUX fallback
    
    # Fallback to FLUX-schnell
    print(f"🎨 Falling back to FLUX for image generation...")
    return await _generate_with_flux(request.prompt, user_id)


async def _generate_with_google_imagen(
    prompt: str,
    aspect_ratio: str,
    number_of_images: int,
    user_id: str
) -> dict:
    """
    Generate image using Google AI Studio Imagen 3.0.
    
    Returns:
        dict with success, images, and optional error
    """
    # Check provider quota
    available, reason = await ProviderQuotaService.check_provider_available("google", "image")
    if not available:
        return {
            "success": False,
            "error": f"Google Imagen quota exhausted: {reason}",
            "images": []
        }
    
    api_key = config.GOOGLE_AI_STUDIO_KEY_IMAGE
    model = config.GOOGLE_AI_STUDIO_IMAGE_MODEL
    
    # Build API URL
    # Format: https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:generateContent?key={key}
    url = f"{config.GOOGLE_AI_STUDIO_BASE_URL}/{model}:generateContent?key={api_key}"
    
    # Note: Google Imagen only generates ONE image per request
    if number_of_images and number_of_images > 1:
        print(f"⚠️ Warning: Google Imagen only supports 1 image per request. Requested: {number_of_images}")
    
    # Build request payload
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "imageConfig": {
                "aspectRatio": aspect_ratio
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"🎨 Generating image with Google Imagen 3.0 for user {user_id[:8] if user_id != 'anonymous' else 'anon'}...")
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Extract images from response
            if "candidates" in data and len(data["candidates"]) > 0:
                images = []
                
                for candidate in data["candidates"]:
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            # Check for inline_data (image)
                            if "inlineData" in part:
                                mime_type = part["inlineData"].get("mimeType", "image/png")
                                image_data = part["inlineData"]["data"]
                                
                                # Convert to data URL for frontend
                                image_url = f"data:{mime_type};base64,{image_data}"
                                images.append({
                                    "url": image_url,
                                    "base64": image_data
                                })
                
                if images:
                    print(f"✅ Generated {len(images)} image(s) with Google Imagen 3.0")
                    return {
                        "success": True,
                        "images": images,
                        "prompt": prompt,
                        "message": f"Imagen generada con Google AI Studio (Imagen 3.0)",
                        "provider": "google"
                    }
                else:
                    return {
                        "success": False,
                        "error": "No images found in response",
                        "images": []
                    }
            else:
                return {
                    "success": False,
                    "error": "Unexpected response format from Google Imagen",
                    "images": []
                }
    
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        print(f"❌ Google Imagen API error: {error_detail}")
        
        # Handle quota exceeded errors
        if e.response.status_code == 429:
            await ProviderQuotaService.mark_provider_exhausted("google", "image", 429)
            return {
                "success": False,
                "error": "Google Imagen quota exceeded (429). Falling back to FLUX...",
                "images": []
            }
        
        return {
            "success": False,
            "error": f"Google Imagen error: {e.response.status_code}",
            "images": []
        }
    
    except Exception as e:
        print(f"❌ Google Imagen error: {str(e)}")
        return {
            "success": False,
            "error": f"Google Imagen error: {str(e)}",
            "images": []
        }


async def _generate_with_flux(prompt: str, user_id: str) -> dict:
    """
    Generate image using FLUX-schnell via HuggingFace.
    
    Returns:
        dict with success, images, and optional error
    """
    if not config.FLUX_IMAGE_KEY:
        return {
            "success": False,
            "error": "Neither Google Imagen nor FLUX is configured. Please add GOOGLE_AI_STUDIO_KEY_IMAGE or FLUX_IMAGE_KEY.",
            "images": []
        }
    
    url = config.FLUX_IMAGE_URL
    headers = {
        "Authorization": f"Bearer {config.FLUX_IMAGE_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "num_inference_steps": 4,  # FLUX-schnell uses 4 steps
            "guidance_scale": 0.0      # FLUX-schnell doesn't use guidance
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"🎨 Generating image with FLUX-schnell for user {user_id[:8] if user_id != 'anonymous' else 'anon'}...")
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            # FLUX returns raw image bytes
            image_bytes = response.content
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/png;base64,{image_base64}"
            
            print(f"✅ Generated image with FLUX-schnell")
            
            # Increment OpenRouter quota (FLUX is via HuggingFace but counts as fallback)
            await ProviderQuotaService.increment_usage("openrouter", "image")
            
            return {
                "success": True,
                "images": [{
                    "url": image_url,
                    "base64": image_base64
                }],
                "prompt": prompt,
                "message": "Imagen generada con FLUX-schnell (HuggingFace)",
                "provider": "flux"
            }
    
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text
        print(f"❌ FLUX API error: {error_detail}")
        
        return {
            "success": False,
            "error": f"FLUX error: {e.response.status_code}",
            "images": []
        }
    
    except Exception as e:
        print(f"❌ FLUX error: {str(e)}")
        return {
            "success": False,
            "error": f"FLUX error: {str(e)}",
            "images": []
        }
