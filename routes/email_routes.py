
"""
Email Routes - Email verification and password reset
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from services.email_service import EmailService
from middleware.security_middleware import SecurityMiddleware

router = APIRouter(prefix="/api/email", tags=["Email"])

class RequestPasswordResetRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.get("/verify")
async def verify_email(token: str):
    """Verify email with token"""
    result = await EmailService.verify_email_token(token)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {
        "success": True,
        "message": "Email verificado exitosamente"
    }

@router.post("/request-password-reset")
async def request_password_reset(request: RequestPasswordResetRequest, req: Request):
    """Request password reset email"""
    email = SecurityMiddleware.sanitize_input(request.email.lower())
    
    result = await EmailService.send_password_reset_email(email)
    
    return {
        "success": True,
        "message": "Si el email existe, recibirás un enlace de restablecimiento"
    }

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password with token"""
    is_valid, error_msg = SecurityMiddleware.validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    result = await EmailService.reset_password(request.token, request.new_password)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {
        "success": True,
        "message": "Contraseña actualizada exitosamente"
    }
