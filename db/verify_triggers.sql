
-- ============================================================================
-- Verify and recreate triggers if missing
-- ============================================================================

-- Drop existing triggers if any
DROP TRIGGER IF EXISTS trigger_initialize_user_quotas ON auth.users;
DROP TRIGGER IF EXISTS trigger_initialize_referral_profile ON auth.users;

-- Recreate initialize_user_quotas function
CREATE OR REPLACE FUNCTION initialize_user_quotas()
RETURNS TRIGGER AS $$
BEGIN
    -- Orzion Pro
    INSERT INTO model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Pro', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Turbo
    INSERT INTO model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Turbo', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Mini
    INSERT INTO model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Mini', 30, 100, 300)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate initialize_referral_profile function
CREATE OR REPLACE FUNCTION initialize_referral_profile()
RETURNS TRIGGER AS $$
DECLARE
    new_code VARCHAR(20);
    code_exists BOOLEAN;
BEGIN
    LOOP
        new_code := lower(substr(md5(random()::text || NEW.id::text), 1, 8));
        SELECT EXISTS(SELECT 1 FROM referral_profiles WHERE referral_code = new_code) INTO code_exists;
        EXIT WHEN NOT code_exists;
    END LOOP;
    
    INSERT INTO referral_profiles (user_id, referral_code)
    VALUES (NEW.id, new_code)
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER trigger_initialize_user_quotas
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION initialize_user_quotas();

CREATE TRIGGER trigger_initialize_referral_profile
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION initialize_referral_profile();

-- Verify triggers were created
SELECT trigger_name, event_object_table, action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public'
AND event_object_table = 'users';
