"""
Settings routes for managing user settings and data
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from services.user_service import UserService
from services.conversation_service import ConversationService
from middleware.auth_middleware import AuthMiddleware
from middleware.security_middleware import SecurityMiddleware
import json
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

router = APIRouter()

class UpdateSettingsRequest(BaseModel):
    default_model: Optional[str] = None
    enable_search: Optional[bool] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    assistant_name: Optional[str] = None
    response_tone: Optional[str] = None
    response_length: Optional[str] = None
    use_emojis: Optional[bool] = None
    response_language: Optional[str] = None
    system_prompt: Optional[str] = None
    accent_color: Optional[str] = None
    font_size: Optional[int] = None
    line_height: Optional[float] = None
    chat_width: Optional[int] = None
    message_sounds: Optional[bool] = None
    desktop_notifications: Optional[bool] = None
    mobile_vibration: Optional[bool] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    auto_save: Optional[bool] = None
    save_search_history: Optional[bool] = None
    streaming_enabled: Optional[bool] = None
    confirm_delete: Optional[bool] = None

@router.get("/settings")
async def get_settings(user: dict = Depends(AuthMiddleware.require_auth)):
    """Get user settings."""
    try:
        settings = await UserService.get_user_settings(user['id'])
        
        if not settings:
            settings = await UserService.create_user_settings(user['id'])
        
        return {
            "success": True,
            "settings": settings
        }
    except Exception as e:
        print(f"❌ Error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener configuración")

@router.patch("/settings")
async def update_settings(
    request: UpdateSettingsRequest,
    req: Request,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Update user settings."""
    try:
        update_data = {}
        
        for field in request.model_fields:
            value = getattr(request, field)
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")
        
        settings = await UserService.update_user_settings(user['id'], **update_data)
        
        if not settings:
            raise HTTPException(status_code=500, detail="Error al actualizar configuración")
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="settings_updated",
            resource_type="user_settings",
            resource_id=settings['id'],
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req)
        )
        
        return {
            "success": True,
            "settings": settings
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar configuración")

@router.post("/settings/export/json")
async def export_data_json(user: dict = Depends(AuthMiddleware.require_auth)):
    """Export all user data as JSON."""
    try:
        conversations = await ConversationService.list_conversations(user['id'], include_archived=True)
        
        export_data = {
            "user_id": user['id'],
            "email": user.get('email'),
            "full_name": user.get('full_name'),
            "conversations": []
        }
        
        for conv in conversations:
            messages = await ConversationService.get_messages(conv['id'])
            export_data["conversations"].append({
                "id": conv['id'],
                "title": conv['title'],
                "model": conv['model'],
                "created_at": conv['created_at'],
                "messages": messages
            })
        
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        
        return StreamingResponse(
            iter([json_str]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=orzion_export_{user['id']}.json"
            }
        )
    except Exception as e:
        print(f"❌ Error exporting JSON: {e}")
        raise HTTPException(status_code=500, detail="Error al exportar datos")

@router.post("/settings/export/csv")
async def export_data_csv(user: dict = Depends(AuthMiddleware.require_auth)):
    """Export conversations as CSV."""
    try:
        conversations = await ConversationService.list_conversations(user['id'], include_archived=True)
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Conversation ID", "Title", "Model", "Role", "Content", "Created At"])
        
        for conv in conversations:
            messages = await ConversationService.get_messages(conv['id'])
            for msg in messages:
                writer.writerow([
                    conv['id'],
                    conv['title'],
                    conv['model'],
                    msg['role'],
                    msg['content'],
                    msg['created_at']
                ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=orzion_export_{user['id']}.csv"
            }
        )
    except Exception as e:
        print(f"❌ Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail="Error al exportar datos")

@router.delete("/settings/conversations")
async def delete_all_conversations(
    req: Request,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Delete all conversations for the current user."""
    try:
        conversations = await ConversationService.list_conversations(user['id'], include_archived=True)
        
        deleted_count = 0
        for conv in conversations:
            success = await ConversationService.delete_conversation(conv['id'])
            if success:
                deleted_count += 1
        
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="all_conversations_deleted",
            resource_type="conversations",
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req),
            details={"deleted_count": deleted_count}
        )
        
        return {
            "success": True,
            "deleted_count": deleted_count
        }
    except Exception as e:
        print(f"❌ Error deleting conversations: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar conversaciones")
