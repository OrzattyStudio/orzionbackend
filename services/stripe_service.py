"""
Stripe Service - Complete integration with Stripe for subscription payments
Handles customer creation, subscriptions, webhooks, and billing
"""
from typing import Dict, Any, Optional, List
from services.security_logger import SecurityLogger, SecurityEventType
from services.subscription_service import SubscriptionService
from config import Config
import stripe
import os
from datetime import datetime


class StripeService:
    """Service for handling Stripe payment integration"""
    
    _configured = False
    
    @staticmethod
    def configure():
        """Configure Stripe with API key"""
        if StripeService._configured:
            return
        
        api_key = os.getenv("STRIPE_SECRET_KEY", Config.STRIPE_SECRET_KEY)
        
        if not api_key:
            SecurityLogger.log_api_error(
                api_name="StripeService.configure",
                error_message="Stripe not configured - missing STRIPE_SECRET_KEY",
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return
        
        stripe.api_key = api_key
        StripeService._configured = True
    
    @staticmethod
    def is_configured() -> bool:
        """Check if Stripe credentials are configured"""
        StripeService.configure()
        return StripeService._configured
    
    @staticmethod
    def get_client_config() -> Dict[str, str]:
        """Get Stripe publishable key for frontend"""
        publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY", Config.STRIPE_PUBLISHABLE_KEY)
        
        if not publishable_key:
            SecurityLogger.log_api_error(
                api_name="StripeService.get_client_config",
                error_message="Stripe not configured - missing STRIPE_PUBLISHABLE_KEY",
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "publishable_key": "",
                "configured": False
            }
        
        return {
            "publishable_key": publishable_key,
            "configured": True
        }
    
    @staticmethod
    async def create_or_get_customer(user_id: str, email: str, name: Optional[str] = None) -> Optional[str]:
        """
        Create or retrieve a Stripe customer for a user.
        Returns the Stripe customer ID or None if failed.
        """
        if not StripeService.is_configured():
            return None
        
        try:
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return None
            
            # Check if customer already exists in our database
            result = supabase.table('stripe_customers')\
                .select('stripe_customer_id')\
                .eq('user_id', user_id)\
                .single()\
                .execute()
            
            if result.data and result.data.get('stripe_customer_id'):
                return result.data['stripe_customer_id']
            
            # Create new Stripe customer
            customer_data = {
                "email": email,
                "metadata": {
                    "user_id": user_id
                }
            }
            
            if name:
                customer_data["name"] = name
            
            customer = stripe.Customer.create(**customer_data)
            
            # Save to database
            supabase.table('stripe_customers').insert({
                "user_id": user_id,
                "stripe_customer_id": customer.id,
                "email": email
            }).execute()
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=user_id,
                details={
                    "action": "stripe_customer_created",
                    "customer_id": customer.id
                },
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return customer.id
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.create_or_get_customer",
                error_message=str(e),
                user_id=user_id,
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return None
    
    @staticmethod
    def get_price_id(plan_name: str) -> Optional[str]:
        """Get Stripe price ID for a plan"""
        price_ids = {
            "Pro": os.getenv("STRIPE_PRICE_PRO_MONTHLY", Config.STRIPE_PRICE_PRO_MONTHLY),
            "Teams": os.getenv("STRIPE_PRICE_TEAMS_MONTHLY", Config.STRIPE_PRICE_TEAMS_MONTHLY)
        }
        return price_ids.get(plan_name)
    
    @staticmethod
    async def create_checkout_session(
        user_id: str,
        email: str,
        plan_name: str,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session for a subscription.
        Returns session ID and URL or error.
        """
        if not StripeService.is_configured():
            return {
                "success": False,
                "error": "Stripe not configured. Add STRIPE_SECRET_KEY to environment."
            }
        
        try:
            # Get price ID for the plan
            price_id = StripeService.get_price_id(plan_name)
            
            if not price_id:
                return {
                    "success": False,
                    "error": f"Invalid plan: {plan_name}"
                }
            
            # Create or get customer
            customer_id = await StripeService.create_or_get_customer(user_id, email)
            
            if not customer_id:
                return {
                    "success": False,
                    "error": "Failed to create customer"
                }
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': user_id,
                    'plan_name': plan_name
                },
                allow_promotion_codes=True,
                billing_address_collection='auto'
            )
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=user_id,
                details={
                    "action": "checkout_session_created",
                    "plan_name": plan_name,
                    "session_id": session.id
                },
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {
                "success": True,
                "session_id": session.id,
                "url": session.url
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.create_checkout_session",
                error_message=str(e),
                user_id=user_id,
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def create_portal_session(user_id: str, return_url: str) -> Dict[str, Any]:
        """
        Create a Stripe billing portal session for subscription management.
        Returns portal URL or error.
        """
        if not StripeService.is_configured():
            return {
                "success": False,
                "error": "Stripe not configured"
            }
        
        try:
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Get customer ID
            result = supabase.table('stripe_customers')\
                .select('stripe_customer_id')\
                .eq('user_id', user_id)\
                .single()\
                .execute()
            
            if not result.data or not result.data.get('stripe_customer_id'):
                return {
                    "success": False,
                    "error": "No Stripe customer found"
                }
            
            customer_id = result.data['stripe_customer_id']
            
            # Create portal session
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            
            return {
                "success": True,
                "url": session.url
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.create_portal_session",
                error_message=str(e),
                user_id=user_id,
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def cancel_subscription(user_id: str, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a Stripe subscription.
        Subscription will remain active until the end of the billing period.
        """
        if not StripeService.is_configured():
            return {
                "success": False,
                "error": "Stripe not configured"
            }
        
        try:
            # Cancel at period end (don't cancel immediately)
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=user_id,
                details={
                    "action": "subscription_cancelled",
                    "subscription_id": subscription_id,
                    "cancel_at": subscription.cancel_at
                },
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {
                "success": True,
                "message": "Subscription will be cancelled at the end of the billing period",
                "cancel_at": subscription.cancel_at
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.cancel_subscription",
                error_message=str(e),
                user_id=user_id,
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def get_subscription_status(user_id: str) -> Dict[str, Any]:
        """
        Get the current Stripe subscription status for a user.
        """
        try:
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Get active Stripe subscription
            result = supabase.table('stripe_subscriptions')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('status', 'active')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            if result.data and len(result.data) > 0:
                subscription = result.data[0]
                return {
                    "success": True,
                    "has_subscription": True,
                    "subscription": subscription
                }
            
            return {
                "success": True,
                "has_subscription": False,
                "subscription": None
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.get_subscription_status",
                error_message=str(e),
                user_id=user_id,
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def get_billing_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get billing history for a user from Stripe.
        Returns list of payment records.
        """
        try:
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return []
            
            # Get payment history from database
            result = supabase.table('stripe_payments')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.get_billing_history",
                error_message=str(e),
                user_id=user_id,
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return []
    
    @staticmethod
    async def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events.
        Verifies signature and processes events.
        """
        if not StripeService.is_configured():
            return {
                "success": False,
                "error": "Stripe not configured"
            }
        
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", Config.STRIPE_WEBHOOK_SECRET)
        
        if not webhook_secret:
            SecurityLogger.log_api_error(
                api_name="StripeService.handle_webhook",
                error_message="Webhook secret not configured",
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": "Webhook secret not configured"
            }
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            
            # Handle different event types
            event_type = event['type']
            
            if event_type == 'checkout.session.completed':
                return await StripeService._handle_checkout_completed(event['data']['object'])
            
            elif event_type == 'invoice.paid':
                return await StripeService._handle_invoice_paid(event['data']['object'])
            
            elif event_type == 'invoice.payment_failed':
                return await StripeService._handle_payment_failed(event['data']['object'])
            
            elif event_type == 'customer.subscription.updated':
                return await StripeService._handle_subscription_updated(event['data']['object'])
            
            elif event_type == 'customer.subscription.deleted':
                return await StripeService._handle_subscription_deleted(event['data']['object'])
            
            else:
                # Unhandled event type
                return {
                    "success": True,
                    "message": f"Unhandled event type: {event_type}"
                }
            
        except stripe.error.SignatureVerificationError as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.handle_webhook",
                error_message=f"Invalid signature: {str(e)}",
                correlation_id=SecurityLogger.generate_correlation_id(),
                severity="ERROR"
            )
            return {
                "success": False,
                "error": "Invalid signature"
            }
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService.handle_webhook",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _handle_checkout_completed(session) -> Dict[str, Any]:
        """Handle successful checkout"""
        try:
            user_id = session.get('metadata', {}).get('user_id')
            plan_name = session.get('metadata', {}).get('plan_name')
            
            if not user_id or not plan_name:
                return {"success": False, "error": "Missing metadata"}
            
            # Grant subscription (30 days)
            from services.subscription_service import SubscriptionService
            result = await SubscriptionService.grant_subscription(
                user_id=user_id,
                plan_name=plan_name,
                duration_days=30,
                payment_method='stripe',
                payment_id=session.get('id')
            )
            
            # Record payment
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if supabase:
                supabase.table('stripe_payments').insert({
                    'user_id': user_id,
                    'stripe_payment_id': session.get('payment_intent'),
                    'stripe_subscription_id': session.get('subscription'),
                    'amount': session.get('amount_total', 0) / 100,
                    'currency': session.get('currency', 'usd').upper(),
                    'status': 'succeeded',
                    'metadata': {'session_id': session.get('id')}
                }).execute()
            
            return {"success": True, "message": "Subscription activated"}
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService._handle_checkout_completed",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _handle_invoice_paid(invoice) -> Dict[str, Any]:
        """Handle successful invoice payment"""
        try:
            subscription_id = invoice.get('subscription')
            customer_id = invoice.get('customer')
            
            # Update subscription status
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if supabase:
                supabase.table('stripe_subscriptions')\
                    .update({'status': 'active'})\
                    .eq('stripe_subscription_id', subscription_id)\
                    .execute()
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _handle_payment_failed(invoice) -> Dict[str, Any]:
        """Handle failed payment"""
        try:
            subscription_id = invoice.get('subscription')
            
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if supabase:
                supabase.table('stripe_subscriptions')\
                    .update({'status': 'past_due'})\
                    .eq('stripe_subscription_id', subscription_id)\
                    .execute()
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _handle_subscription_updated(subscription) -> Dict[str, Any]:
        """Handle subscription update"""
        try:
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if supabase:
                supabase.table('stripe_subscriptions')\
                    .update({
                        'status': subscription.get('status'),
                        'current_period_end': datetime.fromtimestamp(subscription.get('current_period_end')).isoformat(),
                        'cancel_at_period_end': subscription.get('cancel_at_period_end', False)
                    })\
                    .eq('stripe_subscription_id', subscription.get('id'))\
                    .execute()
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _handle_subscription_deleted(subscription) -> Dict[str, Any]:
        """Handle subscription cancellation"""
        try:
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if supabase:
                supabase.table('stripe_subscriptions')\
                    .update({'status': 'cancelled'})\
                    .eq('stripe_subscription_id', subscription.get('id'))\
                    .execute()
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
        """Handle successful checkout session completion"""
        try:
            user_id = session['metadata'].get('user_id')
            plan_name = session['metadata'].get('plan_name')
            customer_id = session['customer']
            subscription_id = session['subscription']
            
            if not user_id or not plan_name:
                return {
                    "success": False,
                    "error": "Missing metadata"
                }
            
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Get subscription details from Stripe
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Save subscription to database
            supabase.table('stripe_subscriptions').insert({
                "user_id": user_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "plan": plan_name.lower(),
                "status": "active",
                "current_period_end": datetime.fromtimestamp(subscription['current_period_end']).isoformat()
            }).execute()
            
            # Grant subscription in the main subscription system
            duration_days = 30  # Monthly subscription
            await SubscriptionService.grant_subscription(
                user_id=user_id,
                plan_name=plan_name,
                duration_days=duration_days,
                payment_method='stripe',
                payment_id=subscription_id
            )
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=user_id,
                details={
                    "action": "checkout_completed",
                    "plan_name": plan_name,
                    "subscription_id": subscription_id
                },
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {
                "success": True,
                "message": "Subscription created"
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService._handle_checkout_completed",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _handle_invoice_paid(invoice) -> Dict[str, Any]:
        """Handle successful invoice payment"""
        try:
            customer_id = invoice['customer']
            subscription_id = invoice['subscription']
            amount = invoice['amount_paid'] / 100  # Convert from cents
            currency = invoice['currency']
            
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Get user_id from customer
            customer_result = supabase.table('stripe_customers')\
                .select('user_id')\
                .eq('stripe_customer_id', customer_id)\
                .single()\
                .execute()
            
            if not customer_result.data:
                return {
                    "success": False,
                    "error": "Customer not found"
                }
            
            user_id = customer_result.data['user_id']
            
            # Record payment
            supabase.table('stripe_payments').insert({
                "user_id": user_id,
                "stripe_payment_id": invoice['id'],
                "amount": amount,
                "currency": currency.upper(),
                "status": "succeeded"
            }).execute()
            
            # Update subscription period end
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                
                supabase.table('stripe_subscriptions')\
                    .update({
                        "current_period_end": datetime.fromtimestamp(subscription['current_period_end']).isoformat(),
                        "status": "active"
                    })\
                    .eq('stripe_subscription_id', subscription_id)\
                    .execute()
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=user_id,
                details={
                    "action": "invoice_paid",
                    "amount": amount,
                    "currency": currency
                },
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {
                "success": True,
                "message": "Payment recorded"
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService._handle_invoice_paid",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _handle_payment_failed(invoice) -> Dict[str, Any]:
        """Handle failed invoice payment"""
        try:
            customer_id = invoice['customer']
            
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Get user_id from customer
            customer_result = supabase.table('stripe_customers')\
                .select('user_id')\
                .eq('stripe_customer_id', customer_id)\
                .single()\
                .execute()
            
            if not customer_result.data:
                return {
                    "success": False,
                    "error": "Customer not found"
                }
            
            user_id = customer_result.data['user_id']
            
            # Record failed payment
            supabase.table('stripe_payments').insert({
                "user_id": user_id,
                "stripe_payment_id": invoice['id'],
                "amount": invoice['amount_due'] / 100,
                "currency": invoice['currency'].upper(),
                "status": "failed"
            }).execute()
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.API_ERROR,
                user_id=user_id,
                details={
                    "action": "payment_failed",
                    "invoice_id": invoice['id']
                },
                correlation_id=SecurityLogger.generate_correlation_id(),
                severity="WARNING"
            )
            
            return {
                "success": True,
                "message": "Payment failure recorded"
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService._handle_payment_failed",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _handle_subscription_updated(subscription) -> Dict[str, Any]:
        """Handle subscription update event"""
        try:
            subscription_id = subscription['id']
            status = subscription['status']
            
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Update subscription status
            supabase.table('stripe_subscriptions')\
                .update({
                    "status": status,
                    "current_period_end": datetime.fromtimestamp(subscription['current_period_end']).isoformat()
                })\
                .eq('stripe_subscription_id', subscription_id)\
                .execute()
            
            return {
                "success": True,
                "message": "Subscription updated"
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService._handle_subscription_updated",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def _handle_subscription_deleted(subscription) -> Dict[str, Any]:
        """Handle subscription cancellation/deletion"""
        try:
            subscription_id = subscription['id']
            customer_id = subscription['customer']
            
            from services.supabase_service import SupabaseService
            supabase = SupabaseService.get_service_client()
            
            if not supabase:
                return {
                    "success": False,
                    "error": "Database unavailable"
                }
            
            # Get user_id
            customer_result = supabase.table('stripe_customers')\
                .select('user_id')\
                .eq('stripe_customer_id', customer_id)\
                .single()\
                .execute()
            
            if not customer_result.data:
                return {
                    "success": False,
                    "error": "Customer not found"
                }
            
            user_id = customer_result.data['user_id']
            
            # Update subscription status
            supabase.table('stripe_subscriptions')\
                .update({
                    "status": "cancelled"
                })\
                .eq('stripe_subscription_id', subscription_id)\
                .execute()
            
            # Get plan name to cancel in main subscription system
            sub_result = supabase.table('stripe_subscriptions')\
                .select('plan')\
                .eq('stripe_subscription_id', subscription_id)\
                .single()\
                .execute()
            
            if sub_result.data:
                plan_name = sub_result.data['plan'].capitalize()
                await SubscriptionService.cancel_subscription(user_id, plan_name)
            
            SecurityLogger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=user_id,
                details={
                    "action": "subscription_deleted",
                    "subscription_id": subscription_id
                },
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            
            return {
                "success": True,
                "message": "Subscription cancelled"
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="StripeService._handle_subscription_deleted",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_price_id(plan_name: str) -> Optional[str]:
        """Get Stripe price ID for a plan"""
        price_ids = {
            "Pro": os.getenv("STRIPE_PRICE_PRO_MONTHLY", Config.STRIPE_PRICE_PRO_MONTHLY),
            "Teams": os.getenv("STRIPE_PRICE_TEAMS_MONTHLY", Config.STRIPE_PRICE_TEAMS_MONTHLY)
        }
        
        return price_ids.get(plan_name)
    
    @staticmethod
    def get_plan_prices() -> Dict[str, float]:
        """Get pricing for all plans"""
        return {
            "Free": 0.00,
            "Pro": 20.00,
            "Teams": 50.00
        }
