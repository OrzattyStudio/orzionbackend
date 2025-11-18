from supabase import create_client, Client
from typing import Optional, Dict, List
from config import config
import os
import logging

logger = logging.getLogger(__name__)

class SupabaseService:
    _anon_client: Optional[Client] = None
    _service_client: Optional[Client] = None
    
    REQUIRED_TABLES = [
        "user_settings",
        "conversations",
        "messages",
        "audit_logs",
        "rate_limits"
    ]
    
    @classmethod
    def get_anon_client(cls) -> Optional[Client]:
        """Get client with anon key for auth operations. Returns None if credentials missing."""
        if cls._anon_client is None:
            supabase_url = os.getenv("SUPABASE_URL", config.SUPABASE_URL)
            supabase_key = os.getenv("SUPABASE_ANON_KEY", config.SUPABASE_ANON_KEY)
            
            if not supabase_url or not supabase_key:
                logger.warning("⚠️ Supabase anon client unavailable: SUPABASE_URL and SUPABASE_ANON_KEY not configured")
                return None
            
            cls._anon_client = create_client(supabase_url, supabase_key)
            print("✅ Supabase anon client initialized")
        
        return cls._anon_client
    
    @classmethod
    def get_service_client(cls) -> Optional[Client]:
        """Get client with service role key for backend operations (bypasses RLS). Returns None if credentials missing."""
        if cls._service_client is None:
            supabase_url = os.getenv("SUPABASE_URL", config.SUPABASE_URL)
            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", config.SUPABASE_SERVICE_ROLE_KEY)
            
            if not supabase_url or not service_key:
                logger.warning("⚠️ Supabase service client unavailable: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY not configured")
                return None
            
            cls._service_client = create_client(supabase_url, service_key)
            print("✅ Supabase service client initialized")
        
        return cls._service_client
    
    @classmethod
    def reset_clients(cls):
        cls._anon_client = None
        cls._service_client = None
    
    @classmethod
    async def verify_schema(cls) -> Dict[str, any]:
        """
        Verify that all required tables exist in Supabase.
        Returns dict with verification status and missing tables.
        Does NOT raise exceptions - returns status for logging.
        """
        try:
            client = cls.get_service_client()
            if not client:
                logger.error("❌ Error verifying Supabase schema: credentials not configured")
                return {
                    "all_tables_exist": False,
                    "existing_tables": [],
                    "missing_tables": cls.REQUIRED_TABLES,
                    "status": "unavailable",
                    "error": "Supabase credentials not configured"
                }
            
            existing_tables = []
            missing_tables = []
            
            for table in cls.REQUIRED_TABLES:
                try:
                    result = client.table(table).select("*", count="exact").limit(0).execute()
                    existing_tables.append(table)
                    logger.info(f"✅ Table '{table}' exists")
                except Exception as e:
                    missing_tables.append(table)
                    logger.warning(f"⚠️  Table '{table}' not found or not accessible: {str(e)}")
            
            all_ok = len(missing_tables) == 0
            
            if all_ok:
                logger.info("✅ All required Supabase tables are present")
            else:
                logger.warning(f"⚠️  Missing tables: {', '.join(missing_tables)}")
            
            return {
                "all_tables_exist": all_ok,
                "existing_tables": existing_tables,
                "missing_tables": missing_tables,
                "required_tables": cls.REQUIRED_TABLES
            }
        
        except Exception as e:
            logger.error(f"❌ Error verifying Supabase schema: {str(e)}")
            return {
                "all_tables_exist": False,
                "existing_tables": [],
                "missing_tables": cls.REQUIRED_TABLES,
                "required_tables": cls.REQUIRED_TABLES,
                "error": str(e)
            }
    
    @classmethod
    def get_schema_status(cls) -> Dict[str, any]:
        """
        Get current schema status synchronously.
        Returns dict with table existence status.
        """
        try:
            client = cls.get_service_client()
            if not client:
                return {
                    "all_tables_exist": False,
                    "existing_tables": [],
                    "missing_tables": cls.REQUIRED_TABLES,
                    "required_tables": cls.REQUIRED_TABLES,
                    "status": "unavailable",
                    "error": "Supabase credentials not configured"
                }
            
            existing_tables = []
            missing_tables = []
            
            for table in cls.REQUIRED_TABLES:
                try:
                    client.table(table).select("*", count="exact").limit(0).execute()
                    existing_tables.append(table)
                except Exception:
                    missing_tables.append(table)
            
            return {
                "all_tables_exist": len(missing_tables) == 0,
                "existing_tables": existing_tables,
                "missing_tables": missing_tables,
                "required_tables": cls.REQUIRED_TABLES
            }
        
        except Exception as e:
            return {
                "all_tables_exist": False,
                "existing_tables": [],
                "missing_tables": cls.REQUIRED_TABLES,
                "required_tables": cls.REQUIRED_TABLES,
                "error": str(e)
            }
    
    @classmethod
    async def check_connection(cls) -> bool:
        """
        Check if Supabase connection is working.
        Returns True if connection is OK, False otherwise.
        """
        try:
            client = cls.get_service_client()
            if not client:
                logger.error("❌ Supabase connection check failed: credentials not configured")
                return False
            
            client.table("user_settings").select("*", count="exact").limit(0).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Supabase connection check failed: {str(e)}")
            return False

# Lazy initialization - clients are created when first accessed
# This prevents crashes if SUPABASE_* secrets are not set
supabase_client = None
supabase_service = None

def get_supabase_client():
    global supabase_client
    if supabase_client is None:
        supabase_client = SupabaseService.get_anon_client()
    return supabase_client

def get_supabase_service():
    global supabase_service
    if supabase_service is None:
        supabase_service = SupabaseService.get_service_client()
    return supabase_service
