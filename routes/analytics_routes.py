"""
Analytics routes for usage statistics
"""

from fastapi import APIRouter, Depends
from middleware.auth_middleware import AuthMiddleware
from services.conversation_service import ConversationService
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/analytics/usage")
async def get_usage_analytics(user: dict = Depends(AuthMiddleware.require_auth)):
    """Get usage analytics for the current user."""
    try:
        conversations = await ConversationService.list_conversations(
            user['id'], 
            include_archived=True
        )
        
        total_conversations = len(conversations)
        total_messages = 0
        models_used = {}
        
        for conv in conversations:
            messages = await ConversationService.get_messages(conv['id'])
            total_messages += len(messages)
            
            model = conv.get('model', 'Unknown')
            models_used[model] = models_used.get(model, 0) + 1
        
        recent_conversations = [c for c in conversations[:10]]
        
        return {
            "success": True,
            "analytics": {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "average_messages_per_conversation": round(total_messages / total_conversations, 2) if total_conversations > 0 else 0,
                "models_used": models_used,
                "recent_conversations": recent_conversations
            }
        }
    except Exception as e:
        print(f"❌ Error getting analytics: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/analytics/models")
async def get_model_analytics(user: dict = Depends(AuthMiddleware.require_auth)):
    """Get model usage statistics."""
    try:
        conversations = await ConversationService.list_conversations(
            user['id'],
            include_archived=True
        )
        
        model_stats = {}
        
        for conv in conversations:
            model = conv.get('model', 'Unknown')
            if model not in model_stats:
                model_stats[model] = {
                    "count": 0,
                    "total_messages": 0
                }
            
            model_stats[model]["count"] += 1
            messages = await ConversationService.get_messages(conv['id'])
            model_stats[model]["total_messages"] += len(messages)
        
        return {
            "success": True,
            "model_stats": model_stats
        }
    except Exception as e:
        print(f"❌ Error getting model analytics: {e}")
        return {
            "success": False,
            "error": str(e)
        }
