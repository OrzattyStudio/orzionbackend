import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Supabase Configuration - NO defaults for security
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

    # PostgreSQL Database - LEGACY CODE (NOT USED)
    # This project uses ONLY Supabase for database operations
    # The following DATABASE_URL is commented out as local PostgreSQL is no longer used
    # DATABASE_URL = f"postgresql://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")

    # Secret Key - Must be set via environment variable for production
    # Generate a random one for development if not set
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        import secrets
        SECRET_KEY = secrets.token_hex(32)
        print("⚠️ WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY in environment for production!")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # ========================================================================
    # LLM Model Configuration
    # ========================================================================
    
    # Primary LLM API Keys
    # Configure these in Render for production deployment
    GOOGLE_AI_STUDIO_KEY_PRO = os.getenv("GOOGLE_AI_STUDIO_KEY_PRO", "")
    GOOGLE_AI_STUDIO_KEY_TURBO = os.getenv("GOOGLE_AI_STUDIO_KEY_TURBO", "")
    GOOGLE_AI_STUDIO_KEY_MINI = os.getenv("GOOGLE_AI_STUDIO_KEY_MINI", "")
    GOOGLE_AI_STUDIO_KEY_IMAGE = os.getenv("GOOGLE_AI_STUDIO_KEY_IMAGE", "")
    
    # Primary LLM Models
    GOOGLE_AI_STUDIO_PRO_MODEL = os.getenv("GOOGLE_AI_STUDIO_PRO_MODEL", "gemini-3-pro")
    GOOGLE_AI_STUDIO_TURBO_MODEL = os.getenv("GOOGLE_AI_STUDIO_TURBO_MODEL", "gemini-2.5-flash")
    GOOGLE_AI_STUDIO_MINI_MODEL = os.getenv("GOOGLE_AI_STUDIO_MINI_MODEL", "gemini-2.0-flash")
    GOOGLE_AI_STUDIO_IMAGE_MODEL = os.getenv("GOOGLE_AI_STUDIO_IMAGE_MODEL", "imagen-4.0-ultra")
    
    # Primary LLM Base URL
    GOOGLE_AI_STUDIO_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    
    # Per-user daily quotas (to support 100+ concurrent users)
    QUOTA_PRO_PER_USER_DAY = int(os.getenv("QUOTA_PRO_PER_USER_DAY", "2"))
    QUOTA_TURBO_PER_USER_DAY = int(os.getenv("QUOTA_TURBO_PER_USER_DAY", "10"))
    QUOTA_MINI_PER_USER_DAY = int(os.getenv("QUOTA_MINI_PER_USER_DAY", "12"))
    QUOTA_IMAGE_PER_USER_DAY = int(os.getenv("QUOTA_IMAGE_PER_USER_DAY", "1"))
    
    # System-level quotas (daily limits)
    QUOTA_GOOGLE_PRO_DAILY = int(os.getenv("QUOTA_GOOGLE_PRO_DAILY", "200"))
    QUOTA_GOOGLE_TURBO_DAILY = int(os.getenv("QUOTA_GOOGLE_TURBO_DAILY", "1000"))
    QUOTA_GOOGLE_MINI_DAILY = int(os.getenv("QUOTA_GOOGLE_MINI_DAILY", "1500"))
    QUOTA_GOOGLE_IMAGE_DAILY = int(os.getenv("QUOTA_GOOGLE_IMAGE_DAILY", "50"))
    
    # Fallback LLM Configuration (automatic backup when quotas exhausted)
    ORZION_PRO_URL = os.getenv("ORZION_PRO_URL", "https://openrouter.ai/api/v1/chat/completions")
    ORZION_PRO_KEY = os.getenv("ORZION_PRO_KEY", "")
    ORZION_PRO_MODEL = os.getenv('ORZION_PRO_MODEL', 'meta-llama/llama-3.3-70b-instruct')
    
    ORZION_TURBO_URL = os.getenv("ORZION_TURBO_URL", "https://openrouter.ai/api/v1/chat/completions")
    ORZION_TURBO_KEY = os.getenv("ORZION_TURBO_KEY", "")
    ORZION_TURBO_MODEL = os.getenv("ORZION_TURBO_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    
    ORZION_MINI_URL = os.getenv("ORZION_MINI_URL", "https://openrouter.ai/api/v1/chat/completions")
    ORZION_MINI_KEY = os.getenv("ORZION_MINI_KEY", "")
    ORZION_MINI_MODEL = os.getenv("ORZION_MINI_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    
    # Image Generation Fallback
    FLUX_IMAGE_URL = os.getenv("FLUX_IMAGE_URL", "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell")
    FLUX_IMAGE_KEY = os.getenv("FLUX_IMAGE_KEY", "")
    
    # Special Models - NO hardcoded keys
    MODEL_RESEARCH = os.getenv("MODEL_RESEARCH", "")
    MODEL_RESEARCH_KEY = os.getenv("MODEL_RESEARCH_KEY", "")
    
    # Legacy Google Gemini (deprecated, kept for backwards compatibility)
    GOOGLE_GEMINI_URL = os.getenv("GOOGLE_GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent")
    GOOGLE_GEMINI_KEY = os.getenv("GOOGLE_GEMINI_KEY", "")

    # Cache Configuration (24h TTL)
    RESPONSE_CACHE_TTL_SECONDS = int(os.getenv("RESPONSE_CACHE_TTL_SECONDS", str(24 * 60 * 60)))
    
    # Batch Processing Configuration
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
    
    # Proxy Configuration (optional)
    HTTP_PROXY = os.getenv("HTTP_PROXY", "")
    HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")

    # Google Custom Search
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_CX = os.getenv("GOOGLE_CX", "")

    # Resend Email Service
    RESEND_API_KEY = os.getenv("RESEND_API", "")
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Orzion AI <noreply@orzionai.com>")

    # PayPal Payment Configuration
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "")
    PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")  # sandbox o live

    @classmethod
    def check_required_vars(cls) -> dict:
        """
        Check all required and optional environment variables.
        Returns dict with status and lists of missing variables.
        """
        critical_vars = {
            "SUPABASE_URL": cls.SUPABASE_URL,
            "SUPABASE_ANON_KEY": cls.SUPABASE_ANON_KEY,
            "SUPABASE_SERVICE_ROLE_KEY": cls.SUPABASE_SERVICE_ROLE_KEY
        }

        important_vars = {
            "GOOGLE_AI_STUDIO_KEY_PRO": cls.GOOGLE_AI_STUDIO_KEY_PRO,
            "GOOGLE_AI_STUDIO_KEY_TURBO": cls.GOOGLE_AI_STUDIO_KEY_TURBO,
            "GOOGLE_AI_STUDIO_KEY_MINI": cls.GOOGLE_AI_STUDIO_KEY_MINI,
            "GOOGLE_AI_STUDIO_KEY_IMAGE": cls.GOOGLE_AI_STUDIO_KEY_IMAGE
        }

        optional_vars = {
            "ORZION_PRO_KEY": cls.ORZION_PRO_KEY,
            "ORZION_TURBO_KEY": cls.ORZION_TURBO_KEY,
            "ORZION_MINI_KEY": cls.ORZION_MINI_KEY,
            "FLUX_IMAGE_KEY": cls.FLUX_IMAGE_KEY,
            "GOOGLE_OAUTH_CLIENT_ID": cls.GOOGLE_OAUTH_CLIENT_ID,
            "GOOGLE_GEMINI_KEY": cls.GOOGLE_GEMINI_KEY,
            "GOOGLE_API_KEY": cls.GOOGLE_API_KEY,
            "GOOGLE_CX": cls.GOOGLE_CX,
            "MODEL_RESEARCH_KEY": cls.MODEL_RESEARCH_KEY,
            "RESEND_API_KEY": cls.RESEND_API_KEY,
            "PAYPAL_CLIENT_ID": cls.PAYPAL_CLIENT_ID,
            "PAYPAL_SECRET": cls.PAYPAL_SECRET
        }

        missing_critical = [var for var, val in critical_vars.items() if not val]
        missing_important = [var for var, val in important_vars.items() if not val]
        missing_optional = [var for var, val in optional_vars.items() if not val]

        return {
            "all_ok": len(missing_critical) == 0 and len(missing_important) == 0,
            "critical_ok": len(missing_critical) == 0,
            "missing_critical": missing_critical,
            "missing_important": missing_important,
            "missing_optional": missing_optional
        }

    @classmethod
    def validate(cls):
        """Validate and log all environment variable status."""
        status = cls.check_required_vars()

        if status["missing_critical"]:
            print("\n" + "="*70)
            print("🔴 CRITICAL: Missing required environment variables!")
            print("="*70)
            for var in status["missing_critical"]:
                print(f"  ❌ {var}")
            print("\n⚠️  The application may not function correctly without these variables.")
            print("="*70 + "\n")

        if status["missing_important"]:
            print("\n" + "="*70)
            print("⚠️  WARNING: Missing primary LLM API keys")
            print("="*70)
            for var in status["missing_important"]:
                print(f"  ⚠️  {var}")
            print("\n💡 System will use fallback models for responses.")
            print("💡 Configure primary LLM keys in Render for production.")
            print("="*70 + "\n")

        if status["missing_optional"]:
            print(f"\nℹ️  Optional features disabled (missing vars): {', '.join(status['missing_optional'])}")

        if status["all_ok"]:
            print("✅ All critical and important environment variables are configured!")

        return status["critical_ok"]

config = Config()