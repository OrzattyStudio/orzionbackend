from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel
from typing import Optional
from services.conversation_service import ConversationService
from middleware.auth_middleware import AuthMiddleware
from middleware.security_middleware import SecurityMiddleware

router = APIRouter()

class CreateConversationRequest(BaseModel):
    title: str
    model: str = "Orzion Pro"

class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None

@router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequest,
    req: Request,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Create a new conversation."""
    try:
        # Sanitize title
        title = SecurityMiddleware.sanitize_input(request.title, max_length=500)

        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El título es requerido"
            )

        # Create conversation
        conversation = await ConversationService.create_conversation(
            user_id=user['id'],
            title=title,
            model=request.model
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear la conversación"
            )

        # Log audit
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="conversation_created",
            resource_type="conversation",
            resource_id=conversation['id'],
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req)
        )

        return {
            "success": True,
            "conversation": conversation
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/conversations")
async def list_conversations(
    include_archived: bool = False,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """List all conversations for the current user."""
    try:
        conversations = await ConversationService.list_conversations(
            user_id=user['id'],
            include_archived=include_archived
        )

        return {
            "success": True,
            "conversations": conversations
        }

    except Exception as e:
        print(f"❌ Error listing conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Get a specific conversation with its messages."""
    try:
        # Get conversation
        conversation = await ConversationService.get_conversation(conversation_id, user['id'])

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")

        # Check if user owns this conversation
        if conversation['user_id'] != user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a esta conversación"
            )

        # Get messages
        messages = await ConversationService.get_messages(conversation_id)

        return {
            "success": True,
            "conversation": conversation,
            "messages": messages,
            "model": conversation.get('model', 'Orzion Pro')  # Include model
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener la conversación")

@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: int,
    request: UpdateConversationRequest,
    req: Request,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Update a conversation (rename or archive)."""
    try:
        # Get conversation first to verify ownership
        conversation = await ConversationService.get_conversation(conversation_id, user['id'])

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada"
            )

        if conversation['user_id'] != user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para modificar esta conversación"
            )

        # Sanitize title if provided
        title = None
        if request.title is not None:
            title = SecurityMiddleware.sanitize_input(request.title, max_length=500)
            if not title:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El título no puede estar vacío"
                )

        # Update conversation
        updated_conversation = await ConversationService.update_conversation(
            conversation_id=conversation_id,
            title=title,
            is_archived=request.is_archived
        )

        if not updated_conversation:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar la conversación"
            )

        # Log audit
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="conversation_updated",
            resource_type="conversation",
            resource_id=conversation_id,
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req),
            details={"title": title, "is_archived": request.is_archived}
        )

        return {
            "success": True,
            "conversation": updated_conversation
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    req: Request,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Delete a conversation and all its messages."""
    try:
        # Get conversation first to verify ownership
        conversation = await ConversationService.get_conversation(conversation_id, user['id'])

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada"
            )

        if conversation['user_id'] != user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar esta conversación"
            )

        # Delete conversation
        success = await ConversationService.delete_conversation(conversation_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al eliminar la conversación"
            )

        # Log audit
        await SecurityMiddleware.log_audit(
            user_id=user['id'],
            action="conversation_deleted",
            resource_type="conversation",
            resource_id=conversation_id,
            ip_address=SecurityMiddleware.get_client_ip(req),
            user_agent=SecurityMiddleware.get_user_agent(req)
        )

        return {
            "success": True,
            "message": "Conversación eliminada exitosamente"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Get all messages for a conversation."""
    try:
        # Get conversation first to verify ownership
        conversation = await ConversationService.get_conversation(conversation_id, user['id'])

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada"
            )

        if conversation['user_id'] != user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a esta conversación"
            )

        # Get messages
        messages = await ConversationService.get_messages(conversation_id)

        return {
            "success": True,
            "messages": messages
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/conversations/search")
async def search_conversations(
    q: str,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Search conversations by query."""
    try:
        conversations = await ConversationService.list_conversations(
            user['id'],
            include_archived=True
        )

        results = []
        query_lower = q.lower()

        for conv in conversations:
            if query_lower in conv['title'].lower():
                results.append(conv)
                continue

            messages = await ConversationService.get_messages(conv['id'])
            for msg in messages:
                if query_lower in msg['content'].lower():
                    results.append(conv)
                    break

        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        print(f"❌ Error searching conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la búsqueda"
        )

@router.post("/conversations/{conversation_id}/share")
async def share_conversation(
    conversation_id: int,
    req: Request,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Create a shareable link for a conversation."""
    try:
        conversation = await ConversationService.get_conversation(conversation_id, user['id'])

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada"
            )

        import secrets
        share_token = secrets.token_urlsafe(32)

        from datetime import datetime, timedelta
        from services.supabase_service import get_supabase_service

        supabase = get_supabase_service()
        share_data = {
            "conversation_id": conversation_id,
            "share_token": share_token,
            "created_by": user['id'],
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "views": 0
        }

        response = supabase.table("shared_conversations").insert(share_data).execute()

        if response.data:
            share_url = f"{req.base_url}shared/{share_token}"
            return {
                "success": True,
                "share_url": str(share_url),
                "share_token": share_token
            }

        raise HTTPException(status_code=500, detail="Error al crear enlace")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error sharing conversation: {e}")
        raise HTTPException(status_code=500, detail="Error interno")

@router.post("/messages/{message_id}/feedback")
async def add_message_feedback(
    message_id: int,
    feedback_type: str,
    user: dict = Depends(AuthMiddleware.require_auth)
):
    """Add feedback to a message."""
    try:
        if feedback_type not in ['thumbs_up', 'thumbs_down', 'love', 'laugh']:
            raise HTTPException(status_code=400, detail="Tipo de feedback inválido")

        from services.supabase_service import get_supabase_service
        supabase = get_supabase_service()

        feedback_data = {
            "message_id": message_id,
            "user_id": user['id'],
            "feedback_type": feedback_type
        }

        response = supabase.table("message_feedback").upsert(feedback_data).execute()

        return {
            "success": True,
            "feedback": response.data[0] if response.data else None
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error adding feedback: {e}")
        raise HTTPException(status_code=500, detail="Error al agregar feedback")
