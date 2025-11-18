from typing import Optional, Dict
from services.supabase_service import get_supabase_service

class UserService:
    
    @staticmethod
    async def get_user_settings(user_id: str) -> Optional[Dict]:
        """Get user settings from Supabase."""
        try:
            supabase_service = get_supabase_service()
            response = supabase_service.table("user_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            
            if response.data:
                return response.data
            return None
            
        except Exception as e:
            print(f"❌ Error getting user settings: {e}")
            return None
    
    @staticmethod
    async def create_user_settings(user_id: str, default_model: str = "Orzion Pro", terms_accepted: bool = False) -> Optional[Dict]:
        """Create default user settings in Supabase."""
        try:
            supabase_service = get_supabase_service()
            settings_data = {
                "user_id": user_id,
                "default_model": default_model,
                "enable_search": True,
                "theme": "dark",
                "language": "es",
                "terms_accepted": terms_accepted
            }
            
            if terms_accepted:
                from datetime import datetime
                settings_data["terms_accepted_at"] = datetime.utcnow().isoformat()
            
            response = supabase_service.table("user_settings").insert(settings_data).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"❌ Error creating user settings: {e}")
            return None
    
    @staticmethod
    async def update_user_settings(user_id: str, **kwargs) -> Optional[Dict]:
        """Update user settings in Supabase with any provided fields."""
        try:
            supabase_service = get_supabase_service()
            
            allowed_fields = [
                'default_model', 'enable_search', 'theme', 'language',
                'assistant_name', 'response_tone', 'response_length', 
                'use_emojis', 'response_language', 'system_prompt',
                'accent_color', 'font_size', 'line_height', 'chat_width',
                'message_sounds', 'desktop_notifications', 'mobile_vibration',
                'full_name', 'bio', 'terms_accepted', 'terms_accepted_at',
                'auto_save', 'save_search_history', 'streaming_enabled', 'confirm_delete'
            ]
            
            update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
            
            if not update_data:
                return await UserService.get_user_settings(user_id)
            
            from datetime import datetime
            update_data["updated_at"] = datetime.utcnow().isoformat()
            
            response = supabase_service.table("user_settings").update(update_data).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Error updating user settings: {e}")
            return None
    
    @staticmethod
    async def accept_terms(user_id: str) -> Optional[Dict]:
        """Mark that user has accepted terms of service."""
        try:
            from datetime import datetime
            supabase_service = get_supabase_service()
            
            update_data = {
                "terms_accepted": True,
                "terms_accepted_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = supabase_service.table("user_settings").update(update_data).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Error accepting terms: {e}")
            return None
