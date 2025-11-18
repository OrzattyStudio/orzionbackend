"""
Payment Routes - API endpoints for payment processing (PayPal & Stripe)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any
from pydantic import BaseModel
from middleware.auth_middleware import AuthMiddleware
from services.paypal_service import PayPalService
from services.stripe_service import StripeService
from services.subscription_service import SubscriptionService
from services.security_logger import SecurityLogger

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.get("/config")
async def get_paypal_config() -> Dict[str, Any]:
    """
    Get PayPal client configuration for frontend.
    Returns client ID and mode (sandbox/live).
    """
    try:
        config = PayPalService.get_client_config()
        return {
            "success": True,
            "paypal": config
        }
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/payments/config",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching payment config")


@router.get("/plans/prices")
async def get_plan_prices() -> Dict[str, Any]:
    """
    Get pricing for all subscription plans.
    """
    try:
        prices = PayPalService.get_plan_prices()
        return {
            "success": True,
            "prices": prices
        }
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/payments/plans/prices",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching prices")


class CreateOrderRequest(BaseModel):
    plan_name: str
    billing_period: str = "monthly"


@router.post("/orders/create")
async def create_payment_order(
    request: CreateOrderRequest,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Create a PayPal order for a subscription plan.
    
    NOTE: PayPal integration requires setup. See PAYMENT_SETUP.md for instructions.
    """
    try:
        result = await PayPalService.create_order(
            request.plan_name,
            request.billing_period
        )
        
        if result.get("success"):
            return {
                "success": True,
                "order_id": result.get("order_id"),
                "approval_url": result.get("approval_url")
            }
        else:
            return {
                "success": False,
                "message": result.get("error", "PayPal integration not yet configured"),
                "configured": PayPalService.is_configured()
            }
            
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="POST /api/payments/orders/create",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error creating payment order")


class CaptureOrderRequest(BaseModel):
    payment_id: str
    payer_id: str


@router.post("/orders/capture")
async def capture_payment_order(
    request: CaptureOrderRequest,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Capture a PayPal payment after user approval.
    """
    try:
        user_id = current_user["id"]
        result = await PayPalService.capture_order(request.payment_id, request.payer_id, user_id)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Payment captured successfully"
            }
        else:
            return {
                "success": False,
                "message": result.get("error", "Failed to capture payment")
            }
            
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="POST /api/payments/orders/capture",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error capturing payment")


@router.get("/stripe/config")
async def get_stripe_config() -> Dict[str, Any]:
    """
    Get Stripe client configuration for frontend.
    Returns publishable key for Stripe.js initialization.
    """
    try:
        config = StripeService.get_client_config()
        return {
            "success": True,
            "stripe": config
        }
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/payments/stripe/config",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching Stripe config")


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    """
    Handle Stripe webhook events.
    Processes subscription updates, payments, and cancellations.
    """
    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        result = await StripeService.handle_webhook(payload, signature)
        
        if result.get("success"):
            return {"received": True}
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Webhook processing failed"))
    
    except HTTPException:
        raise
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="POST /api/webhooks/stripe",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error processing webhook")


@router.get("/billing/history")
async def get_billing_history(
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get billing history for the authenticated user.
    Returns list of payment transactions.
    """
    try:
        user_id = current_user["id"]
        history = await StripeService.get_billing_history(user_id)
        
        return {
            "success": True,
            "payments": history
        }
    
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/billing/history",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching billing history")
