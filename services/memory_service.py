"""
Memory service for managing user memories across conversations
"""

from typing import Optional, List, Dict
from datetime import datetime
from services.supabase_service import get_supabase_service
from services.llm_service import LLMService
import re

class MemoryService:
    
    @staticmethod
    async def extract_memories_from_conversation(
        user_id: str,
        user_message: str,
        assistant_response: str,
        conversation_id: int,
        message_id: int = None
    ) -> List[Dict]:
        """
        Extract memories from a conversation using pattern matching and LLM.
        Returns list of extracted memories.
        """
        try:
            # Quick rule-based extraction for common patterns
            rule_based_memories = MemoryService._extract_rule_based(user_message, assistant_response)
            
            # Use LLM to extract deeper insights (only if authenticated user)
            llm_memories = await MemoryService._extract_with_llm(user_message, assistant_response)
            
            # Combine and deduplicate
            all_memories = rule_based_memories + llm_memories
            
            # Save to database
            saved_memories = []
            for memory in all_memories:
                saved = await MemoryService.add_memory(
                    user_id=user_id,
                    memory_text=memory['text'],
                    memory_type=memory['type'],
                    importance_score=memory.get('importance', 0.5),
                    source_conversation_id=conversation_id,
                    source_message_id=message_id
                )
                if saved:
                    saved_memories.append(saved)
            
            return saved_memories
            
        except Exception as e:
            print(f"❌ Error extracting memories: {e}")
            return []
    
    @staticmethod
    def _extract_rule_based(user_message: str, assistant_response: str) -> List[Dict]:
        """Extract memories using pattern matching."""
        memories = []
        
        # Patterns for preferences
        preference_patterns = [
            r"prefiero\s+(.+?)(?:\.|,|$)",
            r"me gusta\s+(.+?)(?:\.|,|$)",
            r"no me gusta\s+(.+?)(?:\.|,|$)",
            r"quiero\s+(.+?)(?:\.|,|$)",
            r"necesito\s+(.+?)(?:\.|,|$)",
        ]
        
        # Patterns for facts
        fact_patterns = [
            r"soy\s+(.+?)(?:\.|,|$)",
            r"trabajo en\s+(.+?)(?:\.|,|$)",
            r"estudio\s+(.+?)(?:\.|,|$)",
            r"vivo en\s+(.+?)(?:\.|,|$)",
            r"tengo\s+(.+?)(?:\.|,|$)",
        ]
        
        # Extract preferences
        for pattern in preference_patterns:
            matches = re.findall(pattern, user_message.lower(), re.IGNORECASE)
            for match in matches[:2]:  # Limit to 2 per pattern
                memories.append({
                    'text': match.strip(),
                    'type': 'preference',
                    'importance': 0.7
                })
        
        # Extract facts
        for pattern in fact_patterns:
            matches = re.findall(pattern, user_message.lower(), re.IGNORECASE)
            for match in matches[:2]:  # Limit to 2 per pattern
                memories.append({
                    'text': match.strip(),
                    'type': 'fact',
                    'importance': 0.8
                })
        
        return memories[:5]  # Return max 5 rule-based memories
    
    @staticmethod
    async def _extract_with_llm(user_message: str, assistant_response: str) -> List[Dict]:
        """Use LLM to extract important memories."""
        try:
            # Create extraction prompt
            extraction_prompt = f"""Analiza la siguiente conversación y extrae SOLO información importante sobre el usuario que deba recordarse en futuras conversaciones.

USUARIO: {user_message}
ASISTENTE: {assistant_response}

Extrae información en estas categorías:
- FACT: Hechos sobre el usuario (trabajo, estudios, ubicación, etc.)
- PREFERENCE: Preferencias del usuario (gustos, disgustos, estilos)
- GOAL: Objetivos o metas mencionadas
- CONTEXT: Contexto relevante para futuras conversaciones

Responde SOLO con una lista JSON de máximo 3 recuerdos importantes:
[
  {{"type": "fact", "text": "texto del recuerdo", "importance": 0.8}},
  ...
]

Si no hay nada importante que recordar, responde: []
"""
            
            messages = [{"role": "user", "content": extraction_prompt}]
            
            # Use Orzion Mini for extraction (cheaper and faster)
            response = await LLMService.get_chat_completion(
                "Orzion Mini",
                messages,
                search_context=None,
                special_mode=None
            )
            
            # Parse JSON response
            import json
            try:
                # Extract JSON from response
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    memories = json.loads(json_match.group())
                    return memories[:3]  # Max 3 LLM memories
            except:
                pass
                
            return []
            
        except Exception as e:
            print(f"⚠️ LLM memory extraction failed: {e}")
            return []
    
    @staticmethod
    async def add_memory(
        user_id: str,
        memory_text: str,
        memory_type: str = 'fact',
        importance_score: float = 0.5,
        source_conversation_id: int = None,
        source_message_id: int = None
    ) -> Optional[Dict]:
        """Add a new memory for a user."""
        try:
            supabase = get_supabase_service()
            
            # Check for duplicates
            existing = await MemoryService.find_similar_memory(user_id, memory_text)
            if existing:
                # Update importance if higher
                if importance_score > existing.get('importance_score', 0):
                    return await MemoryService.update_memory(
                        existing['id'],
                        importance_score=importance_score
                    )
                return existing
            
            # Create new memory
            memory_data = {
                'user_id': user_id,
                'memory_text': memory_text,
                'memory_type': memory_type,
                'importance_score': min(max(importance_score, 0.0), 1.0),
                'source_conversation_id': source_conversation_id,
                'source_message_id': source_message_id,
                'is_active': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            response = supabase.table('user_memories').insert(memory_data).execute()
            
            if response.data and len(response.data) > 0:
                print(f"✅ Memory added: {memory_text[:50]}...")
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"❌ Error adding memory: {e}")
            return None
    
    @staticmethod
    async def find_similar_memory(user_id: str, memory_text: str) -> Optional[Dict]:
        """Find similar existing memory to avoid duplicates."""
        try:
            supabase = get_supabase_service()
            
            # Simple similarity check (contains or is contained)
            response = supabase.table('user_memories')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('is_active', True)\
                .execute()
            
            if response.data:
                memory_lower = memory_text.lower()
                for existing in response.data:
                    existing_lower = existing['memory_text'].lower()
                    # Check if texts are very similar
                    if (memory_lower in existing_lower or 
                        existing_lower in memory_lower):
                        return existing
            
            return None
            
        except Exception as e:
            print(f"❌ Error finding similar memory: {e}")
            return None
    
    @staticmethod
    async def get_active_memories(
        user_id: str,
        limit: int = 10,
        memory_type: str = None
    ) -> List[Dict]:
        """Get active memories for a user, sorted by importance and recency."""
        try:
            supabase = get_supabase_service()
            
            query = supabase.table('user_memories')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('is_active', True)
            
            if memory_type:
                query = query.eq('memory_type', memory_type)
            
            response = query\
                .order('importance_score', desc=True)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"❌ Error getting memories: {e}")
            return []
    
    @staticmethod
    async def get_all_memories(user_id: str, include_inactive: bool = False) -> List[Dict]:
        """Get all memories for a user."""
        try:
            supabase = get_supabase_service()
            
            query = supabase.table('user_memories')\
                .select('*')\
                .eq('user_id', user_id)
            
            if not include_inactive:
                query = query.eq('is_active', True)
            
            response = query\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"❌ Error getting all memories: {e}")
            return []
    
    @staticmethod
    async def update_memory(
        memory_id: int,
        memory_text: str = None,
        importance_score: float = None,
        is_active: bool = None
    ) -> Optional[Dict]:
        """Update a memory."""
        try:
            supabase = get_supabase_service()
            
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            
            if memory_text is not None:
                update_data['memory_text'] = memory_text
            if importance_score is not None:
                update_data['importance_score'] = min(max(importance_score, 0.0), 1.0)
            if is_active is not None:
                update_data['is_active'] = is_active
            
            response = supabase.table('user_memories')\
                .update(update_data)\
                .eq('id', memory_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"❌ Error updating memory: {e}")
            return None
    
    @staticmethod
    async def delete_memory(memory_id: int) -> bool:
        """Delete a memory (actually just deactivate)."""
        return await MemoryService.update_memory(memory_id, is_active=False) is not None
    
    @staticmethod
    async def format_memories_for_prompt(user_id: str) -> str:
        """Format active memories into a string for LLM context."""
        try:
            memories = await MemoryService.get_active_memories(user_id, limit=10)
            
            if not memories:
                return ""
            
            # Group by type
            facts = []
            preferences = []
            goals = []
            context = []
            
            for memory in memories:
                text = memory['memory_text']
                mem_type = memory['memory_type']
                
                if mem_type == 'fact':
                    facts.append(text)
                elif mem_type == 'preference':
                    preferences.append(text)
                elif mem_type == 'goal':
                    goals.append(text)
                else:
                    context.append(text)
            
            # Build formatted string
            formatted = "=== INFORMACIÓN DEL USUARIO ===\n"
            
            if facts:
                formatted += "\n📋 DATOS:\n"
                for fact in facts:
                    formatted += f"- {fact}\n"
            
            if preferences:
                formatted += "\n⭐ PREFERENCIAS:\n"
                for pref in preferences:
                    formatted += f"- {pref}\n"
            
            if goals:
                formatted += "\n🎯 OBJETIVOS:\n"
                for goal in goals:
                    formatted += f"- {goal}\n"
            
            if context:
                formatted += "\n💡 CONTEXTO:\n"
                for ctx in context:
                    formatted += f"- {ctx}\n"
            
            formatted += "\n=== FIN DE INFORMACIÓN ===\n"
            
            return formatted
            
        except Exception as e:
            print(f"❌ Error formatting memories: {e}")
            return ""
