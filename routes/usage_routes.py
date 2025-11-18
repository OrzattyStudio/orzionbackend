"""
Usage Routes - API endpoints for viewing usage limits and statistics
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from middleware.auth_middleware import AuthMiddleware
from services.limit_service import RateLimitService
from services.security_logger import SecurityLogger

router = APIRouter(prefix="/api/usage", tags=["Usage"])


@router.get("/summary")
async def get_usage_summary(current_user: Dict = Depends(AuthMiddleware.require_auth)) -> Dict[str, Any]:
    """
    Get complete usage summary for all models.
    Shows daily limits, current usage, remaining, and percentage used.
    
    Example response:
    {
        "success": true,
        "data": {
            "plan": "Free",
            "models": {
                "Orzion Pro": {
                    "limits": {
                        "messages_daily": 50,
                        "tokens_per_message": 2000,
                        "tokens_daily": 10000
                    },
                    "usage": {
                        "messages": 35,
                        "tokens": 7500
                    },
                    "remaining": {
                        "messages": 15,
                        "tokens": 2500
                    },
                    "percentage_used": {
                        "messages": 70,
                        "tokens": 75
                    },
                    "unlimited_messages": false
                }
            }
        }
    }
    """
    try:
        user_id = current_user["id"]
        summary = await RateLimitService.get_usage_summary(user_id)
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/usage/summary",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching usage summary")


@router.get("/quota/{model}")
async def get_model_quota(
    model: str,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get detailed quota information for a specific model.
    Shows base limits, bonus limits, and total limits.
    """
    try:
        user_id = current_user["id"]
        
        # Validate model name
        valid_models = ["Orzion Pro", "Orzion Turbo", "Orzion Mini"]
        if model not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model. Must be one of: {', '.join(valid_models)}")
        
        quota = await RateLimitService.get_user_quota(user_id, model)
        
        if not quota:
            return {
                "success": False,
                "message": "Quota not found for this model"
            }
        
        return {
            "success": True,
            "data": {
                "model": model,
                "quota": quota
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name=f"GET /api/usage/quota/{model}",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching model quota")


@router.get("/current/{model}")
async def get_current_usage(
    model: str,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get current usage for a specific model (daily messages and tokens).
    """
    try:
        user_id = current_user["id"]
        
        # Validate model name
        valid_models = ["Orzion Pro", "Orzion Turbo", "Orzion Mini"]
        if model not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model. Must be one of: {', '.join(valid_models)}")
        
        usage = await RateLimitService.get_current_usage(user_id, model)
        limits = await RateLimitService.get_user_limits(user_id, model)
        
        return {
            "success": True,
            "data": {
                "model": model,
                "usage": usage,
                "limits": limits if limits else {}
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name=f"GET /api/usage/current/{model}",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching current usage")
