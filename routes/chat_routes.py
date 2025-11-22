from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import json
from services.llm_service import LLMService
from services.search_service import SearchService
from services.conversation_service import ConversationService
from services.limit_service import RateLimitService
from middleware.auth_middleware import AuthMiddleware
from middleware.security_middleware import SecurityMiddleware

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    prompt: str
    model: str = "Orzion Pro"
    enable_search: bool = False
    history: List[Message] = []
    conversation_id: Optional[int] = None
    special_mode: Optional[str] = None
    image: Optional[str] = None # Added field for image URL

@router.post("/chat")
async def chat(
    request: ChatRequest,
    req: Request
):
    """Handle chat requests with optional authentication."""
    try:
        # Get user if authenticated (optional)
        user = await AuthMiddleware.get_current_user(req)
        user_id = user['id'] if user else None

        # Sanitize input
        prompt = SecurityMiddleware.sanitize_input(request.prompt, max_length=10000)

        if not prompt:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

        # Check rate limit if user is authenticated
        if user_id:
            # Calculate estimated tokens for the message
            message_tokens = RateLimitService.estimate_tokens(prompt)

            allowed, error_data, usage_info = await RateLimitService.check_rate_limit(
                user_id,
                request.model,
                message_tokens
            )
            if not allowed:
                # Return structured error for better frontend handling
                if isinstance(error_data, dict):
                    error_detail = {
                        **error_data,
                        "usage_info": usage_info,
                        "status": "limit_exceeded"
                    }
                else:
                    error_detail = {
                        "message": str(error_data),
                        "usage_info": usage_info,
                        "status": "limit_exceeded"
                    }
                raise HTTPException(status_code=429, detail=error_detail)

        # Get search context if enabled
        search_context = None
        if request.enable_search:
            search_context = await SearchService.search_web(prompt)

        # Get user memories and inject into context (if authenticated)
        memories_context = None
        if user_id:
            try:
                from services.memory_service import MemoryService
                memories_context = await MemoryService.format_memories_for_prompt(user_id)
                if memories_context:
                    print(f"🧠 Injecting {len(memories_context)} chars of user memories")
            except Exception as e:
                print(f"⚠️ Error getting memories (non-critical): {e}")

        # Build message list
        messages = []
        
        # Inject memories at the beginning if available
        if memories_context:
            messages.append({
                "role": "system",
                "content": memories_context
            })
        
        for msg in request.history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add user message with image if present
        if request.image:
            user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or "Analiza esta imagen"},
                    {"type": "image_url", "image_url": {"url": request.image}}
                ]
            }
        else:
            user_message = {"role": "user", "content": prompt}

        messages.append(user_message)

        # Get LLM response
        full_response = await LLMService.get_chat_completion(
            request.model,
            messages,
            search_context,
            request.special_mode # Add special_mode here
        )

        # Save to database if user is authenticated
        conversation_id = request.conversation_id
        if user_id and full_response:
            conversation = await ConversationService.save_chat(
                user_id=user_id,
                model=request.model,
                messages=messages,
                assistant_response=full_response,
                conversation_id=conversation_id
            )
            if conversation:
                conversation_id = conversation.get('id')

        return {
            "success": True,
            "response": full_response,
            "conversation_id": conversation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"🔴 Exception in chat endpoint: {error_msg}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/chats")
async def get_chats(user: dict = Depends(AuthMiddleware.require_auth)):
    """Get user's chat history."""
    try:
        chats = await ConversationService.list_conversations(user['id'])
        return {"success": True, "chats": chats}
    except Exception as e:
        print(f"❌ Error retrieving chats: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    req: Request
):
    """Handle chat requests with streaming responses."""
    try:
        # Get user if authenticated (optional)
        user = await AuthMiddleware.get_current_user(req)
        user_id = user['id'] if user else None

        # Sanitize input
        prompt = SecurityMiddleware.sanitize_input(request.prompt, max_length=10000)

        if not prompt:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

        # Check rate limit if user is authenticated
        if user_id:
            # Calculate estimated tokens for the message
            message_tokens = RateLimitService.estimate_tokens(prompt)

            allowed, error_data, usage_info = await RateLimitService.check_rate_limit(
                user_id,
                request.model,
                message_tokens
            )
            if not allowed:
                # Return structured error for better frontend handling
                if isinstance(error_data, dict):
                    error_detail = {
                        **error_data,
                        "usage_info": usage_info,
                        "status": "limit_exceeded"
                    }
                else:
                    error_detail = {
                        "message": str(error_data),
                        "usage_info": usage_info,
                        "status": "limit_exceeded"
                    }
                raise HTTPException(status_code=429, detail=error_detail)

        # Get search context if enabled
        search_context = None
        if request.enable_search:
            search_context = await SearchService.search_web(prompt)

        # Get user memories and inject into context (if authenticated)
        memories_context = None
        if user_id:
            try:
                from services.memory_service import MemoryService
                memories_context = await MemoryService.format_memories_for_prompt(user_id)
                if memories_context:
                    print(f"🧠 Injecting {len(memories_context)} chars of user memories into stream")
            except Exception as e:
                print(f"⚠️ Error getting memories (non-critical): {e}")

        # Build message list
        messages = []
        
        # Inject memories at the beginning if available
        if memories_context:
            messages.append({
                "role": "system",
                "content": memories_context
            })
        
        for msg in request.history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add user message with image if present
        if request.image:
            user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or "Analiza esta imagen"},
                    {"type": "image_url", "image_url": {"url": request.image}}
                ]
            }
        else:
            user_message = {"role": "user", "content": prompt}

        messages.append(user_message)

        async def generate():
            full_response = ""
            conversation_id = request.conversation_id

            try:
                async for chunk in LLMService.get_chat_completion_stream(
                    request.model,
                    messages,
                    search_context,
                    request.special_mode # Add special_mode here
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                # Save to database if user is authenticated
                if user_id and full_response:
                    # Crear una copia de messages para guardar, con content simplificado
                    messages_to_save = []
                    for msg in messages:
                        if isinstance(msg.get('content'), list):
                            # Extraer solo el texto del mensaje con imagen
                            text_content = ""
                            for content_part in msg['content']:
                                if content_part.get('type') == 'text':
                                    text_content = content_part.get('text', '')
                                    break
                            messages_to_save.append({
                                "role": msg['role'],
                                "content": text_content + " [imagen adjunta]"
                            })
                        else:
                            messages_to_save.append(msg)

                    conversation = await ConversationService.save_chat(
                        user_id=user_id,
                        model=request.model,
                        messages=messages_to_save,
                        assistant_response=full_response,
                        conversation_id=conversation_id
                    )
                    if conversation:
                        conversation_id = conversation.get('id')

                # Siempre enviar la respuesta final con conversation_id (si existe)
                yield f"data: {json.dumps({'conversation_id': conversation_id, 'done': True})}\n\n"

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                print(f"🔴 Exception in streaming: {error_msg}")
                yield f"data: {json.dumps({'error': error_msg})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"🔴 Exception in chat stream endpoint: {error_msg}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")