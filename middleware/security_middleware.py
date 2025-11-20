"""
Security middleware for input sanitization and validation
"""

import re
from typing import Optional
from datetime import datetime, timedelta
import html
from services.supabase_service import get_supabase_service


class SecurityMiddleware:

    @staticmethod
    def sanitize_input(text: str, max_length: int = 10000) -> str:
        """
        Sanitize user input to prevent XSS and injection attacks.

        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Truncate to max length
        text = text[:max_length]

        # Remove null bytes
        text = text.replace('\x00', '')

        # Escape HTML entities
        text = html.escape(text, quote=True)

        return text

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address format.

        Args:
            email: Email address to validate

        Returns:
            True if valid, False otherwise
        """
        if not email or len(email) > 255:
            return False

        # Basic email regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        return bool(re.match(pattern, email))

    @staticmethod
    def validate_password(password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not password:
            return False, "La contraseña es requerida"

        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"

        if len(password) > 128:
            return False, "La contraseña es demasiado larga"

        # Check for at least one letter and one number
        has_letter = bool(re.search(r'[a-zA-Z]', password))
        has_number = bool(re.search(r'[0-9]', password))

        if not (has_letter and has_number):
            return False, "La contraseña debe contener al menos una letra y un número"

        return True, None

    @staticmethod
    async def check_rate_limit(
        user_id: str,
        model: str,
        max_requests: int = 100,
        time_window_hours: int = 1
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user has exceeded rate limit for a specific model.
        STRICT SECURITY: New accounts (< 24h) have reduced limits.

        Args:
            user_id: User ID (UUID string)
            model: Model name
            max_requests: Maximum requests allowed in time window
            time_window_hours: Time window in hours

        Returns:
            Tuple of (is_allowed, error_message)
        """
        try:
            supabase = get_supabase_service()
            now = datetime.utcnow().isoformat()

            # STRICT SECURITY: Check if account is new (< 24 hours)
            try:
                user_response = supabase.table('user_settings')\
                    .select('created_at')\
                    .eq('user_id', user_id)\
                    .execute()
                
                if user_response.data and len(user_response.data) > 0:
                    created_at = datetime.fromisoformat(user_response.data[0]['created_at'].replace('Z', '+00:00'))
                    account_age_hours = (datetime.utcnow() - created_at.replace(tzinfo=None)).total_seconds() / 3600
                    
                    # New accounts get 50% reduced limits for first 24 hours
                    if account_age_hours < 24:
                        max_requests = max(1, int(max_requests * 0.5))
                        print(f"🔒 SECURITY: New account detected ({account_age_hours:.1f}h old), reduced limit to {max_requests}")
            except Exception as age_check_error:
                print(f"⚠️ Could not check account age: {age_check_error}")

            # Get current rate limit record that hasn't expired
            response = supabase.table('rate_limits')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('model', model)\
                .gt('reset_at', now)\
                .execute()

            if response.data and len(response.data) > 0:
                record = response.data[0]

                # Check if limit exceeded
                if record['request_count'] >= max_requests:
                    return False, f"Rate limit exceeded for {model}. Try again later."

                # Increment count
                supabase.table('rate_limits')\
                    .update({
                        'request_count': record['request_count'] + 1,
                        'last_request': now
                    })\
                    .eq('id', record['id'])\
                    .execute()
            else:
                # Create new rate limit record
                reset_at = (datetime.utcnow() + timedelta(hours=time_window_hours)).isoformat()

                supabase.table('rate_limits')\
                    .insert({
                        'user_id': user_id,
                        'model': model,
                        'request_count': 1,
                        'last_request': now,
                        'reset_at': reset_at
                    })\
                    .execute()

            return True, None

        except Exception as e:
            print(f"⚠️ Rate limit check failed (non-critical): {e}")
            # Allow request on error to avoid blocking users
            return True, None
    
    @staticmethod
    async def check_suspicious_activity(user_id: str, ip_address: str) -> tuple[bool, Optional[str]]:
        """
        STRICT SECURITY: Check for suspicious account activity.
        
        Args:
            user_id: User ID to check
            ip_address: Current IP address
            
        Returns:
            Tuple of (is_safe, warning_message)
        """
        try:
            supabase = get_supabase_service()
            
            # Check for multiple registrations from same IP in last hour
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            
            ip_registrations = supabase.table('audit_logs')\
                .select('*')\
                .eq('action', 'user_register')\
                .eq('ip_address', ip_address)\
                .gte('created_at', one_hour_ago)\
                .execute()
            
            if ip_registrations.data and len(ip_registrations.data) > 3:
                print(f"⚠️ SECURITY ALERT: Multiple registrations from IP {ip_address}")
                return False, "Too many accounts created from this IP. Please try again later."
            
            return True, None
            
        except Exception as e:
            print(f"⚠️ Suspicious activity check failed: {e}")
            return True, None

    @staticmethod
    async def log_audit(
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """
        Log an audit event using Supabase.

        Args:
            user_id: User ID (UUID string, can be None for anonymous)
            action: Action performed
            resource_type: Type of resource
            resource_id: ID of resource
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional details as string

        Returns:
            True if logged successfully
        """
        from services.audit_service import AuditLogService

        return await AuditLogService.log_audit(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )

    @staticmethod
    def get_client_ip(request) -> str:
        """Get client IP address from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        return request.client.host if request.client else "unknown"

    @staticmethod
    def get_user_agent(request) -> str:
        """Get user agent from request."""
        return request.headers.get("User-Agent", "unknown")