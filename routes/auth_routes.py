"""
Authentication routes for login, register, and Google OAuth using Supabase Auth
"""

from fastapi import APIRouter, HTTPException, Response, Request, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from services.auth_service import AuthService
from services.user_service import UserService
from middleware.auth_middleware import AuthMiddleware
from middleware.security_middleware import SecurityMiddleware
from config import config

router = APIRouter()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    terms_accepted: Optional[bool] = False

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    credential: str

@router.post("/auth/register")
async def register(request: RegisterRequest, req: Request, response: Response):
    """Register a new user with Supabase Auth."""
    try:
        email = SecurityMiddleware.sanitize_input(request.email.lower())
        full_name = SecurityMiddleware.sanitize_input(request.full_name) if request.full_name else None
        
        if not SecurityMiddleware.validate_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de correo electrónico inválido"
            )
        
        is_valid, error_msg = SecurityMiddleware.validate_password(request.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        try:
            user = await AuthService.sign_up(
                email=email,
                password=request.password,
                full_name=full_name
            )
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pudo crear el usuario. Verifica tus datos."
                )
        except HTTPException:
            raise
        except Exception as signup_error:
            error_message = str(signup_error)
            print(f"❌ Error capturado en register route: {error_message}")
            
            # Handle specific error messages from AuthService
            if "ya está registrado" in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_message
                )
            
            # Generic error for other cases
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message if error_message else "Error al crear la cuenta."
            )
        
        # Create user settings
        try:
            await UserService.create_user_settings(user['id'], terms_accepted=request.terms_accepted)
        except Exception as settings_error:
            print(f"⚠️ Could not create user settings: {settings_error}")
        
        # Send verification email asynchronously (don't wait for it)
        from services.email_service import EmailService
        import asyncio
        asyncio.create_task(EmailService.send_verification_email(email, user['id'], full_name))
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="user_register",
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req)
        )
        
        return {
            "success": True,
            "message": "Usuario registrado exitosamente. Por favor inicia sesión con tu correo y contraseña.",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user.get('full_name')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in register: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/auth/login")
async def login(request: LoginRequest, req: Request, response: Response):
    """Login with Supabase Auth."""
    try:
        email = SecurityMiddleware.sanitize_input(request.email.lower())
        
        auth_response = await AuthService.sign_in(
            email=email,
            password=request.password
        )
        
        if not auth_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correo o contraseña incorrectos. Verifica tus credenciales e intenta nuevamente."
            )
        
        user = auth_response['user']
        session = auth_response['session']
        
        settings = await UserService.get_user_settings(user['id'])
        if not settings:
            await UserService.create_user_settings(user['id'])
        
        response.set_cookie(
            key="access_token",
            value=session['access_token'],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=session['expires_at'] if session.get('expires_at') else 3600
        )
        
        response.set_cookie(
            key="refresh_token",
            value=session['refresh_token'],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=30 * 24 * 60 * 60
        )
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="user_login",
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req)
        )
        
        return {
            "success": True,
            "message": "Inicio de sesión exitoso",
            "access_token": session['access_token'],
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user.get('full_name'),
                "avatar_url": user.get('avatar_url'),
                "email_verified": user.get('email_verified', False)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/auth/google")
async def google_auth(request: GoogleAuthRequest, req: Request, response: Response):
    """Authenticate with Google OAuth using Supabase."""
    try:
        try:
            idinfo = id_token.verify_oauth2_token(
                request.credential,
                google_requests.Request(),
                config.GOOGLE_OAUTH_CLIENT_ID
            )
        except Exception as e:
            print(f"❌ Error verifying Google token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de Google inválido"
            )
        
        auth_response = await AuthService.sign_in_with_google(request.credential)
        
        if not auth_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al autenticar con Google"
            )
        
        user = auth_response['user']
        session = auth_response['session']
        
        settings = await UserService.get_user_settings(user['id'])
        if not settings:
            await UserService.create_user_settings(user['id'])
        
        response.set_cookie(
            key="access_token",
            value=session['access_token'],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=session['expires_at'] if session.get('expires_at') else 3600
        )
        
        response.set_cookie(
            key="refresh_token",
            value=session['refresh_token'],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=30 * 24 * 60 * 60
        )
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="google_login",
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req)
        )
        
        return {
            "success": True,
            "message": "Autenticación con Google exitosa",
            "access_token": session['access_token'],
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user.get('full_name'),
                "avatar_url": user.get('avatar_url'),
                "email_verified": True
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in google_auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(AuthMiddleware.require_auth)):
    """Logout user from Supabase."""
    try:
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="user_logout",
            ip_address=None,
            user_agent=None
        )
        
        return {
            "success": True,
            "message": "Sesión cerrada exitosamente"
        }
        
    except Exception as e:
        print(f"❌ Error in logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.options("/auth/me")
async def options_me():
    """Handle OPTIONS request for /auth/me"""
    return {"status": "ok"}

@router.get("/auth/me")
async def get_current_user_info(user: dict = Depends(AuthMiddleware.require_auth)):
    """Get current user information."""
    try:
        settings = await UserService.get_user_settings(user['id'])
        
        return {
            "success": True,
            "user": {
                "id": user['id'],
                "email": user['email'],
                "full_name": user.get('full_name'),
                "avatar_url": user.get('avatar_url'),
                "email_verified": user.get('email_verified', False),
                "created_at": user.get('created_at')
            },
            "settings": settings
        }
        
    except Exception as e:
        print(f"❌ Error getting user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/api/terms-status")
async def get_terms_status(user: dict = Depends(AuthMiddleware.require_auth)):
    """Check if user has accepted terms of service."""
    try:
        settings = await UserService.get_user_settings(user['id'])
        
        if not settings:
            return {
                "success": True,
                "terms_accepted": False,
                "terms_accepted_at": None
            }
        
        return {
            "success": True,
            "terms_accepted": settings.get("terms_accepted", False),
            "terms_accepted_at": settings.get("terms_accepted_at")
        }
        
    except Exception as e:
        print(f"❌ Error getting terms status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/api/accept-terms")
async def accept_terms(user: dict = Depends(AuthMiddleware.require_auth)):
    """Mark that user has accepted terms of service."""
    try:
        result = await UserService.accept_terms(user['id'])
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar la aceptación de términos"
            )
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="terms_accepted",
            ip_address=None,
            user_agent=None
        )
        
        return {
            "success": True,
            "message": "Términos de servicio aceptados exitosamente",
            "terms_accepted": True,
            "terms_accepted_at": result.get("terms_accepted_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error accepting terms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )
