import sys
import os
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from routes import (
    auth_routes,
    chat_routes,
    conversation_routes,
    user_routes,
    image_routes,
    settings_routes,
    analytics_routes,
    document_routes,
    payment_routes,
    subscription_routes,
    referral_routes,
    feedback_routes,
    usage_routes,
    email_routes
)
from config import config
from services.supabase_service import SupabaseService

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event for startup and shutdown tasks."""
    print("\n" + "="*70)
    print("🚀 Orzion Chat API - Starting Up")
    print("="*70)

    print("\n📋 Validating environment variables...")
    config.validate()

    print("\n🔍 Verifying Supabase schema...")
    try:
        schema_status = await SupabaseService.verify_schema()

        if not schema_status["all_tables_exist"]:
            print("\n" + "="*70)
            print("⚠️  WARNING: Some Supabase tables are missing!")
            print("="*70)
            print(f"Missing tables: {', '.join(schema_status['missing_tables'])}")
            print("The server will continue, but some features may not work.")
            print("="*70 + "\n")
        else:
            print("✅ All Supabase tables verified successfully")
    except Exception as e:
        print(f"\n⚠️  WARNING: Could not verify Supabase schema: {str(e)}")
        print("The server will continue, but database features may not work.")

    print("\n✅ Startup complete!")
    print("="*70 + "\n")

    yield

    print("\n👋 Shutting down Orzion Chat API...")

app = FastAPI(title="Orzion Chat API", version="1.0.0", lifespan=lifespan)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        is_production = os.getenv("ENVIRONMENT") == "production"

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com https://unpkg.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https://orzionbackend.onrender.com https://orzion-pro.pages.dev https://*.replit.dev https://accounts.google.com https://*.openrouter.ai https://www.googleapis.com https://unpkg.com; "
            "frame-src 'self' https://accounts.google.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests;"
        )

        if is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), "
            "gyroscope=(), accelerometer=()"
        )

        return response

generated_files_dir = Path("generated_files")
generated_files_dir.mkdir(exist_ok=True)

# Get allowed origins from environment or use secure defaults
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []

# Add Replit domains if running on Replit
replit_dev_domain = os.getenv("REPL_SLUG")
replit_owner = os.getenv("REPL_OWNER")
if replit_dev_domain and replit_owner:
    replit_url = f"https://{replit_dev_domain}.{replit_owner}.repl.co"
    if replit_url not in allowed_origins:
        allowed_origins.append(replit_url)

# Add production frontend URLs
production_origins = [
    "https://orzion.com",
    "https://www.orzion.com",
    "https://orzionbackend.onrender.com",
    "https://orzion-pro.pages.dev",
]
for origin in production_origins:
    if origin not in allowed_origins:
        allowed_origins.append(origin)

# Add Replit dev domains (wildcards for development)
import re
replit_dev_pattern = re.compile(r'https://[a-f0-9-]+\.replit\.dev')
# Note: CORS doesn't support wildcards, so we'll handle this in the CORS middleware
# by checking the origin pattern at runtime

# Add localhost for development
if not allowed_origins or os.getenv("ENVIRONMENT") == "development":
    allowed_origins.extend([
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://0.0.0.0:5000",
    ])

# Custom CORS middleware to handle Replit dev domains
from starlette.middleware.cors import CORSMiddleware as _CORSMiddleware
from starlette.datastructures import Headers

class CustomCORSMiddleware(_CORSMiddleware):
    def is_allowed_origin(self, origin: str) -> bool:
        # Check if it's a Replit dev domain
        if re.match(r'https://[a-f0-9-]+\.replit\.dev', origin):
            return True
        # Otherwise use the default logic
        return super().is_allowed_origin(origin)

app.add_middleware(
    CustomCORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["Content-Type"],
    max_age=3600,
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_routes.router, prefix="/api", tags=["auth"])
app.include_router(chat_routes.router, prefix="/api", tags=["chat"])
app.include_router(conversation_routes.router, prefix="/api", tags=["conversations"])
app.include_router(user_routes.router, prefix="/api", tags=["user"])
app.include_router(image_routes.router, prefix="/api", tags=["image"])
app.include_router(settings_routes.router, prefix="/api/user", tags=["settings"])
app.include_router(analytics_routes.router, prefix="/api", tags=["analytics"])
app.include_router(document_routes.router, prefix="/api", tags=["documents"])
app.include_router(referral_routes.router, tags=["referrals"])
app.include_router(usage_routes.router, tags=["usage"])
app.include_router(feedback_routes.router, tags=["feedback"])
app.include_router(subscription_routes.router, tags=["subscriptions"])
app.include_router(payment_routes.router, tags=["payments"])
app.include_router(email_routes.router)

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
print(f"Frontend directory: {frontend_dir}")
print(f"Frontend directory exists: {os.path.exists(frontend_dir)}")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    print(f"Mounted /static to {frontend_dir}")

if generated_files_dir.exists():
    app.mount("/downloads", StaticFiles(directory=str(generated_files_dir)), name="downloads")
    print(f"Mounted /downloads to {generated_files_dir}")

@app.get("/")
async def serve_frontend():
    """Serve the main HTML page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Orzion Chat API", "version": "4.0"}

@app.get("/login.html")
async def serve_login():
    """Serve the login page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "login.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Login page not found"}

@app.get("/chat.html")
async def serve_chat():
    """Serve the chat page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "chat.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Chat page not found"}

@app.get("/chat/{conversation_id}")
async def serve_chat_conversation(conversation_id: int):
    """Serve the chat page for a specific conversation."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "chat.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Chat page not found"}

@app.get("/settings.html")
async def serve_settings():
    """Serve the settings page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "settings.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Settings page not found"}

@app.get("/terms.html")
async def serve_terms():
    """Serve the terms of use page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "terms.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Terms page not found"}

@app.get("/privacy.html")
async def serve_privacy():
    """Serve the privacy policy page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "privacy.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Privacy page not found"}

@app.get("/plans.html")
async def serve_plans():
    """Serve the plans page."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "plans.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "Plans page not found"}

@app.get("/robots.txt")
async def serve_robots():
    """Serve robots.txt for SEO."""
    robots_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "robots.txt")
    if os.path.exists(robots_path):
        return FileResponse(robots_path, media_type="text/plain")
    return FileResponse(robots_path, media_type="text/plain", status_code=404)

@app.get("/sitemap.xml")
async def serve_sitemap():
    """Serve sitemap.xml for SEO."""
    sitemap_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "sitemap.xml")
    if os.path.exists(sitemap_path):
        return FileResponse(sitemap_path, media_type="application/xml")
    return FileResponse(sitemap_path, media_type="application/xml", status_code=404)

@app.get("/manifest.json")
async def serve_manifest():
    """Serve manifest.json for PWA."""
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/json")
    return {"error": "Manifest not found"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    Returns detailed status of all critical components.
    """
    from services.llm_service import LLMService

    health_data = {
        "service": "Orzion Chat",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "healthy"
    }

    env_status = config.check_required_vars()
    health_data["config_ok"] = env_status["critical_ok"]
    health_data["missing_critical_vars"] = env_status["missing_critical"]
    health_data["missing_important_vars"] = env_status["missing_important"]

    try:
        db_ok = await SupabaseService.check_connection()
        health_data["database_ok"] = db_ok

        if db_ok:
            schema_status = SupabaseService.get_schema_status()
            health_data["database_tables_ok"] = schema_status["all_tables_exist"]
            health_data["missing_tables"] = schema_status.get("missing_tables", [])
        else:
            health_data["database_tables_ok"] = False
            health_data["missing_tables"] = []
    except Exception as e:
        health_data["database_ok"] = False
        health_data["database_error"] = str(e)
        health_data["database_tables_ok"] = False

    circuit_breaker_status = {}
    for api_name, breaker in LLMService.circuit_breakers.items():
        circuit_breaker_status[api_name] = {
            "is_open": breaker.is_open,
            "failure_count": breaker.failure_count
        }
    health_data["circuit_breakers"] = circuit_breaker_status

    if not health_data["config_ok"] or not health_data["database_ok"]:
        health_data["status"] = "degraded"

    return health_data

# Config endpoint for frontend
@app.get("/api/config")
async def get_config():
    """Return public configuration for frontend."""
    return {
        "google_client_id": config.GOOGLE_OAUTH_CLIENT_ID,
        "app_name": "Orzion",
        "version": "1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
