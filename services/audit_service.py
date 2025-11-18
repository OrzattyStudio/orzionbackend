"""
Audit logging service using Supabase
"""

from typing import Optional
from datetime import datetime
from services.supabase_service import get_supabase_service
import os

class AuditLogService:
    
    @staticmethod
    async def log_audit(
        user_id: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """Log an audit event to Supabase."""
        # Check if audit logging is disabled
        if os.getenv("DISABLE_AUDIT_LOGS", "false").lower() == "true":
            return True
        
        supabase_service = get_supabase_service()
        try:
            audit_data = {
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Remove None values
            audit_data = {k: v for k, v in audit_data.items() if v is not None}
            
            response = supabase_service.table("audit_logs").insert(audit_data).execute()
            
            if response.data:
                return True
            return False
            
        except Exception as e:
            # Silently fail to avoid breaking main flow
            print(f"⚠️ Audit log failed (non-critical): {e}")
            return False
