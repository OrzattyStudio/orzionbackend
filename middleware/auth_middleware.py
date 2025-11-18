"""
Authentication middleware for FastAPI
Handles authentication with Supabase Auth
"""

from fastapi import Request, HTTPException, status
from typing import Optional
from services.auth_service import AuthService

class AuthMiddleware:

    @staticmethod
    async def get_current_user(request: Request) -> Optional[dict]:
        """
        Get current user from Supabase access token.
        Returns user dict or None if not authenticated.
        """
        try:
            access_token = request.cookies.get("access_token")

            if not access_token:
                return None

            user = await AuthService.get_user_from_token(access_token)
            return user

        except Exception as e:
            print(f"❌ Error in get_current_user: {e}")
            return None

    @staticmethod
    async def require_auth(request: Request) -> dict:
        """
        Verify JWT token from cookie and return user data.
        Raises HTTPException if token is invalid.
        """
        # Allow OPTIONS requests
        if request.method == "OPTIONS":
            return {}

        try:
            user = await AuthMiddleware.get_current_user(request)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No autenticado. Por favor inicia sesión."
                )

            return user
        except HTTPException as e:
            # Re-raise HTTPException to be handled by FastAPI
            raise e
        except Exception as e:
            # Handle other exceptions, e.g., invalid token format
            print(f"❌ Error in require_auth: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor al autenticar."
            )