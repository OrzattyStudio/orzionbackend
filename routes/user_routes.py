"""
User routes for managing user profile
Note: User settings endpoints are in settings_routes.py to avoid conflicts
"""

from fastapi import APIRouter, HTTPException, status, Depends
from middleware.auth_middleware import AuthMiddleware

router = APIRouter()

@router.get("/user/profile")
async def get_profile(user: dict = Depends(AuthMiddleware.require_auth)):
    """Get current user profile."""
    try:
        return {
            "success": True,
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "avatar_url": user.get('avatar_url'),
                "email_verified": user.get('email_verified', False),
                "created_at": user['created_at'].isoformat() if user.get('created_at') else None,
                "last_login": user['last_login'].isoformat() if user.get('last_login') else None
            }
        }
        
    except Exception as e:
        print(f"❌ Error getting profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )
