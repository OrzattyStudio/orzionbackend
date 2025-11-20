"""
Rate Limit Service - Manages usage limits with Supabase persistence
Implements daily message and token limits per plan
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from services.supabase_service import get_supabase_service
from services.security_logger import SecurityLogger


class RateLimitService:
    """
    Service for managing usage quotas and rate limits.
    Uses Supabase for persistent storage (survives restarts).
    """
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for a text message.
        Approximation: ~1 token per 4 characters (common for English text).
        This is a rough estimate; actual token count may vary by model.
        """
        if not text:
            return 0
        # Rough approximation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)
    
    # Default limits organized by Plan and Model
    DEFAULT_LIMITS = {
        "Free": {
            "Orzion Mini": {
                "messages_daily": 200,
                "tokens_per_message": 6000,
                "tokens_daily": 30000
            },
            "Orzion Turbo": {
                "messages_daily": 100,
                "tokens_per_message": 3000,
                "tokens_daily": 20000
            },
            "Orzion Pro": {
                "messages_daily": 50,
                "tokens_per_message": 2000,
                "tokens_daily": 10000
            }
        },
        "Pro": {
            "Orzion Mini": {
                "messages_daily": 500,
                "tokens_per_message": 10000,
                "tokens_daily": 50000
            },
            "Orzion Turbo": {
                "messages_daily": 300,
                "tokens_per_message": 6000,
                "tokens_daily": 25000
            },
            "Orzion Pro": {
                "messages_daily": 150,
                "tokens_per_message": 5000,
                "tokens_daily": 20000
            }
        },
        "Teams": {
            "Orzion Mini": {
                "messages_daily": -1,
                "tokens_per_message": 50000,
                "tokens_daily": 256000
            },
            "Orzion Turbo": {
                "messages_daily": -1,
                "tokens_per_message": 30000,
                "tokens_daily": 128000
            },
            "Orzion Pro": {
                "messages_daily": 1000,
                "tokens_per_message": 40000,
                "tokens_daily": 50000
            }
        }
    }
    
    @staticmethod
    async def get_user_limits(user_id: str, plan_name: str = None) -> Dict[str, Dict]:
        """
        Get user's limits for all models based on their plan.
        Returns a dict with model names as keys and their limits as values.
        """
        try:
            if not plan_name:
                from services.subscription_service import SubscriptionService
                plan_info = await SubscriptionService.get_user_active_plan(user_id)
                plan_name = plan_info.get("plan_name", "Free")
            
            if plan_name not in RateLimitService.DEFAULT_LIMITS:
                plan_name = "Free"
            
            all_limits = {}
            for model in RateLimitService.DEFAULT_LIMITS[plan_name]:
                limits = RateLimitService.DEFAULT_LIMITS[plan_name][model].copy()
                
                supabase = get_supabase_service()
                if supabase:
                    response = supabase.table('model_usage_quota')\
                        .select('bonus_messages_daily, bonus_tokens_daily')\
                        .eq('user_id', user_id)\
                        .eq('model', model)\
                        .execute()
                    
                    if response.data and len(response.data) > 0:
                        bonus_data = response.data[0]
                        bonus_messages = bonus_data.get('bonus_messages_daily', 0)
                        bonus_tokens = bonus_data.get('bonus_tokens_daily', 0)
                        
                        if limits["messages_daily"] != -1:
                            limits["messages_daily"] += bonus_messages
                        limits["tokens_daily"] += bonus_tokens
                
                all_limits[model] = limits
            
            return all_limits
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="RateLimitService.get_user_limits",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return RateLimitService.DEFAULT_LIMITS.get("Free", {})
    
    @staticmethod
    async def get_current_usage(user_id: str, model: str) -> Dict[str, int]:
        """Get current daily usage (messages and tokens) for a specific model"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return {"messages": 0, "tokens": 0}
            
            today = datetime.utcnow().date()
            
            response = supabase.table('model_usage_daily')\
                .select('messages_used, tokens_used')\
                .eq('user_id', user_id)\
                .eq('model', model)\
                .eq('date', today.isoformat())\
                .execute()
            
            if response.data and len(response.data) > 0:
                return {
                    "messages": response.data[0].get('messages_used', 0),
                    "tokens": response.data[0].get('tokens_used', 0)
                }
            return {"messages": 0, "tokens": 0}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="RateLimitService.get_current_usage",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"messages": 0, "tokens": 0}
    
    @staticmethod
    async def check_rate_limit(user_id: str, model: str, message_tokens: int = 0) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if user has exceeded daily rate limits for the model.
        Uses daily limits from model_usage_daily table.
        
        Args:
            user_id: User ID
            model: Model name (Orzion Pro, Orzion Turbo, Orzion Mini)
            message_tokens: Estimated token count for the current message
            
        Returns: (allowed: bool, error_message: str or None, usage_info: dict or None)
        """
        try:
            user_limits = await RateLimitService.get_user_limits(user_id)
            model_limits = user_limits.get(model, {})
            
            if not model_limits:
                return True, None, None
            
            messages_daily_limit = model_limits.get('messages_daily', 0)
            tokens_per_message_limit = model_limits.get('tokens_per_message', 0)
            tokens_daily_limit = model_limits.get('tokens_daily', 0)
            
            if tokens_per_message_limit != -1 and message_tokens > tokens_per_message_limit:
                return (False, f"Mensaje excede el límite de {tokens_per_message_limit} tokens. Tu mensaje tiene {message_tokens} tokens.", None)
            
            supabase = get_supabase_service()
            if not supabase:
                return True, None, None
                
            today = datetime.utcnow().date()
            response = supabase.table('model_usage_daily')\
                .select('messages_used, tokens_used')\
                .eq('user_id', user_id)\
                .eq('model', model)\
                .eq('date', today.isoformat())\
                .execute()
            
            messages_used = response.data[0]['messages_used'] if response.data and len(response.data) > 0 else 0
            tokens_used = response.data[0]['tokens_used'] if response.data and len(response.data) > 0 else 0
            
            usage_info = {
                "messages": {
                    "current": messages_used,
                    "limit": messages_daily_limit,
                    "unlimited": messages_daily_limit == -1
                },
                "tokens": {
                    "current": tokens_used,
                    "limit": tokens_daily_limit,
                    "unlimited": tokens_daily_limit == -1,
                    "per_message_limit": tokens_per_message_limit
                },
                "model": model
            }
            
            if messages_daily_limit != -1 and messages_used >= messages_daily_limit:
                time_until_reset = RateLimitService._get_time_until_reset()
                return (False, {
                    "type": "messages_limit",
                    "model": model,
                    "limit": messages_daily_limit,
                    "used": messages_used,
                    "reset_time": time_until_reset,
                    "message": f"Has alcanzado el límite diario de {messages_daily_limit} mensajes para {model}."
                }, usage_info)
            
            if tokens_daily_limit != -1 and (tokens_used + message_tokens) > tokens_daily_limit:
                time_until_reset = RateLimitService._get_time_until_reset()
                return (False, {
                    "type": "tokens_limit",
                    "model": model,
                    "limit": tokens_daily_limit,
                    "used": tokens_used,
                    "reset_time": time_until_reset,
                    "message": f"Has alcanzado el límite diario de {tokens_daily_limit} tokens para {model}."
                }, usage_info)
            
            increment_response = await supabase.rpc('increment_daily_usage', {
                'p_user_id': user_id,
                'p_model': model,
                'p_date': today.isoformat(),
                'p_messages': 1,
                'p_tokens': message_tokens
            }).execute()
            
            if increment_response.data:
                new_messages = increment_response.data.get('messages_used', messages_used + 1)
                new_tokens = increment_response.data.get('tokens_used', tokens_used + message_tokens)
                
                usage_info = {
                    "messages": {
                        "current": new_messages,
                        "limit": messages_daily_limit,
                        "unlimited": messages_daily_limit == -1
                    },
                    "tokens": {
                        "current": new_tokens,
                        "limit": tokens_daily_limit,
                        "unlimited": tokens_daily_limit == -1,
                        "per_message_limit": tokens_per_message_limit
                    },
                    "model": model
                }
            
            return (True, None, usage_info)
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="RateLimitService.check_rate_limit",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return True, None, None
    
    @staticmethod
    def _get_time_until_reset() -> str:
        """Get human-readable time until daily limits reset (midnight UTC)"""
        now = datetime.utcnow()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        delta = tomorrow - now
        hours = int(delta.total_seconds() / 3600)
        minutes = int((delta.total_seconds() % 3600) / 60)
        
        if hours > 0:
            return f"{hours} horas y {minutes} minutos"
        else:
            return f"{minutes} minutos"
    
    @staticmethod
    async def get_usage_summary(user_id: str) -> Dict:
        """
        Get complete usage summary for all models.
        Useful for displaying in frontend.
        """
        try:
            from services.subscription_service import SubscriptionService
            plan_info = await SubscriptionService.get_user_active_plan(user_id)
            plan_name = plan_info.get("plan_name", "Free")
            
            user_limits = await RateLimitService.get_user_limits(user_id, plan_name)
            
            summary = {
                "plan": plan_name,
                "models": {}
            }
            
            for model, limits in user_limits.items():
                usage = await RateLimitService.get_current_usage(user_id, model)
                
                messages_limit = limits.get("messages_daily", 0)
                tokens_limit = limits.get("tokens_daily", 0)
                messages_used = usage.get("messages", 0)
                tokens_used = usage.get("tokens", 0)
                
                summary["models"][model] = {
                    "limits": {
                        "messages_daily": messages_limit,
                        "tokens_per_message": limits.get("tokens_per_message", 0),
                        "tokens_daily": tokens_limit
                    },
                    "usage": {
                        "messages": messages_used,
                        "tokens": tokens_used
                    },
                    "remaining": {
                        "messages": -1 if messages_limit == -1 else max(0, messages_limit - messages_used),
                        "tokens": max(0, tokens_limit - tokens_used)
                    },
                    "percentage_used": {
                        "messages": 0 if messages_limit == -1 else int((messages_used / messages_limit) * 100) if messages_limit > 0 else 0,
                        "tokens": int((tokens_used / tokens_limit) * 100) if tokens_limit > 0 else 0
                    },
                    "unlimited_messages": messages_limit == -1
                }
            
            return summary
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="RateLimitService.get_usage_summary",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"plan": "Free", "models": {}}
    
    @staticmethod
    async def cleanup_old_daily_records():
        """Clean up old daily usage records (called periodically by background task)"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return
            
            # Call Supabase RPC function to cleanup (older than 30 days)
            supabase.rpc('cleanup_old_daily_usage').execute()
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="RateLimitService.cleanup_old_daily_records",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )


# Singleton instance
rate_limiter = RateLimitService()
