"""
Subscription Service - Manages user subscription plans
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from services.supabase_service import get_supabase_service
from services.security_logger import SecurityLogger


class SubscriptionService:
    """Service for managing user subscriptions and plans"""
    
    @staticmethod
    async def get_user_active_plan(user_id: str) -> Dict[str, Any]:
        """
        Get user's currently active subscription plan.
        Returns the highest priority active plan.
        """
        try:
            supabase = get_supabase_service()
            if not supabase:
                return {
                    "plan_name": "Free",
                    "status": "active",
                    "expires_at": None
                }
            
            # Use RPC function to get active plan
            result = supabase.rpc('get_user_active_plan', {
                'p_user_id': user_id
            }).execute()
            
            plan_name = result.data if result.data else "Free"
            
            # Get subscription details
            response = supabase.table('user_subscriptions')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('plan_name', plan_name)\
                .eq('status', 'active')\
                .maybe_single()\
                .execute()
            
            if response.data:
                return {
                    "plan_name": response.data['plan_name'],
                    "status": response.data['status'],
                    "expires_at": response.data.get('expires_at'),
                    "starts_at": response.data.get('starts_at'),
                    "payment_method": response.data.get('payment_method')
                }
            
            return {
                "plan_name": "Free",
                "status": "active",
                "expires_at": None
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="SubscriptionService.get_user_active_plan",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "plan_name": "Free",
                "status": "active",
                "expires_at": None
            }
    
    @staticmethod
    async def get_all_plans() -> list:
        """Get all available subscription plans"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return []
            
            response = supabase.table('subscription_plans')\
                .select('*')\
                .order('price_monthly')\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="SubscriptionService.get_all_plans",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return []
    
    @staticmethod
    async def get_user_subscriptions(user_id: str) -> list:
        """Get all subscriptions for a user (active and expired)"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return []
            
            response = supabase.table('user_subscriptions')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="SubscriptionService.get_user_subscriptions",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return []
    
    @staticmethod
    async def get_subscription_history(user_id: str) -> list:
        """Get subscription change history for a user"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return []
            
            response = supabase.table('subscription_history')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(50)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="SubscriptionService.get_subscription_history",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return []
    
    @staticmethod
    async def grant_subscription(
        user_id: str,
        plan_name: str,
        duration_days: int,
        payment_method: str = 'referral_bonus',
        payment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Grant or extend a subscription for a user.
        Uses the grant_subscription_time RPC function.
        """
        try:
            supabase = get_supabase_service()
            if not supabase:
                return {
                    "success": False,
                    "error": "Database service unavailable"
                }
            
            result = supabase.rpc('grant_subscription_time', {
                'p_user_id': user_id,
                'p_plan_name': plan_name,
                'p_duration_days': duration_days,
                'p_reason': f'Granted via {payment_method}'
            }).execute()
            
            if result.data and result.data.get('success'):
                SecurityLogger.log_security_event(
                    event_type="SUBSCRIPTION_GRANTED",
                    user_id=user_id,
                    details={
                        "plan_name": plan_name,
                        "duration_days": duration_days,
                        "payment_method": payment_method,
                        "payment_id": payment_id
                    },
                    correlation_id=SecurityLogger.generate_correlation_id()
                )
                
                return {
                    "success": True,
                    "subscription_id": result.data.get('subscription_id'),
                    "expires_at": result.data.get('expires_at')
                }
            
            return {
                "success": False,
                "error": result.data.get('error', 'Unknown error') if result.data else 'Failed to grant subscription'
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="SubscriptionService.grant_subscription",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def cancel_subscription(user_id: str, plan_name: str) -> Dict[str, Any]:
        """Cancel a user's subscription"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return {
                    "success": False,
                    "error": "Database service unavailable"
                }
            
            now = datetime.utcnow()
            
            # Update subscription status to cancelled
            supabase.table('user_subscriptions')\
                .update({
                    "status": "cancelled",
                    "cancelled_at": now.isoformat(),
                    "updated_at": now.isoformat()
                })\
                .eq('user_id', user_id)\
                .eq('plan_name', plan_name)\
                .eq('status', 'active')\
                .execute()
            
            # Log cancellation
            supabase.table('subscription_history').insert({
                "user_id": user_id,
                "action": "cancelled",
                "from_plan": plan_name,
                "reason": "User requested cancellation"
            }).execute()
            
            SecurityLogger.log_security_event(
                event_type="SUBSCRIPTION_CANCELLED",
                user_id=user_id,
                details={"plan_name": plan_name},
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {
                "success": True,
                "message": "Subscription cancelled successfully"
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="SubscriptionService.cancel_subscription",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
