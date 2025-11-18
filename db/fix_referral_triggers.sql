
-- ============================================================================
-- FIX: Referral System Triggers on auth.users
-- ============================================================================
-- This fixes the trigger creation to work with auth.users (not public.users)
-- Run this in Supabase SQL Editor
-- ============================================================================

-- Step 1: Drop existing triggers if they exist
-- ============================================================================
DROP TRIGGER IF EXISTS trigger_initialize_user_quotas ON auth.users;
DROP TRIGGER IF EXISTS trigger_initialize_referral_profile ON auth.users;

-- Step 2: Recreate the initialize_user_quotas function
-- ============================================================================
CREATE OR REPLACE FUNCTION public.initialize_user_quotas()
RETURNS TRIGGER AS $$
BEGIN
    -- Orzion Pro
    INSERT INTO public.model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Pro', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Turbo
    INSERT INTO public.model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Turbo', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Mini
    INSERT INTO public.model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Mini', 30, 100, 300)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error in initialize_user_quotas for user %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 3: Recreate the initialize_referral_profile function
-- ============================================================================
CREATE OR REPLACE FUNCTION public.initialize_referral_profile()
RETURNS TRIGGER AS $$
DECLARE
    new_code VARCHAR(20);
    code_exists BOOLEAN;
BEGIN
    -- Generate unique 8-character code
    LOOP
        new_code := lower(substr(md5(random()::text || NEW.id::text), 1, 8));
        SELECT EXISTS(SELECT 1 FROM public.referral_profiles WHERE referral_code = new_code) INTO code_exists;
        EXIT WHEN NOT code_exists;
    END LOOP;
    
    -- Create referral profile
    INSERT INTO public.referral_profiles (user_id, referral_code)
    VALUES (NEW.id, new_code)
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error in initialize_referral_profile for user %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 4: Create triggers on auth.users (NOT public.users)
-- ============================================================================
CREATE TRIGGER trigger_initialize_user_quotas
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.initialize_user_quotas();

CREATE TRIGGER trigger_initialize_referral_profile
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.initialize_referral_profile();

-- Step 5: Verify triggers were created correctly
-- ============================================================================
SELECT 
    trigger_name,
    event_object_schema,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE trigger_name IN ('trigger_initialize_user_quotas', 'trigger_initialize_referral_profile')
ORDER BY trigger_name;

-- Expected output:
-- trigger_initialize_user_quotas    | auth | users | EXECUTE FUNCTION public.initialize_user_quotas()
-- trigger_initialize_referral_profile | auth | users | EXECUTE FUNCTION public.initialize_referral_profile()
