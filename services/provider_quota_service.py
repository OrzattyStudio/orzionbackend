"""
Provider Quota Service - Manages quota tracking for AI providers

Tracks daily request quotas and RPM limits per provider. Automatically marks providers
as exhausted when quotas are exceeded, with automatic reset at midnight UTC.

Falls back to in-memory storage if Supabase is not available.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Literal
from services.supabase_service import get_supabase_service
from services.security_logger import SecurityLogger
import asyncio

ProviderType = Literal["google", "openrouter"]
ModelType = Literal["pro", "turbo", "mini", "image"]


class ProviderQuotaService:
    """
    Service for tracking provider-level quotas and rate limits.
    
    Primary provider limits:
    - Pro: 200 req/day, 5 RPM
    - Turbo: 1,000 req/day, 15 RPM
    - Mini: 1,500 req/day, 15 RPM
    - Image: 50 img/day, 5 RPM
    
    Fallback provider: Unlimited with API key
    """
    
    # In-memory fallback storage
    _memory_storage: Dict[str, Dict] = {}
    _last_rpm_check: Dict[str, datetime] = {}
    _rpm_counter: Dict[str, int] = {}
    
    # Provider limits
    PROVIDER_LIMITS = {
        "google": {
            "pro": {"daily": 200, "rpm": 5},
            "turbo": {"daily": 1000, "rpm": 15},
            "mini": {"daily": 1500, "rpm": 15},
            "image": {"daily": 50, "rpm": 5}
        },
        "openrouter": {
            # Fallback provider - unlimited with API key billing
            "pro": {"daily": -1, "rpm": -1},
            "turbo": {"daily": -1, "rpm": -1},
            "mini": {"daily": -1, "rpm": -1},
            "image": {"daily": -1, "rpm": -1}
        }
    }
    
    @staticmethod
    def _get_storage_key(provider: ProviderType, model: ModelType) -> str:
        """Generate storage key for provider-model combination."""
        return f"provider_quota_{provider}_{model}"
    
    @staticmethod
    async def _get_quota_data(provider: ProviderType, model: ModelType) -> Dict:
        """Get quota data from Supabase or memory fallback."""
        key = ProviderQuotaService._get_storage_key(provider, model)
        today = datetime.now(timezone.utc).date().isoformat()
        
        try:
            supabase = get_supabase_service()
            if supabase:
                response = supabase.table('provider_quotas')\
                    .select('*')\
                    .eq('provider', provider)\
                    .eq('model', model)\
                    .eq('date', today)\
                    .execute()
                
                if response.data and len(response.data) > 0:
                    return response.data[0]
                else:
                    # Create new record
                    new_record = {
                        'provider': provider,
                        'model': model,
                        'date': today,
                        'requests_used': 0,
                        'is_exhausted': False,
                        'last_error_time': None
                    }
                    insert_response = supabase.table('provider_quotas').insert(new_record).execute()
                    if insert_response.data and len(insert_response.data) > 0:
                        return insert_response.data[0]
        except Exception as e:
            print(f"⚠️ Supabase unavailable for quota tracking, using memory: {e}")
        
        # Fallback to memory
        if key not in ProviderQuotaService._memory_storage:
            ProviderQuotaService._memory_storage[key] = {
                'provider': provider,
                'model': model,
                'date': today,
                'requests_used': 0,
                'is_exhausted': False,
                'last_error_time': None
            }
        
        # Reset if new day
        if ProviderQuotaService._memory_storage[key]['date'] != today:
            ProviderQuotaService._memory_storage[key] = {
                'provider': provider,
                'model': model,
                'date': today,
                'requests_used': 0,
                'is_exhausted': False,
                'last_error_time': None
            }
        
        return ProviderQuotaService._memory_storage[key]
    
    @staticmethod
    async def _update_quota_data(provider: ProviderType, model: ModelType, data: Dict):
        """Update quota data in Supabase or memory fallback."""
        key = ProviderQuotaService._get_storage_key(provider, model)
        today = datetime.now(timezone.utc).date().isoformat()
        
        try:
            supabase = get_supabase_service()
            if supabase:
                supabase.table('provider_quotas')\
                    .update(data)\
                    .eq('provider', provider)\
                    .eq('model', model)\
                    .eq('date', today)\
                    .execute()
                return
        except Exception as e:
            print(f"⚠️ Supabase unavailable for quota update, using memory: {e}")
        
        # Fallback to memory
        if key in ProviderQuotaService._memory_storage:
            ProviderQuotaService._memory_storage[key].update(data)
    
    @staticmethod
    async def check_provider_available(provider: ProviderType, model: ModelType) -> tuple[bool, Optional[str]]:
        """
        Check if provider has quota available.
        
        Returns:
            (available: bool, reason: Optional[str])
        """
        quota_data = await ProviderQuotaService._get_quota_data(provider, model)
        limits = ProviderQuotaService.PROVIDER_LIMITS.get(provider, {}).get(model, {})
        
        # Check if marked as exhausted
        if quota_data.get('is_exhausted'):
            return False, f"{provider} marked as exhausted for {model}"
        
        # Check daily limit
        daily_limit = limits.get('daily', -1)
        if daily_limit > 0:
            requests_used = quota_data.get('requests_used', 0)
            if requests_used >= daily_limit:
                # Mark as exhausted
                await ProviderQuotaService._update_quota_data(provider, model, {'is_exhausted': True})
                return False, f"{provider} daily quota exceeded ({requests_used}/{daily_limit})"
        
        # Check RPM limit
        rpm_limit = limits.get('rpm', -1)
        if rpm_limit > 0:
            rpm_key = f"{provider}_{model}"
            now = datetime.now(timezone.utc)
            
            # Reset RPM counter every minute
            if rpm_key not in ProviderQuotaService._last_rpm_check or \
               (now - ProviderQuotaService._last_rpm_check[rpm_key]).total_seconds() >= 60:
                ProviderQuotaService._last_rpm_check[rpm_key] = now
                ProviderQuotaService._rpm_counter[rpm_key] = 0
            
            # Check if RPM exceeded
            if ProviderQuotaService._rpm_counter.get(rpm_key, 0) >= rpm_limit:
                return False, f"{provider} RPM limit exceeded ({rpm_limit}/min)"
        
        return True, None
    
    @staticmethod
    async def increment_usage(provider: ProviderType, model: ModelType):
        """Increment usage counter for provider-model combination."""
        quota_data = await ProviderQuotaService._get_quota_data(provider, model)
        requests_used = quota_data.get('requests_used', 0) + 1
        
        await ProviderQuotaService._update_quota_data(provider, model, {
            'requests_used': requests_used
        })
        
        # Increment RPM counter
        rpm_key = f"{provider}_{model}"
        ProviderQuotaService._rpm_counter[rpm_key] = \
            ProviderQuotaService._rpm_counter.get(rpm_key, 0) + 1
        
        print(f"📊 {provider}/{model}: {requests_used} requests today")
    
    @staticmethod
    async def mark_provider_exhausted(provider: ProviderType, model: ModelType, error_code: Optional[int] = None):
        """
        Mark provider as exhausted (typically after 429 error or quota exceeded).
        Will auto-reset at midnight UTC.
        """
        await ProviderQuotaService._update_quota_data(provider, model, {
            'is_exhausted': True,
            'last_error_time': datetime.now(timezone.utc).isoformat()
        })
        
        print(f"🚫 {provider}/{model} marked as exhausted (error: {error_code})")
        
        SecurityLogger.log_api_error(
            api_name=f"{provider}_{model}",
            error_message=f"Provider marked as exhausted",
            status_code=error_code,
            correlation_id=SecurityLogger.generate_correlation_id()
        )
    
    @staticmethod
    async def get_quota_status(provider: ProviderType, model: ModelType) -> Dict:
        """Get current quota status for provider-model combination."""
        quota_data = await ProviderQuotaService._get_quota_data(provider, model)
        limits = ProviderQuotaService.PROVIDER_LIMITS.get(provider, {}).get(model, {})
        
        return {
            'provider': provider,
            'model': model,
            'requests_used': quota_data.get('requests_used', 0),
            'daily_limit': limits.get('daily', -1),
            'rpm_limit': limits.get('rpm', -1),
            'is_exhausted': quota_data.get('is_exhausted', False),
            'last_error_time': quota_data.get('last_error_time')
        }
