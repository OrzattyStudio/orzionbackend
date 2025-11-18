import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import json

class SecurityEventType(Enum):
    AUTH_FAILED = "authentication_failed"
    AUTH_SUCCESS = "authentication_success"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_INPUT = "invalid_input"
    SANDBOX_VIOLATION = "sandbox_violation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    SESSION_EXPIRED = "session_expired"
    CSRF_DETECTED = "csrf_detected"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("security")

class SecurityLogger:
    
    @staticmethod
    def generate_correlation_id() -> str:
        return str(uuid.uuid4())
    
    @staticmethod
    def sanitize_for_logging(data: Any) -> Any:
        if isinstance(data, dict):
            sanitized = {}
            sensitive_keys = {
                'password', 'token', 'secret', 'api_key', 'access_token',
                'refresh_token', 'authorization', 'cookie', 'session_id',
                'credit_card', 'ssn', 'private_key'
            }
            
            for key, value in data.items():
                key_lower = key.lower()
                if any(sensitive in key_lower for sensitive in sensitive_keys):
                    sanitized[key] = "***REDACTED***"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = SecurityLogger.sanitize_for_logging(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [SecurityLogger.sanitize_for_logging(item) for item in data]
        elif isinstance(data, str):
            if len(data) > 1000:
                return data[:1000] + "...[truncated]"
            return data
        return data
    
    @staticmethod
    def log_security_event(
        event_type: SecurityEventType,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        severity: str = "INFO"
    ) -> str:
        if not correlation_id:
            correlation_id = SecurityLogger.generate_correlation_id()
        
        sanitized_details = SecurityLogger.sanitize_for_logging(details) if details else {}
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": correlation_id,
            "event_type": event_type.value,
            "user_id": user_id or "anonymous",
            "ip_address": ip_address or "unknown",
            "user_agent": (user_agent[:200] if user_agent else "unknown"),
            "details": sanitized_details,
            "severity": severity
        }
        
        log_message = json.dumps(log_entry, ensure_ascii=False)
        
        if severity == "CRITICAL":
            logger.critical(log_message)
        elif severity == "ERROR":
            logger.error(log_message)
        elif severity == "WARNING":
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        return correlation_id
    
    @staticmethod
    def log_auth_attempt(
        success: bool,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        event_type = SecurityEventType.AUTH_SUCCESS if success else SecurityEventType.AUTH_FAILED
        severity = "INFO" if success else "WARNING"
        
        details = {
            "email": email if email and not success else "***REDACTED***",
            "reason": reason
        }
        
        return SecurityLogger.log_security_event(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            correlation_id=correlation_id,
            severity=severity
        )
    
    @staticmethod
    def log_rate_limit(
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        resource: str = "unknown",
        limit: int = 0,
        correlation_id: Optional[str] = None
    ) -> str:
        details = {
            "resource": resource,
            "limit": limit,
            "action": "request_blocked"
        }
        
        return SecurityLogger.log_security_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            correlation_id=correlation_id,
            severity="WARNING"
        )
    
    @staticmethod
    def log_sandbox_violation(
        user_id: Optional[str] = None,
        violation_type: str = "unknown",
        code_snippet: Optional[str] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        details = {
            "violation_type": violation_type,
            "code_snippet": code_snippet[:200] if code_snippet else None
        }
        
        return SecurityLogger.log_security_event(
            event_type=SecurityEventType.SANDBOX_VIOLATION,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            correlation_id=correlation_id,
            severity="ERROR"
        )
    
    @staticmethod
    def log_validation_error(
        user_id: Optional[str] = None,
        field: str = "unknown",
        error_message: str = "validation failed",
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        details = {
            "field": field,
            "error": error_message
        }
        
        return SecurityLogger.log_security_event(
            event_type=SecurityEventType.VALIDATION_ERROR,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            correlation_id=correlation_id,
            severity="INFO"
        )
    
    @staticmethod
    def log_api_error(
        api_name: str,
        error_message: str,
        user_id: Optional[str] = None,
        status_code: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        details = {
            "api": api_name,
            "error": error_message[:500],
            "status_code": status_code
        }
        
        return SecurityLogger.log_security_event(
            event_type=SecurityEventType.API_ERROR,
            user_id=user_id,
            details=details,
            correlation_id=correlation_id,
            severity="ERROR"
        )
    
    @staticmethod
    def log_unauthorized_access(
        user_id: Optional[str] = None,
        resource: str = "unknown",
        action: str = "access_denied",
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        details = {
            "resource": resource,
            "action": action
        }
        
        return SecurityLogger.log_security_event(
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            correlation_id=correlation_id,
            severity="WARNING"
        )
    
    @staticmethod
    def log_suspicious_activity(
        user_id: Optional[str] = None,
        activity_type: str = "unknown",
        description: str = "",
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> str:
        details = {
            "activity_type": activity_type,
            "description": description[:500]
        }
        
        return SecurityLogger.log_security_event(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            correlation_id=correlation_id,
            severity="CRITICAL"
        )
