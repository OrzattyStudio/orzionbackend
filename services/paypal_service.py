
"""
PayPal Service - Full integration with PayPal SDK for payment processing
"""
from typing import Dict, Any, Optional
from services.security_logger import SecurityLogger
from services.subscription_service import SubscriptionService
import paypalrestsdk
import os

class PayPalService:
    """Service for handling PayPal payment integration with SDK"""
    
    _configured = False
    
    @staticmethod
    def configure():
        """Configure PayPal SDK with credentials"""
        if PayPalService._configured:
            return
        
        mode = os.getenv("PAYPAL_MODE", "sandbox")
        client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        client_secret = os.getenv("PAYPAL_SECRET", "")
        
        if not client_id or not client_secret:
            return
        
        paypalrestsdk.configure({
            "mode": mode,
            "client_id": client_id,
            "client_secret": client_secret
        })
        
        PayPalService._configured = True
    
    @staticmethod
    def is_configured() -> bool:
        """Check if PayPal credentials are configured"""
        PayPalService.configure()
        return PayPalService._configured
    
    @staticmethod
    def get_client_config() -> Dict[str, str]:
        """Get PayPal client configuration for frontend"""
        client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        mode = os.getenv("PAYPAL_MODE", "sandbox")
        
        if not client_id:
            SecurityLogger.log_api_error(
                api_name="PayPalService.get_client_config",
                error_message="PayPal not configured - missing credentials",
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "client_id": "",
                "mode": "sandbox",
                "configured": False
            }
        
        return {
            "client_id": client_id,
            "mode": mode,
            "configured": True
        }
    
    @staticmethod
    async def create_order(plan_name: str, billing_period: str = "monthly") -> Dict[str, Any]:
        """Create a PayPal order for a subscription plan"""
        if not PayPalService.is_configured():
            return {
                "success": False,
                "error": "PayPal not configured. Add PAYPAL_CLIENT_ID and PAYPAL_SECRET to environment."
            }
        
        try:
            prices = PayPalService.get_plan_prices()
            
            if plan_name not in prices or billing_period not in prices[plan_name]:
                return {
                    "success": False,
                    "error": "Invalid plan or billing period"
                }
            
            amount = prices[plan_name][billing_period]
            
            if amount == 0:
                return {
                    "success": False,
                    "error": "Free plan doesn't require payment"
                }
            
            # Create PayPal payment
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": f"https://{os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')}/payment/success",
                    "cancel_url": f"https://{os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')}/payment/cancel"
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": f"{plan_name} - {billing_period}",
                            "sku": f"{plan_name.lower()}_{billing_period}",
                            "price": str(amount),
                            "currency": "USD",
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": str(amount),
                        "currency": "USD"
                    },
                    "description": f"Orzion AI {plan_name} Subscription - {billing_period}"
                }]
            })
            
            if payment.create():
                approval_url = next(
                    (link.href for link in payment.links if link.rel == "approval_url"),
                    None
                )
                
                SecurityLogger.log_security_event(
                    event_type="PAYMENT_ORDER_CREATED",
                    user_id=None,
                    details={
                        "plan_name": plan_name,
                        "billing_period": billing_period,
                        "amount": amount,
                        "payment_id": payment.id
                    },
                    correlation_id=SecurityLogger.generate_correlation_id()
                )
                
                return {
                    "success": True,
                    "order_id": payment.id,
                    "approval_url": approval_url
                }
            else:
                return {
                    "success": False,
                    "error": payment.error
                }
                
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="PayPalService.create_order",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def capture_order(payment_id: str, payer_id: str, user_id: str) -> Dict[str, Any]:
        """Capture/execute a PayPal payment after user approval"""
        if not PayPalService.is_configured():
            return {
                "success": False,
                "error": "PayPal not configured"
            }
        
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            
            if payment.execute({"payer_id": payer_id}):
                # Extract plan details from payment
                item = payment.transactions[0].item_list.items[0]
                plan_name, billing_period = item.sku.split('_')
                plan_name = plan_name.capitalize()
                
                # Grant subscription
                duration_days = 365 if billing_period == "yearly" else 30
                
                await SubscriptionService.grant_subscription(
                    user_id=user_id,
                    plan_name=plan_name,
                    duration_days=duration_days,
                    payment_method='paypal',
                    payment_id=payment_id
                )
                
                SecurityLogger.log_security_event(
                    event_type="PAYMENT_CAPTURED",
                    user_id=user_id,
                    details={
                        "payment_id": payment_id,
                        "payer_id": payer_id,
                        "amount": payment.transactions[0].amount.total,
                        "plan_name": plan_name,
                        "billing_period": billing_period
                    },
                    correlation_id=SecurityLogger.generate_correlation_id()
                )
                
                return {
                    "success": True,
                    "message": "Payment captured and subscription activated",
                    "plan_name": plan_name,
                    "duration_days": duration_days
                }
            else:
                return {
                    "success": False,
                    "error": payment.error
                }
                
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="PayPalService.capture_order",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_plan_prices() -> Dict[str, Dict[str, float]]:
        """Get pricing for all plans"""
        return {
            "Free": {
                "monthly": 0,
                "yearly": 0
            },
            "Pro": {
                "monthly": 20.00,
                "yearly": 199.99
            },
            "Teams": {
                "monthly": 49.99,
                "yearly": 499.99
            }
        }
