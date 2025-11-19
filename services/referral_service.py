"""
Referral Service - Handles referral code generation, redemption, and IP-based anti-abuse
"""
import hashlib
import hmac
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from services.supabase_service import get_supabase_service
from config import config
from services.security_logger import SecurityLogger


class ReferralService:
    """Service for managing user referrals and bonuses"""
    
    @staticmethod
    def _hash_ip(ip_address: str) -> str:
        """
        Hash IP address using HMAC-SHA256 for privacy and security.
        This prevents storing raw IPs while still allowing duplicate detection.
        """
        secret = config.SECRET_KEY.encode('utf-8')
        ip_bytes = ip_address.encode('utf-8')
        return hmac.new(secret, ip_bytes, hashlib.sha256).hexdigest()
    
    @staticmethod
    async def get_user_referral_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's referral profile with stats"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return None
            
            response = supabase.table('referral_profiles').select('*').eq('user_id', user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="ReferralService.get_user_referral_profile",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return None
    
    @staticmethod
    async def get_referral_stats(user_id: str) -> Dict[str, Any]:
        """Get detailed referral statistics for a user"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return {
                    "referral_code": None,
                    "total_referrals": 0,
                    "bonus_multiplier": 1.0,
                    "successful_referrals": []
                }
            
            # Get referral profile
            profile = await ReferralService.get_user_referral_profile(user_id)
            
            # If no profile exists, create one automatically
            if not profile:
                import secrets
                import string
                
                print(f"[REFERRALS] No profile found for user {user_id}, creating one...")
                
                # Generate unique referral code
                alphabet = string.ascii_uppercase + string.digits
                referral_code = ''.join(secrets.choice(alphabet) for _ in range(8))
                
                print(f"[REFERRALS] Generated code: {referral_code}")
                
                try:
                    # Insert new profile
                    response = supabase.table('referral_profiles').insert({
                        'user_id': user_id,
                        'referral_code': referral_code,
                        'total_successful_referrals': 0,
                        'bonus_multiplier': 1.0
                    }).execute()
                    
                    print(f"[REFERRALS] Insert response: {response}")
                    
                    if response.data and len(response.data) > 0:
                        profile = response.data[0]
                        print(f"[REFERRALS] Profile created successfully: {profile}")
                    else:
                        print(f"[REFERRALS] Insert succeeded but no data returned")
                        # Try to fetch it again
                        profile = await ReferralService.get_user_referral_profile(user_id)
                        print(f"[REFERRALS] Refetched profile: {profile}")
                        
                except Exception as e:
                    print(f"[REFERRALS] Error creating profile: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            if not profile:
                print(f"[REFERRALS] Still no profile after creation attempt")
                return {
                    "referral_code": None,
                    "total_referrals": 0,
                    "bonus_multiplier": 1.0,
                    "successful_referrals": []
                }
            
            # Get successful referral events
            events_response = supabase.table('referral_events')\
                .select('*')\
                .eq('referrer_id', user_id)\
                .eq('status', 'approved')\
                .order('created_at', desc=True)\
                .limit(20)\
                .execute()
            
            return {
                "referral_code": profile['referral_code'],
                "total_referrals": profile['total_successful_referrals'],
                "bonus_multiplier": float(profile['bonus_multiplier']),
                "successful_referrals": events_response.data if events_response.data else [],
                "created_at": profile['created_at']
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="ReferralService.get_referral_stats",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return {
                "referral_code": None,
                "total_referrals": 0,
                "bonus_multiplier": 1.0,
                "successful_referrals": []
            }
    
    @staticmethod
    async def validate_referral_code(referral_code: str) -> Optional[Dict[str, Any]]:
        """Validate that a referral code exists and get referrer info"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return None
            
            response = supabase.table('referral_profiles')\
                .select('user_id, referral_code, total_successful_referrals')\
                .eq('referral_code', referral_code.lower().strip())\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="ReferralService.validate_referral_code",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return None
    
    @staticmethod
    async def check_ip_already_used(ip_address: str) -> bool:
        """
        Check if this IP has already been used for a referral.
        FAIL-SAFE: Returns True (block) on any error to prevent abuse.
        """
        try:
            supabase = get_supabase_service()
            if not supabase:
                SecurityLogger.log_security_event(
                    event_type="IP_CHECK_DB_UNAVAILABLE",
                    user_id=None,
                    details={"reason": "Database unavailable during IP check"},
                    correlation_id=SecurityLogger.generate_correlation_id()
                )
                return True  # FAIL-SAFE: Block if DB unavailable
            
            ip_hash = ReferralService._hash_ip(ip_address)
            
            # Check if IP is in blocklist and not expired
            response = supabase.table('ip_referral_blocklist')\
                .select('*')\
                .eq('ip_hash', ip_hash)\
                .gte('expires_at', datetime.utcnow().isoformat())\
                .execute()
            
            return bool(response.data and len(response.data) > 0)
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="ReferralService.check_ip_already_used",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return True  # FAIL-SAFE: Block on error to prevent abuse
    
    @staticmethod
    async def redeem_referral_code(
        referral_code: str,
        referred_user_id: str,
        ip_address: str,
        user_created_at: datetime
    ) -> Dict[str, Any]:
        """
        Redeem a referral code for a new user.
        Returns: {"success": bool, "message": str, "bonus_applied": bool}
        """
        correlation_id = SecurityLogger.generate_correlation_id()
        
        try:
            print(f"[REFERRAL-SERVICE] 🎁 Starting redemption for user {referred_user_id}, code: {referral_code}")
            
            supabase = get_supabase_service()
            if not supabase:
                print(f"[REFERRAL-SERVICE] ❌ Supabase unavailable")
                return {
                    "success": False,
                    "message": "Referral system temporarily unavailable",
                    "bonus_applied": False
                }
            
            # 1. Validate referral code exists
            print(f"[REFERRAL-SERVICE] 🔍 Validating referral code...")
            referrer = await ReferralService.validate_referral_code(referral_code)
            if not referrer:
                print(f"[REFERRAL-SERVICE] ❌ Invalid referral code: {referral_code}")
                return {
                    "success": False,
                    "message": "Invalid referral code",
                    "bonus_applied": False
                }
            
            referrer_id = referrer['user_id']
            print(f"[REFERRAL-SERVICE] ✅ Valid code! Referrer ID: {referrer_id}")
            
            # 2. Prevent self-referral
            if referrer_id == referred_user_id:
                print(f"[REFERRAL-SERVICE] ❌ Self-referral attempt detected")
                SecurityLogger.log_security_event(
                    event_type="SELF_REFERRAL_ATTEMPT",
                    user_id=referred_user_id,
                    details={"referral_code": referral_code},
                    correlation_id=correlation_id
                )
                return {
                    "success": False,
                    "message": "Cannot use your own referral code",
                    "bonus_applied": False
                }
            
            # 3. Check if user is new (account created within last 24 hours)
            account_age = datetime.utcnow() - user_created_at
            print(f"[REFERRAL-SERVICE] ⏰ Account age: {account_age} (limit: 24h)")
            if account_age > timedelta(hours=24):
                print(f"[REFERRAL-SERVICE] ❌ Account too old: {account_age}")
                return {
                    "success": False,
                    "message": "Referral codes can only be used within 24 hours of account creation",
                    "bonus_applied": False
                }
            
            # 4. Check if this user has already used a referral code
            print(f"[REFERRAL-SERVICE] 🔍 Checking for existing referrals...")
            existing_referral = supabase.table('referral_events')\
                .select('*')\
                .eq('referred_id', referred_user_id)\
                .eq('status', 'approved')\
                .execute()
            
            if existing_referral.data and len(existing_referral.data) > 0:
                print(f"[REFERRAL-SERVICE] ❌ User already used a referral code")
                return {
                    "success": False,
                    "message": "You have already used a referral code",
                    "bonus_applied": False
                }
            
            # 5. Check IP anti-abuse
            print(f"[REFERRAL-SERVICE] 🔍 Checking IP anti-abuse (IP: {ip_address})...")
            ip_already_used = await ReferralService.check_ip_already_used(ip_address)
            if ip_already_used:
                ip_hash = ReferralService._hash_ip(ip_address)
                print(f"[REFERRAL-SERVICE] ❌ IP already used for referral")
                
                # Log this as potential abuse
                SecurityLogger.log_security_event(
                    event_type="DUPLICATE_IP_REFERRAL",
                    user_id=referred_user_id,
                    details={"ip_hash": ip_hash, "referral_code": referral_code},
                    correlation_id=correlation_id
                )
                
                # Create rejected referral event
                supabase.table('referral_events').insert({
                    "referrer_id": referrer_id,
                    "referred_id": referred_user_id,
                    "referral_code": referral_code,
                    "referral_ip_hash": ip_hash,
                    "status": "rejected",
                    "rejection_reason": "IP address already used for another referral"
                }).execute()
                
                return {
                    "success": False,
                    "message": "This device has already been used to redeem a referral code",
                    "bonus_applied": False
                }
            
            # 6. All checks passed - process the referral
            print(f"[REFERRAL-SERVICE] ✅ All checks passed! Processing referral...")
            ip_hash = ReferralService._hash_ip(ip_address)
            
            # Create approved referral event
            print(f"[REFERRAL-SERVICE] 📝 Creating referral event in database...")
            supabase.table('referral_events').insert({
                "referrer_id": referrer_id,
                "referred_id": referred_user_id,
                "referral_code": referral_code,
                "referral_ip_hash": ip_hash,
                "status": "approved"
            }).execute()
            print(f"[REFERRAL-SERVICE] ✅ Referral event created")
            
            # Add IP to blocklist
            supabase.table('ip_referral_blocklist').insert({
                "ip_hash": ip_hash,
                "referral_count": 1,
                "last_referral_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }).execute()
            
            # Apply bonus to referrer (double their limits for backward compatibility)
            supabase.rpc('apply_referral_bonus', {
                'p_user_id': referrer_id,
                'p_bonus_factor': 2.0,
                'p_max_multiplier': 10.0
            }).execute()
            
            # NEW REWARD SYSTEM: Grant subscription time based on referral count
            # IMPORTANT: Fetch AFTER the referral event is created to get updated count
            referrer_profile = await ReferralService.get_user_referral_profile(referrer_id)
            
            # Re-fetch to get the updated count including this new referral
            updated_count = supabase.table('referral_events')\
                .select('id', count='exact')\
                .eq('referrer_id', referrer_id)\
                .eq('status', 'approved')\
                .execute()
            
            total_referrals = updated_count.count if updated_count.count is not None else 1
            
            # Calculate reward based on total referrals (NOW including the current one)
            if total_referrals == 1:
                # First referral: Pro plan for 2 weeks (14 days)
                supabase.rpc('grant_subscription_time', {
                    'p_user_id': referrer_id,
                    'p_plan_name': 'Pro',
                    'p_duration_days': 14,
                    'p_reason': 'First referral bonus'
                }).execute()
                reward_msg = "Plan Pro por 2 semanas"
            elif total_referrals < 10:
                # Additional referrals (2-9): Extend Pro by 3 weeks (21 days)
                supabase.rpc('grant_subscription_time', {
                    'p_user_id': referrer_id,
                    'p_plan_name': 'Pro',
                    'p_duration_days': 21,
                    'p_reason': f'Referral #{total_referrals} bonus'
                }).execute()
                reward_msg = "Plan Pro extendido por 3 semanas"
            elif total_referrals == 10:
                # 10th referral: Grant Teams plan for 2 weeks (14 days)
                supabase.rpc('grant_subscription_time', {
                    'p_user_id': referrer_id,
                    'p_plan_name': 'Teams',
                    'p_duration_days': 14,
                    'p_reason': '10 referrals milestone - Teams bonus'
                }).execute()
                reward_msg = "Plan Teams por 2 semanas (¡Meta de 10 referidos alcanzada!)"
            else:
                # Beyond 10 referrals: Continue extending Pro by 3 weeks
                supabase.rpc('grant_subscription_time', {
                    'p_user_id': referrer_id,
                    'p_plan_name': 'Pro',
                    'p_duration_days': 21,
                    'p_reason': f'Referral #{total_referrals} bonus'
                }).execute()
                reward_msg = "Plan Pro extendido por 3 semanas"
            
            # Log successful referral
            SecurityLogger.log_security_event(
                event_type="REFERRAL_SUCCESS",
                user_id=referred_user_id,
                details={
                    "referrer_id": referrer_id,
                    "referral_code": referral_code,
                    "total_referrals": total_referrals,
                    "reward": reward_msg
                },
                correlation_id=correlation_id
            )
            
            return {
                "success": True,
                "message": f"¡Código de referido aplicado! El usuario que te refirió ha recibido: {reward_msg}.",
                "bonus_applied": True
            }
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="ReferralService.redeem_referral_code",
                error_message=str(e),
                correlation_id=correlation_id
            )
            return {
                "success": False,
                "message": "An error occurred while processing the referral",
                "bonus_applied": False
            }
    
    @staticmethod
    async def get_referral_leaderboard(limit: int = 10) -> list:
        """Get top referrers (for future leaderboard feature)"""
        try:
            supabase = get_supabase_service()
            if not supabase:
                return []
            
            response = supabase.table('referral_profiles')\
                .select('total_successful_referrals, bonus_multiplier, created_at')\
                .order('total_successful_referrals', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            SecurityLogger.log_api_error(
                api_name="ReferralService.get_referral_leaderboard",
                error_message=str(e),
                correlation_id=SecurityLogger.generate_correlation_id()
            )
            return []
