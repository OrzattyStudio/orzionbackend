from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field
from middleware.auth_middleware import AuthMiddleware
from services.supabase_service import get_supabase_service
from services.security_logger import SecurityLogger


router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


class FeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    message: str = Field(..., min_length=1, max_length=1000, description="Feedback message")
    category: str = Field(default="general", description="Feedback category")


@router.post("/submit")
async def submit_feedback(
    feedback: FeedbackRequest,
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Submit user feedback.
    Categories: general, bug, feature, improvement, other
    """
    try:
        user_id = current_user["id"]
        user_email = current_user.get("email", "unknown")

        supabase = get_supabase_service()
        if not supabase:
            raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible")

        feedback_data = {
            "user_id": user_id,
            "user_email": user_email,
            "rating": feedback.rating,
            "message": feedback.message,
            "category": feedback.category,
            "created_at": datetime.utcnow().isoformat()
        }

        # Insert feedback into database
        supabase.table('user_feedback').insert(feedback_data).execute()

        # Log the event
        SecurityLogger.log_security_event(
            event_type="FEEDBACK_SUBMITTED",
            user_id=user_id,
            details={
                "rating": feedback.rating, 
                "category": feedback.category
            },
            correlation_id=SecurityLogger.generate_correlation_id()
        )

        # Return success response
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "¡Gracias por tu feedback! Lo apreciamos mucho."
            }
        )

    except Exception as e:
        error_msg = str(e)
        SecurityLogger.log_api_error(
            api_name="POST /api/feedback/submit",
            error_message=error_msg,
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        
        # Provide more specific error message
        if "user_feedback" in error_msg.lower() or "relation" in error_msg.lower():
            raise HTTPException(
                status_code=500, 
                detail="La tabla de feedback no está configurada. Por favor contacta al administrador."
            )
        elif "supabase" in error_msg.lower() or "database" in error_msg.lower():
            raise HTTPException(
                status_code=500, 
                detail="Error de conexión con la base de datos. Por favor intenta más tarde."
            )
        else:
            raise HTTPException(status_code=500, detail=f"Error al enviar feedback: {error_msg}")


@router.get("/my-stats")
async def get_my_feedback_stats(
    current_user: Dict = Depends(AuthMiddleware.require_auth)
) -> Dict[str, Any]:
    """
    Get feedback statistics for current user only.
    Returns user's own feedback history.
    """
    try:
        user_id = current_user["id"]
        supabase = get_supabase_service()
        if not supabase:
            raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible")

        response = supabase.table('user_feedback')\
            .select('rating, category, created_at')\
            .eq('user_id', user_id)\
            .execute()

        if not response.data:
            return {
                "success": True,
                "total_feedback": 0,
                "average_rating": 0,
                "by_category": {},
                "recent_feedback": []
            }

        total = len(response.data)
        avg_rating = sum(f['rating'] for f in response.data) / total if total > 0 else 0

        by_category = {}
        for f in response.data:
            cat = f.get('category', 'general')
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "success": True,
            "total_feedback": total,
            "average_rating": round(avg_rating, 2),
            "by_category": by_category,
            "recent_feedback": response.data[:10]
        }

    except Exception as e:
        SecurityLogger.log_api_error(
            api_name="GET /api/feedback/my-stats",
            error_message=str(e),
            correlation_id=SecurityLogger.generate_correlation_id()
        )
        raise HTTPException(status_code=500, detail="Error al obtener estadísticas")
