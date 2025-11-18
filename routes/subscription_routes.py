"""
Subscription Routes - API endpoints for subscription management
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any
from pydantic import BaseModel
from middleware.auth_middleware import AuthMiddleware
from services.subscription_service import SubscriptionService
from services.stripe_service import StripeService
from services.security_logger import SecurityLogger
import os

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@router.get("/plans")
async def get_all_plans() -> Dict[str, Any]:
    """
    Get all available subscription plans.
    Public endpoint - no auth required.
    """
    try:
        plans = await SubscriptionService.get_all_plans()
        return {
            "success": True,
            "plans": plans
        }
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/subscriptions/plans",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching plans")


@router.get("/me")
async def get_my_subscription(
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get current user's active subscription plan and details.
    """
    try:
        user_id = current_user["id"]
        active_plan = await SubscriptionService.get_user_active_plan(user_id)
        
        return {
            "success": True,
            "subscription": active_plan
        }
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/subscriptions/me",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching subscription")


@router.get("/history")
async def get_my_subscription_history(
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get user's subscription history.
    """
    try:
        user_id = current_user["id"]
        all_subs = await SubscriptionService.get_user_subscriptions(user_id)
        
        return {
            "success": True,
            "subscriptions": all_subs
        }
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/subscriptions/history",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching history")


@router.post("/cancel/{plan_name}")
async def cancel_subscription(
    plan_name: str,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Cancel a user's subscription.
    """
    try:
        user_id = current_user["id"]
        result = await SubscriptionService.cancel_subscription(user_id, plan_name)
        
        if result.get("success"):
            return {
                "success": True,
                "message": result.get("message", "Subscription cancelled")
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to cancel"))
    except HTTPException:
        raise
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="POST /api/subscriptions/cancel",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error cancelling subscription")


class CreateCheckoutRequest(BaseModel):
    plan_name: str


@router.post("/create")
async def create_stripe_subscription(
    request: CreateCheckoutRequest,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout session for a subscription plan.
    Returns checkout URL to redirect the user.
    """
    try:
        user_id = current_user["id"]
        email = current_user.get("email", "")
        
        if not email:
            raise HTTPException(status_code=400, detail="User email required")
        
        # Get domain for success/cancel URLs
        domain = os.getenv("REPLIT_DEV_DOMAIN", "localhost:5000")
        protocol = "https" if "replit" in domain else "http"
        base_url = f"{protocol}://{domain}"
        
        success_url = f"{base_url}/plans.html?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/plans.html?cancelled=true"
        
        result = await StripeService.create_checkout_session(
            user_id=user_id,
            email=email,
            plan_name=request.plan_name,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        if result.get("success"):
            return {
                "success": True,
                "session_id": result.get("session_id"),
                "url": result.get("url")
            }
        else:
            return {
                "success": False,
                "message": result.get("error", "Stripe not configured"),
                "configured": StripeService.is_configured()
            }
    
    except HTTPException:
        raise
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="POST /api/subscriptions/create",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error creating subscription")


@router.get("/status")
async def get_stripe_subscription_status(
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get current Stripe subscription status for the user.
    """
    try:
        user_id = current_user["id"]
        result = await StripeService.get_subscription_status(user_id)
        
        return result
    
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/subscriptions/status",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching subscription status")


@router.post("/portal")
async def create_billing_portal_session(
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Create a Stripe billing portal session for subscription management.
    Returns portal URL to redirect the user.
    """
    try:
        user_id = current_user["id"]
        
        # Get domain for return URL
        domain = os.getenv("REPLIT_DEV_DOMAIN", "localhost:5000")
        protocol = "https" if "replit" in domain else "http"
        return_url = f"{protocol}://{domain}/plans.html"
        
        result = await StripeService.create_portal_session(user_id, return_url)
        
        if result.get("success"):
            return {
                "success": True,
                "url": result.get("url")
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create portal session"))
    
    except HTTPException:
        raise
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="POST /api/subscriptions/portal",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error creating portal session")
