
"""
Email Service - Email verification and password reset using Resend
"""
import resend
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from services.supabase_service import get_supabase_service
from services.security_logger import SecurityLogger
import os

resend.api_key = os.getenv("RESEND_API", "")

class EmailTemplates:
    """HTML Email Templates"""
    
    @staticmethod
    def base_template(title: str, content: str) -> str:
        """Base template for all emails"""
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td align="center" style="padding: 40px 0;">
                        <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                            <!-- Header -->
                            <tr>
                                <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #10a37f 0%, #14c48e 100%); border-radius: 12px 12px 0 0;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">Orzion AI</h1>
                                </td>
                            </tr>
                            <!-- Content -->
                            <tr>
                                <td style="padding: 40px;">
                                    {content}
                                </td>
                            </tr>
                            <!-- Footer -->
                            <tr>
                                <td style="padding: 30px 40px; background-color: #f9fafb; border-radius: 0 0 12px 12px; text-align: center; border-top: 1px solid #e5e7eb;">
                                    <p style="margin: 0 0 10px; color: #6b7280; font-size: 14px;">
                                        © {datetime.now().year} Orzion AI. Todos los derechos reservados.
                                    </p>
                                    <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                                        Si no solicitaste este email, puedes ignorarlo de forma segura.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    @staticmethod
    def verification_email(verification_url: str, user_name: str = "") -> str:
        """Email verification template"""
        greeting = f"Hola {user_name}," if user_name else "Hola,"
        content = f"""
        <h2 style="margin: 0 0 20px; color: #111827; font-size: 24px; font-weight: 600;">
            ¡Bienvenido a Orzion AI! 🎉
        </h2>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            {greeting}
        </p>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            Gracias por registrarte en Orzion AI. Para completar tu registro y empezar a usar nuestros modelos de IA, necesitamos verificar tu correo electrónico.
        </p>
        <table role="presentation" style="width: 100%; margin: 30px 0;">
            <tr>
                <td align="center">
                    <a href="{verification_url}" style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #10a37f 0%, #14c48e 100%); color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(16, 163, 127, 0.3);">
                        Verificar mi email
                    </a>
                </td>
            </tr>
        </table>
        <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
            Este enlace expirará en <strong>24 horas</strong> por seguridad.
        </p>
        <div style="margin-top: 30px; padding: 20px; background-color: #f3f4f6; border-radius: 8px; border-left: 4px solid #10a37f;">
            <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.6;">
                <strong>💡 Consejo:</strong> Si el botón no funciona, copia y pega este enlace en tu navegador:
            </p>
            <p style="margin: 10px 0 0; color: #6b7280; font-size: 13px; word-break: break-all;">
                {verification_url}
            </p>
        </div>
        """
        return EmailTemplates.base_template("Verifica tu email - Orzion AI", content)
    
    @staticmethod
    def password_reset_email(reset_url: str, user_name: str = "") -> str:
        """Password reset template"""
        greeting = f"Hola {user_name}," if user_name else "Hola,"
        content = f"""
        <h2 style="margin: 0 0 20px; color: #111827; font-size: 24px; font-weight: 600;">
            Restablece tu contraseña 🔐
        </h2>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            {greeting}
        </p>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            Recibimos una solicitud para restablecer la contraseña de tu cuenta de Orzion AI. Haz clic en el botón de abajo para crear una nueva contraseña:
        </p>
        <table role="presentation" style="width: 100%; margin: 30px 0;">
            <tr>
                <td align="center">
                    <a href="{reset_url}" style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #10a37f 0%, #14c48e 100%); color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(16, 163, 127, 0.3);">
                        Restablecer contraseña
                    </a>
                </td>
            </tr>
        </table>
        <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
            Este enlace expirará en <strong>1 hora</strong> por seguridad.
        </p>
        <div style="margin-top: 30px; padding: 20px; background-color: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
            <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 1.6;">
                <strong>⚠️ Importante:</strong> Si no solicitaste restablecer tu contraseña, ignora este email y tu cuenta permanecerá segura.
            </p>
        </div>
        <div style="margin-top: 20px; padding: 20px; background-color: #f3f4f6; border-radius: 8px; border-left: 4px solid #10a37f;">
            <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.6;">
                <strong>💡 Enlace alternativo:</strong> Si el botón no funciona, copia y pega este enlace:
            </p>
            <p style="margin: 10px 0 0; color: #6b7280; font-size: 13px; word-break: break-all;">
                {reset_url}
            </p>
        </div>
        """
        return EmailTemplates.base_template("Restablece tu contraseña - Orzion AI", content)
    
    @staticmethod
    def magic_link_email(magic_url: str, user_name: str = "") -> str:
        """Magic link login template"""
        greeting = f"Hola {user_name}," if user_name else "Hola,"
        content = f"""
        <h2 style="margin: 0 0 20px; color: #111827; font-size: 24px; font-weight: 600;">
            Accede a tu cuenta ✨
        </h2>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            {greeting}
        </p>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            Haz clic en el botón de abajo para iniciar sesión en tu cuenta de Orzion AI sin necesidad de contraseña:
        </p>
        <table role="presentation" style="width: 100%; margin: 30px 0;">
            <tr>
                <td align="center">
                    <a href="{magic_url}" style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #10a37f 0%, #14c48e 100%); color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(16, 163, 127, 0.3);">
                        Iniciar sesión
                    </a>
                </td>
            </tr>
        </table>
        <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
            Este enlace expirará en <strong>15 minutos</strong> por seguridad.
        </p>
        <div style="margin-top: 30px; padding: 20px; background-color: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
            <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 1.6;">
                <strong>⚠️ Seguridad:</strong> Solo haz clic si solicitaste iniciar sesión. Este enlace te dará acceso completo a tu cuenta.
            </p>
        </div>
        <div style="margin-top: 20px; padding: 20px; background-color: #f3f4f6; border-radius: 8px; border-left: 4px solid #10a37f;">
            <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.6;">
                <strong>💡 Enlace alternativo:</strong> Si el botón no funciona, copia y pega este enlace:
            </p>
            <p style="margin: 10px 0 0; color: #6b7280; font-size: 13px; word-break: break-all;">
                {magic_url}
            </p>
        </div>
        """
        return EmailTemplates.base_template("Inicia sesión en Orzion AI", content)
    
    @staticmethod
    def reauthentication_email(reauth_url: str, user_name: str = "", ip_address: str = "") -> str:
        """Reauthentication required template"""
        greeting = f"Hola {user_name}," if user_name else "Hola,"
        ip_info = f"<br>Dirección IP: <strong>{ip_address}</strong>" if ip_address else ""
        content = f"""
        <h2 style="margin: 0 0 20px; color: #111827; font-size: 24px; font-weight: 600;">
            Confirmación de seguridad requerida 🔒
        </h2>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            {greeting}
        </p>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            Detectamos un intento de acceso a tu cuenta que requiere confirmación adicional para garantizar tu seguridad.
        </p>
        <div style="margin: 20px 0; padding: 20px; background-color: #eff6ff; border-radius: 8px; border-left: 4px solid #3b82f6;">
            <p style="margin: 0; color: #1e40af; font-size: 14px; line-height: 1.6;">
                <strong>📍 Detalles del acceso:</strong><br>
                Fecha y hora: <strong>{datetime.now().strftime('%d/%m/%Y %H:%M:%S UTC')}</strong>{ip_info}
            </p>
        </div>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            Si fuiste tú quien intentó acceder, haz clic en el botón de abajo para confirmar:
        </p>
        <table role="presentation" style="width: 100%; margin: 30px 0;">
            <tr>
                <td align="center">
                    <a href="{reauth_url}" style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #10a37f 0%, #14c48e 100%); color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(16, 163, 127, 0.3);">
                        Confirmar acceso
                    </a>
                </td>
            </tr>
        </table>
        <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
            Este enlace expirará en <strong>30 minutos</strong> por seguridad.
        </p>
        <div style="margin-top: 30px; padding: 20px; background-color: #fee2e2; border-radius: 8px; border-left: 4px solid #ef4444;">
            <p style="margin: 0 0 10px; color: #991b1b; font-size: 14px; line-height: 1.6;">
                <strong>🚨 ¿No fuiste tú?</strong>
            </p>
            <p style="margin: 0; color: #991b1b; font-size: 14px; line-height: 1.6;">
                Si no reconoces este intento de acceso, tu cuenta podría estar en riesgo. Te recomendamos:
            </p>
            <ul style="margin: 10px 0 0; padding-left: 20px; color: #991b1b; font-size: 14px; line-height: 1.6;">
                <li>Cambiar tu contraseña inmediatamente</li>
                <li>Revisar la actividad reciente de tu cuenta</li>
                <li>Contactar a nuestro equipo de soporte</li>
            </ul>
        </div>
        <div style="margin-top: 20px; padding: 20px; background-color: #f3f4f6; border-radius: 8px; border-left: 4px solid #10a37f;">
            <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.6;">
                <strong>💡 Enlace alternativo:</strong> Si el botón no funciona, copia y pega este enlace:
            </p>
            <p style="margin: 10px 0 0; color: #6b7280; font-size: 13px; word-break: break-all;">
                {reauth_url}
            </p>
        </div>
        """
        return EmailTemplates.base_template("Confirmación de seguridad - Orzion AI", content)
    
    @staticmethod
    def welcome_email(user_name: str = "") -> str:
        """Welcome email after verification"""
        greeting = f"Hola {user_name}," if user_name else "Hola,"
        content = f"""
        <h2 style="margin: 0 0 20px; color: #111827; font-size: 24px; font-weight: 600;">
            ¡Bienvenido a Orzion AI! 🎊
        </h2>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            {greeting}
        </p>
        <p style="margin: 0 0 20px; color: #374151; font-size: 16px; line-height: 1.6;">
            Tu cuenta ha sido verificada exitosamente. ¡Estás listo para comenzar a usar Orzion AI!
        </p>
        <div style="margin: 30px 0; padding: 25px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 8px; border-left: 4px solid #10a37f;">
            <h3 style="margin: 0 0 15px; color: #065f46; font-size: 18px; font-weight: 600;">
                🚀 Comienza ahora:
            </h3>
            <ul style="margin: 0; padding-left: 20px; color: #065f46; font-size: 15px; line-height: 1.8;">
                <li>Prueba nuestros 3 modelos de IA: Mini, Turbo y Pro</li>
                <li>Genera documentos, imágenes y código</li>
                <li>Accede a búsqueda web en tiempo real</li>
                <li>Personaliza tu experiencia en Ajustes</li>
            </ul>
        </div>
        <table role="presentation" style="width: 100%; margin: 30px 0;">
            <tr>
                <td align="center">
                    <a href="https://orzionai.pages.dev/chat" style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #10a37f 0%, #14c48e 100%); color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(16, 163, 127, 0.3);">
                        Ir al Chat
                    </a>
                </td>
            </tr>
        </table>
        <div style="margin-top: 30px; padding: 20px; background-color: #f3f4f6; border-radius: 8px;">
            <p style="margin: 0 0 10px; color: #374151; font-size: 14px; line-height: 1.6;">
                <strong>💡 ¿Necesitas ayuda?</strong>
            </p>
            <p style="margin: 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                Visita nuestra <a href="https://orzionai.pages.dev/api-docs" style="color: #10a37f; text-decoration: underline;">documentación</a> o contáctanos en cualquier momento.
            </p>
        </div>
        """
        return EmailTemplates.base_template("¡Bienvenido a Orzion AI!", content)


class EmailService:
    """Service for sending emails via Resend"""
    
    @staticmethod
    def is_configured() -> bool:
        """Check if Resend is configured"""
        return bool(resend.api_key)
    
    @staticmethod
    async def send_verification_email(email: str, user_id: str, user_name: str = "") -> Dict[str, Any]:
        """Send email verification link"""
        if not EmailService.is_configured():
            print("⚠️ Resend not configured, skipping verification email")
            return {"success": False, "error": "Resend not configured"}
        
        try:
            supabase = get_supabase_service()
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
            # Store verification token
            try:
                supabase.table('email_verification_tokens').insert({
                    'user_id': user_id,
                    'token': token,
                    'email': email,
                    'expires_at': expires_at.isoformat()
                }).execute()
            except Exception as db_error:
                print(f"⚠️ Could not store verification token: {db_error}")
                # Continue anyway - we'll send the email
            
            verification_url = f"https://orzionai.pages.dev/verify-email?token={token}"
            
            # Send email
            params = {
                "from": "Orzion AI <noreply@orzionai.com>",
                "to": [email],
                "subject": "Verifica tu correo electrónico - Orzion AI",
                "html": EmailTemplates.verification_email(verification_url, user_name)
            }
            
            try:
                resend.Emails.send(params)
                print(f"✅ Verification email sent to {email}")
            except Exception as email_error:
                print(f"⚠️ Could not send verification email: {email_error}")
            
            SecurityLogger.log_security_event(
                event_type="EMAIL_VERIFICATION_SENT",
                user_id=user_id,
                details={"email": email},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {"success": True}
            
        except Exception as e:
            print(f"❌ Error in send_verification_email: {e}")
            SecurityLogger.log_api_error(
                api_name="EmailService.send_verification_email",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def verify_email_token(token: str) -> Dict[str, Any]:
        """Verify email token and mark email as verified"""
        try:
            supabase = get_supabase_service()
            
            # Get token
            result = supabase.table('email_verification_tokens')\
                .select('*')\
                .eq('token', token)\
                .single()\
                .execute()
            
            if not result.data:
                return {"success": False, "error": "Token inválido"}
            
            token_data = result.data
            expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
            
            if datetime.utcnow() > expires_at:
                return {"success": False, "error": "Token expirado"}
            
            # Mark email as verified
            supabase.auth.admin.update_user_by_id(
                token_data['user_id'],
                {"email_confirmed_at": datetime.utcnow().isoformat()}
            )
            
            # Send welcome email
            await EmailService.send_welcome_email(token_data['email'])
            
            # Delete used token
            supabase.table('email_verification_tokens')\
                .delete()\
                .eq('token', token)\
                .execute()
            
            SecurityLogger.log_security_event(
                event_type="EMAIL_VERIFIED",
                user_id=token_data['user_id'],
                details={"email": token_data['email']},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {"success": True}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="EmailService.verify_email_token",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_password_reset_email(email: str, user_name: str = "") -> Dict[str, Any]:
        """Send password reset link"""
        if not EmailService.is_configured():
            return {"success": False, "error": "Resend not configured"}
        
        try:
            supabase = get_supabase_service()
            
            # Find user by email
            user_result = supabase.auth.admin.list_users()
            user = next((u for u in user_result if u.email == email), None)
            
            if not user:
                # Don't reveal if email exists
                return {"success": True, "message": "Si el email existe, recibirás un enlace"}
            
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=1)
            
            # Store reset token
            supabase.table('password_reset_tokens').insert({
                'user_id': user.id,
                'token': token,
                'email': email,
                'expires_at': expires_at.isoformat()
            }).execute()
            
            reset_url = f"https://orzionai.pages.dev/reset-password?token={token}"
            
            # Send email
            params = {
                "from": "Orzion AI <noreply@orzionai.com>",
                "to": [email],
                "subject": "Restablece tu contraseña - Orzion AI",
                "html": EmailTemplates.password_reset_email(reset_url, user_name)
            }
            
            resend.Emails.send(params)
            
            SecurityLogger.log_security_event(
                event_type="PASSWORD_RESET_REQUESTED",
                user_id=user.id,
                details={"email": email},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {"success": True, "message": "Si el email existe, recibirás un enlace"}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="EmailService.send_password_reset_email",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def reset_password(token: str, new_password: str) -> Dict[str, Any]:
        """Reset password with token"""
        try:
            supabase = get_supabase_service()
            
            # Get token
            result = supabase.table('password_reset_tokens')\
                .select('*')\
                .eq('token', token)\
                .single()\
                .execute()
            
            if not result.data:
                return {"success": False, "error": "Token inválido"}
            
            token_data = result.data
            expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
            
            if datetime.utcnow() > expires_at:
                return {"success": False, "error": "Token expirado"}
            
            # Update password
            supabase.auth.admin.update_user_by_id(
                token_data['user_id'],
                {"password": new_password}
            )
            
            # Delete used token
            supabase.table('password_reset_tokens')\
                .delete()\
                .eq('token', token)\
                .execute()
            
            SecurityLogger.log_security_event(
                event_type="PASSWORD_RESET",
                user_id=token_data['user_id'],
                details={"email": token_data['email']},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {"success": True}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="EmailService.reset_password",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_magic_link(email: str, user_name: str = "") -> Dict[str, Any]:
        """Send magic link for passwordless login"""
        if not EmailService.is_configured():
            return {"success": False, "error": "Resend not configured"}
        
        try:
            supabase = get_supabase_service()
            
            # Find user by email
            user_result = supabase.auth.admin.list_users()
            user = next((u for u in user_result if u.email == email), None)
            
            if not user:
                return {"success": False, "error": "Usuario no encontrado"}
            
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            
            # Store magic link token
            supabase.table('magic_link_tokens').insert({
                'user_id': user.id,
                'token': token,
                'email': email,
                'expires_at': expires_at.isoformat()
            }).execute()
            
            magic_url = f"https://orzionai.pages.dev/magic-login?token={token}"
            
            # Send email
            params = {
                "from": "Orzion AI <noreply@orzionai.com>",
                "to": [email],
                "subject": "Accede a tu cuenta - Orzion AI",
                "html": EmailTemplates.magic_link_email(magic_url, user_name)
            }
            
            resend.Emails.send(params)
            
            SecurityLogger.log_security_event(
                event_type="MAGIC_LINK_SENT",
                user_id=user.id,
                details={"email": email},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {"success": True}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="EmailService.send_magic_link",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_reauthentication_email(email: str, user_id: str, user_name: str = "", ip_address: str = "") -> Dict[str, Any]:
        """Send reauthentication required email"""
        if not EmailService.is_configured():
            return {"success": False, "error": "Resend not configured"}
        
        try:
            supabase = get_supabase_service()
            
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            
            # Store reauth token
            supabase.table('reauth_tokens').insert({
                'user_id': user_id,
                'token': token,
                'email': email,
                'ip_address': ip_address,
                'expires_at': expires_at.isoformat()
            }).execute()
            
            reauth_url = f"https://orzionai.pages.dev/confirm-access?token={token}"
            
            # Send email
            params = {
                "from": "Orzion AI <noreply@orzionai.com>",
                "to": [email],
                "subject": "Confirmación de seguridad requerida - Orzion AI",
                "html": EmailTemplates.reauthentication_email(reauth_url, user_name, ip_address)
            }
            
            resend.Emails.send(params)
            
            SecurityLogger.log_security_event(
                event_type="REAUTH_EMAIL_SENT",
                user_id=user_id,
                details={"email": email, "ip": ip_address},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {"success": True}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="EmailService.send_reauthentication_email",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def send_welcome_email(email: str, user_name: str = "") -> Dict[str, Any]:
        """Send welcome email after verification"""
        if not EmailService.is_configured():
            return {"success": False, "error": "Resend not configured"}
        
        try:
            params = {
                "from": "Orzion AI <noreply@orzionai.com>",
                "to": [email],
                "subject": "¡Bienvenido a Orzion AI! 🎊",
                "html": EmailTemplates.welcome_email(user_name)
            }
            
            resend.Emails.send(params)
            
            return {"success": True}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="EmailService.send_welcome_email",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
