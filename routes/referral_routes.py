"""
Referral Routes - API endpoints for the referral system
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any
from pydantic import BaseModel
from middleware.auth_middleware import AuthMiddleware
from services.referral_service import ReferralService
from services.security_logger import SecurityLogger
from datetime import datetime

router = APIRouter(prefix="/api/referrals", tags=["Referrals"])


class RedeemReferralRequest(BaseModel):
    referral_code: str


@router.get("/me")
async def get_my_referral_stats(current_user: Dict = Depends(AuthMiddleware.require_auth)) -> Dict[str, Any]:
    """
    Get current user's referral code and statistics.
    Returns referral code, total referrals, bonus multiplier, and recent successful referrals.
    """
    try:
        user_id = current_user["id"]
        print(f"[REFERRALS] Fetching stats for user: {user_id}")
        stats = await ReferralService.get_referral_stats(user_id)
        print(f"[REFERRALS] Stats retrieved: {stats}")
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        print(f"[REFERRALS] Error: {str(e)}")
        SecurityLogger.log_api_error(
            api_name="GET /api/referrals/me",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail=f"Error fetching referral stats: {str(e)}")


@router.post("/redeem")
async def redeem_referral_code(
    request: Request,
    body: RedeemReferralRequest,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Redeem a referral code.
    Can only be used within 24 hours of account creation.
    Validates IP to prevent multi-account abuse.
    """
    try:
        user_id = current_user["id"]
        print(f"[REFERRAL-REDEEM] 🎁 User {user_id} attempting to redeem code: {body.referral_code}")
        
        # Get user's IP address
        client_ip = request.client.host if request.client else "0.0.0.0"
        print(f"[REFERRAL-REDEEM] 📍 Client IP: {client_ip}")
        
        # Get user creation timestamp from Supabase
        # Note: current_user should include created_at from the JWT or we fetch it
        user_created_at = current_user.get("created_at")
        if not user_created_at:
            # Fallback: assume account is fresh (within 24h)
            print(f"[REFERRAL-REDEEM] ⚠️ No created_at in JWT, assuming fresh account")
            user_created_at = datetime.utcnow()
        elif isinstance(user_created_at, str):
            user_created_at = datetime.fromisoformat(user_created_at.replace('Z', '+00:00'))
            print(f"[REFERRAL-REDEEM] 📅 Account created at: {user_created_at}")
        
        account_age = datetime.utcnow() - user_created_at
        print(f"[REFERRAL-REDEEM] ⏰ Account age: {account_age} (limit: 24h)")
        
        # Redeem the referral code
        result = await ReferralService.redeem_referral_code(
            referral_code=body.referral_code,
            referred_user_id=user_id,
            ip_address=client_ip,
            user_created_at=user_created_at
        )
        
        if result["success"]:
            print(f"[REFERRAL-REDEEM] ✅ Redemption successful!")
            return {
                "success": True,
                "message": result["message"],
                "bonus_applied": result["bonus_applied"]
            }
        else:
            print(f"[REFERRAL-REDEEM] ❌ Redemption failed: {result['message']}")
            return {
                "success": False,
                "message": result["message"],
                "bonus_applied": False
            }
        
    except Exception as e:
        print(f"[REFERRAL-REDEEM] ❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        SecurityLogger.log_api_error(
            api_name="POST /api/referrals/redeem",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error redeeming referral code")


@router.get("/validate/{referral_code}")
async def validate_referral_code(referral_code: str) -> Dict[str, Any]:
    """
    Validate if a referral code exists and is valid.
    Public endpoint (no auth required) to check code before registration.
    """
    try:
        referrer = await ReferralService.validate_referral_code(referral_code)
        
        if referrer:
            return {
                "success": True,
                "valid": True,
                "message": "Valid referral code"
            }
        else:
            return {
                "success": True,
                "valid": False,
                "message": "Invalid referral code"
            }
        
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/referrals/validate/{referral_code}",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error validating referral code")


@router.get("/leaderboard")
async def get_referral_leaderboard(limit: int = 10) -> Dict[str, Any]:
    """
    Get top referrers (public leaderboard).
    Returns anonymized stats (no user IDs).
    """
    try:
        leaderboard = await ReferralService.get_referral_leaderboard(limit)
        
        return {
            "success": True,
            "data": leaderboard
        }
        
    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/referrals/leaderboard",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error fetching leaderboard")
