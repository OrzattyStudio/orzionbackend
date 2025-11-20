from typing import Optional, Dict
from services.supabase_service import get_supabase_client, get_supabase_service
import os

# gotrue will be imported via supabase client when needed
try:
    from gotrue.errors import AuthApiError
except ImportError:
    # Fallback if gotrue is not directly available
    AuthApiError = Exception

class AuthService:
    @staticmethod
    async def sign_up(email: str, password: str, full_name: Optional[str] = None) -> Optional[Dict]:
        """Register a new user with Supabase Auth."""
        supabase_client = get_supabase_client()
        supabase_service = get_supabase_service()
        try:
            user_metadata = {}
            if full_name:
                user_metadata["full_name"] = full_name

            # Disable email confirmation in the sign up request
            response = supabase_client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_metadata,
                    "email_redirect_to": None  # Disable email confirmation
                }
            })

            print(f"📧 Sign up response received for: {email}")
            print(f"📧 User ID: {response.user.id if response.user else 'None'}")

            if response.user:

                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "full_name": response.user.user_metadata.get("full_name") if response.user.user_metadata else None,
                    "email_verified": response.user.email_confirmed_at is not None,
                    "created_at": response.user.created_at
                }
            return None

        except AuthApiError as e:
            error_msg = str(e)
            print(f"❌ Supabase Auth error during sign up: {error_msg}")
            print(f"❌ Error type: {type(e).__name__}")

            # Log comprehensive error details
            if hasattr(e, 'message'):
                print(f"❌ Error message attr: {e.message}")
            if hasattr(e, 'status'):
                print(f"❌ Error status code: {e.status}")
            if hasattr(e, 'code'):
                print(f"❌ Error code: {e.code}")
            if hasattr(e, 'args') and e.args:
                print(f"❌ Error args: {e.args}")

            # Try to extract JSON error details
            try:
                import json
                error_json = json.loads(error_msg) if isinstance(error_msg, str) and error_msg.startswith('{') else None
                if error_json:
                    print(f"❌ Supabase error JSON: {json.dumps(error_json, indent=2)}")
            except:
                pass

            # Check if it's a duplicate email error
            if "already registered" in error_msg.lower() or "duplicate" in error_msg.lower() or "unique" in error_msg.lower() or "already been registered" in error_msg.lower():
                print("⚠️ User already exists")
                raise Exception("Este correo ya está registrado. Intenta iniciar sesión.")

            # Check for database or email confirmation errors
            if "database error" in error_msg.lower() or "500" in error_msg or "internal server error" in error_msg.lower():
                print("⚠️ Supabase internal server error - possible trigger or RLS policy issue")
                raise Exception("Error del servidor de autenticación. Verifica la configuración de Supabase (triggers, policies).")

            # Generic error for other cases
            raise Exception(f"Error al crear la cuenta: {error_msg}")
        except Exception as e:
            # Only catch non-Exception errors here
            error_msg = str(e)
            if "ya está registrado" in error_msg.lower():
                raise
            print(f"❌ Unexpected error during sign up: {e}")
            raise Exception(f"Error inesperado: {error_msg}")

    @staticmethod
    async def sign_in(email: str, password: str) -> Optional[Dict]:
        """Sign in user with Supabase Auth."""
        supabase_client = get_supabase_client()
        try:
            response = supabase_client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user and response.session:
                return {
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "full_name": response.user.user_metadata.get("full_name") if response.user.user_metadata else None,
                        "avatar_url": response.user.user_metadata.get("avatar_url") if response.user.user_metadata else None,
                        "email_verified": response.user.email_confirmed_at is not None
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at
                    }
                }
            return None

        except AuthApiError as e:
            print(f"❌ Supabase Auth error during sign in: {e}")
            return None
        except Exception as e:
            print(f"❌ Error during sign in: {e}")
            return None

    @staticmethod
    async def sign_in_with_google(id_token: str) -> Optional[Dict]:
        """Sign in with Google OAuth using ID token."""
        supabase_client = get_supabase_client()
        try:
            response = supabase_client.auth.sign_in_with_id_token({
                "provider": "google",
                "token": id_token
            })

            if response.user and response.session:
                return {
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "full_name": response.user.user_metadata.get("full_name") if response.user.user_metadata else None,
                        "avatar_url": response.user.user_metadata.get("avatar_url") if response.user.user_metadata else None,
                        "email_verified": True
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token,
                        "expires_at": response.session.expires_at
                    }
                }
            return None

        except AuthApiError as e:
            print(f"❌ Supabase Auth error during Google sign in: {e}")
            return None
        except Exception as e:
            print(f"❌ Error during Google sign in: {e}")
            return None

    @staticmethod
    async def get_user_from_token(access_token: str) -> Optional[Dict]:
        """Get user data from access token."""
        supabase_client = get_supabase_client()
        try:
            response = supabase_client.auth.get_user(access_token)

            if response.user:
                return {
                    "id": response.user.id,
                    "email": response.user.email,
                    "full_name": response.user.user_metadata.get("full_name") if response.user.user_metadata else None,
                    "avatar_url": response.user.user_metadata.get("avatar_url") if response.user.user_metadata else None,
                    "email_verified": response.user.email_confirmed_at is not None,
                    "created_at": response.user.created_at
                }
            return None

        except AuthApiError as e:
            print(f"❌ Supabase Auth error getting user: {e}")
            return None
        except Exception as e:
            print(f"❌ Error getting user from token: {e}")
            return None

    @staticmethod
    async def sign_out(access_token: str) -> bool:
        """Sign out user."""
        supabase_client = get_supabase_client()
        try:
            supabase_client.auth.sign_out()
            return True
        except Exception as e:
            print(f"❌ Error signing out: {e}")
            return False