"""
Memory routes for managing user memories
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from services.memory_service import MemoryService
from middleware.auth_middleware import AuthMiddleware

router = APIRouter()

class AddMemoryRequest(BaseModel):
    memory_text: str
    memory_type: str = 'fact'
    importance_score: float = 0.5

class UpdateMemoryRequest(BaseModel):
    memory_text: Optional[str] = None
    importance_score: Optional[float] = None
    is_active: Optional[bool] = None

@router.get("/memories")
async def get_memories(
    req: Request,
    include_inactive: bool = False
):
    """Get all memories for the authenticated user."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        user_id = user['id']
        
        memories = await MemoryService.get_all_memories(user_id, include_inactive)
        
        return {
            "success": True,
            "memories": memories,
            "count": len(memories)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/memories/active")
async def get_active_memories(
    req: Request,
    limit: int = 10,
    memory_type: Optional[str] = None
):
    """Get active memories for the authenticated user."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        user_id = user['id']
        
        memories = await MemoryService.get_active_memories(user_id, limit, memory_type)
        
        return {
            "success": True,
            "memories": memories,
            "count": len(memories)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting active memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/memories")
async def add_memory(
    request: AddMemoryRequest,
    req: Request
):
    """Add a new memory for the authenticated user."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        user_id = user['id']
        
        memory = await MemoryService.add_memory(
            user_id=user_id,
            memory_text=request.memory_text,
            memory_type=request.memory_type,
            importance_score=request.importance_score
        )
        
        if not memory:
            raise HTTPException(status_code=500, detail="Failed to add memory")
        
        return {
            "success": True,
            "memory": memory
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error adding memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/memories/{memory_id}")
async def update_memory(
    memory_id: int,
    request: UpdateMemoryRequest,
    req: Request
):
    """Update a memory (must belong to authenticated user)."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        
        # Verify memory belongs to user
        supabase = get_supabase_service()
        from services.supabase_service import get_supabase_service
        
        existing = supabase.table('user_memories')\
            .select('*')\
            .eq('id', memory_id)\
            .eq('user_id', user['id'])\
            .execute()
        
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        memory = await MemoryService.update_memory(
            memory_id=memory_id,
            memory_text=request.memory_text,
            importance_score=request.importance_score,
            is_active=request.is_active
        )
        
        if not memory:
            raise HTTPException(status_code=500, detail="Failed to update memory")
        
        return {
            "success": True,
            "memory": memory
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: int,
    req: Request
):
    """Delete (deactivate) a memory."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        
        # Verify memory belongs to user
        from services.supabase_service import get_supabase_service
        supabase = get_supabase_service()
        
        existing = supabase.table('user_memories')\
            .select('*')\
            .eq('id', memory_id)\
            .eq('user_id', user['id'])\
            .execute()
        
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        success = await MemoryService.delete_memory(memory_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete memory")
        
        return {
            "success": True,
            "message": "Memory deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/memories/formatted")
async def get_formatted_memories(req: Request):
    """Get memories formatted for LLM context."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        user_id = user['id']
        
        formatted = await MemoryService.format_memories_for_prompt(user_id)
        
        return {
            "success": True,
            "formatted": formatted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error formatting memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/memories/explicit")
async def get_explicit_memories(
    req: Request,
    limit: int = 20
):
    """Get memories that were explicitly requested by the user."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        user_id = user['id']
        
        memories = await MemoryService.get_active_memories(
            user_id, 
            limit=limit, 
            memory_type='explicit_user_request'
        )
        
        return {
            "success": True,
            "memories": memories,
            "count": len(memories)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting explicit memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/memories/clear")
async def clear_all_memories(req: Request):
    """Clear all memories for the authenticated user."""
    try:
        user = await AuthMiddleware.get_current_user(req, required=True)
        user_id = user['id']
        
        from services.supabase_service import get_supabase_service
        supabase = get_supabase_service()
        
        # Deactivate all memories
        response = supabase.table('user_memories')\
            .update({'is_active': False})\
            .eq('user_id', user_id)\
            .execute()
        
        return {
            "success": True,
            "message": "All memories cleared successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error clearing memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
