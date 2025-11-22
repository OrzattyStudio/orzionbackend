"""
Conversation service for managing chat conversations using Supabase
"""

from typing import Optional, List, Dict
from datetime import datetime
from services.supabase_service import get_supabase_service
from services.llm_service import LLMService

class ConversationService:

    @staticmethod
    async def create_conversation(
        user_id: str,
        title: str,
        model: str = "Orzion Pro"
    ) -> Optional[Dict]:
        """Create a new conversation."""
        supabase_service = get_supabase_service()
        try:
            conversation_data = {
                "user_id": user_id,
                "title": title,
                "model": model,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "is_archived": False
            }

            response = supabase_service.table("conversations").insert(conversation_data).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            print(f"❌ Error creating conversation: {e}")
            return None

    @staticmethod
    async def get_conversation(conversation_id: int, user_id: str = None) -> Optional[Dict]:
        """Get a specific conversation."""
        try:
            supabase = get_supabase_service()

            # Get conversation
            query = supabase.table('conversations').select('*').eq('id', conversation_id)
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.execute()

            if not response or not response.data or len(response.data) == 0:
                return None

            return response.data[0]
        except Exception as e:
            print(f"❌ Error getting conversation: {e}")
            return None

    @staticmethod
    async def list_conversations(
        user_id: str,
        include_archived: bool = False
    ) -> List[Dict]:
        """List all conversations for a user."""
        supabase_service = get_supabase_service()
        try:
            query = supabase_service.table("conversations").select("*").eq("user_id", user_id)

            if not include_archived:
                query = query.eq("is_archived", False)

            response = query.order("updated_at", desc=True).execute()
            return response.data if response.data else []

        except Exception as e:
            print(f"❌ Error listing conversations: {e}")
            return []

    @staticmethod
    async def update_conversation(
        conversation_id: int,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None
    ) -> Optional[Dict]:
        """Update conversation details."""
        supabase_service = get_supabase_service()
        try:
            update_data = {"updated_at": datetime.utcnow().isoformat()}

            if title is not None:
                update_data["title"] = title

            if is_archived is not None:
                update_data["is_archived"] = is_archived

            response = supabase_service.table("conversations").update(update_data).eq("id", conversation_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            print(f"❌ Error updating conversation: {e}")
            return None

    @staticmethod
    async def delete_conversation(conversation_id: int) -> bool:
        """Delete a conversation and all its messages."""
        supabase_service = get_supabase_service()
        try:
            response = supabase_service.table("conversations").delete().eq("id", conversation_id).execute()
            return response.data is not None

        except Exception as e:
            print(f"❌ Error deleting conversation: {e}")
            return False

    @staticmethod
    async def add_message(
        conversation_id: int,
        role: str,
        content: str,
        tokens_used: int = 0
    ) -> Optional[Dict]:
        """Add a message to a conversation."""
        supabase_service = get_supabase_service()
        try:
            message_data = {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "created_at": datetime.utcnow().isoformat(),
                "tokens_used": tokens_used
            }

            response = supabase_service.table("messages").insert(message_data).execute()

            if response.data and len(response.data) > 0:
                supabase_service.table("conversations").update({
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", conversation_id).execute()

                return response.data[0]
            return None

        except Exception as e:
            print(f"❌ Error adding message: {e}")
            return None

    @staticmethod
    async def get_messages(conversation_id: int) -> List[Dict]:
        """Get all messages for a conversation."""
        supabase_service = get_supabase_service()
        try:
            response = supabase_service.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
            return response.data if response.data else []

        except Exception as e:
            print(f"❌ Error getting messages: {e}")
            return []

    @staticmethod
    async def generate_smart_title(user_message: str, assistant_response: str) -> str:
        """Generate a smart title for the conversation using LLM."""
        try:
            # Extraer solo texto del mensaje del usuario si es un objeto
            if isinstance(user_message, dict):
                user_message = user_message.get('text', str(user_message))
            
            # Convertir a string si no lo es
            user_message = str(user_message)
            
            # Si el mensaje es muy corto, usarlo directamente
            if len(user_message) < 60:
                return user_message.strip()
            
            title_prompt = f"""Genera un título corto (máximo 6 palabras) para esta conversación. 
Solo responde con el título, sin comillas ni explicaciones adicionales.

Usuario: {user_message[:200]}
Asistente: {assistant_response[:200]}

Título:"""
            
            messages = [{"role": "user", "content": title_prompt}]
            
            # Usar Orzion Mini para velocidad
            title = await LLMService.get_chat_completion("Orzion Mini", messages)
            
            # Limpiar el título
            title = title.strip().strip('"').strip("'")
            
            # Limitar longitud
            if len(title) > 60:
                title = title[:60] + "..."
            
            # Si el título está vacío o contiene errores, usar fallback
            if not title or "error" in title.lower() or "404" in title:
                # Generar título simple basado en las primeras palabras del mensaje
                words = user_message.split()[:6]
                title = " ".join(words)
                if len(user_message) > len(title):
                    title += "..."
            
            return title if title else user_message[:60]
        except Exception as e:
            print(f"⚠️ Error generando título inteligente: {e}")
            # Fallback: usar las primeras palabras del mensaje del usuario
            try:
                words = str(user_message).split()[:6]
                fallback_title = " ".join(words)
                if len(str(user_message)) > len(fallback_title):
                    fallback_title += "..."
                return fallback_title
            except:
                return "Nueva conversación"

    @staticmethod
    async def save_chat(
        user_id: str,
        model: str,
        messages: list,
        assistant_response: str,
        conversation_id: Optional[int] = None
    ) -> Optional[Dict]:
        """Save a chat conversation to the database."""
        try:
            if not conversation_id:
                user_messages = [msg for msg in messages if msg['role'] == 'user']
                last_user_msg = user_messages[-1] if user_messages else None
                
                # Extraer contenido del mensaje (puede ser string o dict con imagen)
                user_content = ""
                if last_user_msg:
                    if isinstance(last_user_msg['content'], str):
                        user_content = last_user_msg['content']
                    elif isinstance(last_user_msg['content'], dict):
                        user_content = last_user_msg['content'].get('text', '')
                    else:
                        user_content = str(last_user_msg['content'])
                
                # Si no hay contenido, usar un título por defecto
                if not user_content:
                    user_content = "Nueva conversación"
                
                # Generar título inteligente
                print(f"🤔 Generando título inteligente para la conversación...")
                title = await ConversationService.generate_smart_title(user_content, assistant_response)

                print(f"📝 Creating new conversation with title: {title}")
                conversation = await ConversationService.create_conversation(
                    user_id=user_id,
                    title=title,
                    model=model
                )

                if not conversation:
                    print("❌ Failed to create conversation")
                    return None

                conversation_id = conversation['id']
                print(f"✅ Created conversation with ID: {conversation_id}")
            else:
                print(f"📝 Using existing conversation ID: {conversation_id}")

            user_messages = [msg for msg in messages if msg['role'] == 'user']
            if user_messages and conversation_id:
                last_user_message = user_messages[-1]
                print(f"💾 Saving user message to conversation {conversation_id}")
                await ConversationService.add_message(
                    conversation_id=int(conversation_id),
                    role='user',
                    content=last_user_message['content']
                )

            if conversation_id:
                print(f"💾 Saving assistant response to conversation {conversation_id}")
                await ConversationService.add_message(
                    conversation_id=int(conversation_id),
                    role='assistant',
                    content=assistant_response
                )

            # Extract memories from this conversation (DISABLED - solo recuerdos del chat actual)
            # Los recuerdos se extraen solo si el usuario lo solicita explícitamente
            # Para evitar recordar información de chats eliminados
            try:
                from services.memory_service import MemoryService
                # MEMORY EXTRACTION DISABLED BY DEFAULT
                # Solo se activa si el usuario pide "recuerda esto" o similar
                print(f"ℹ️ Memory extraction disabled (only per-conversation context)")
            except Exception as e:
                print(f"⚠️ Error in memory service: {e}")

            print(f"✅ Chat saved successfully to conversation {conversation_id}")
            return {'id': conversation_id}

        except Exception as e:
            print(f"❌ Error saving chat: {e}")
            import traceback
            traceback.print_exc()
            return None