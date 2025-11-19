
"""
Email Routes - Email verification and password reset
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr
from services.email_service import EmailService
from middleware.security_middleware import SecurityMiddleware
from middleware.auth_middleware import AuthMiddleware

router = APIRouter(prefix="/api/email", tags=["Email"])

class RequestPasswordResetRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

@router.get("/verify")
async def verify_email(token: str):
    """Verify email with token"""
    print(f"[EMAIL-VERIFY] 📧 Verifying email with token: {token[:10]}...")
    result = await EmailService.verify_email_token(token)
    
    if not result.get("success"):
        print(f"[EMAIL-VERIFY] ❌ Verification failed: {result.get('error')}")
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    print(f"[EMAIL-VERIFY] ✅ Email verified successfully")
    return {
        "success": True,
        "message": "Email verificado exitosamente"
    }

@router.post("/resend-verification")
async def resend_verification_email(request: ResendVerificationRequest):
    """Resend verification email to user"""
    print(f"[EMAIL-RESEND] 📧 Resending verification email to: {request.email}")
    email = SecurityMiddleware.sanitize_input(request.email.lower())
    
    try:
        # Get user by email from Supabase
        from services.supabase_service import get_supabase_service
        supabase = get_supabase_service()
        
        # Find user by email
        users = supabase.auth.admin.list_users()
        user = next((u for u in users if u.email == email), None)
        
        if not user:
            print(f"[EMAIL-RESEND] ⚠️ User not found, but returning success for security")
            # Don't reveal if email exists
            return {
                "success": True,
                "message": "Si el email existe, recibirás un correo de verificación"
            }
        
        # Check if email is already verified
        if user.email_confirmed_at:
            print(f"[EMAIL-RESEND] ℹ️ Email already verified")
            return {
                "success": True,
                "message": "Tu email ya está verificado"
            }
        
        # Send verification email
        result = await EmailService.send_verification_email(
            email=email,
            user_id=user.id,
            user_name=user.user_metadata.get('full_name', '')
        )
        
        if result.get("success"):
            print(f"[EMAIL-RESEND] ✅ Verification email resent successfully")
        else:
            print(f"[EMAIL-RESEND] ⚠️ Failed to send email: {result.get('error')}")
        
        return {
            "success": True,
            "message": "Email de verificación enviado. Revisa tu bandeja de entrada."
        }
        
    except Exception as e:
        print(f"[EMAIL-RESEND] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error al enviar email de verificación")

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
