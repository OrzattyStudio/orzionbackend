
-- ============================================================================
-- ORZION REFERRAL SYSTEM & USAGE LIMITS SCHEMA
-- ============================================================================
-- This schema implements:
-- 1. Dynamic usage quotas per model (base + bonus from referrals)
-- 2. Rolling time windows (hour, 3-hour, day) for rate limiting
-- 3. Referral system with unique codes and IP-based anti-abuse
-- 4. Tracking of successful referrals and bonus multipliers
-- ============================================================================

-- ============================================================================
-- Table: model_usage_quota
-- Stores base and bonus limits for each user per model
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_usage_quota (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    model VARCHAR(50) NOT NULL, -- 'Orzion Pro', 'Orzion Turbo', 'Orzion Mini'
    
    -- Base limits (defaults are for Pro/Turbo, Mini gets different values via trigger)
    base_limit_hour INTEGER NOT NULL,
    base_limit_three_hour INTEGER NOT NULL,
    base_limit_day INTEGER NOT NULL,
    
    -- Bonus limits from referrals (cumulative)
    bonus_limit_hour INTEGER NOT NULL DEFAULT 0,
    bonus_limit_three_hour INTEGER NOT NULL DEFAULT 0,
    bonus_limit_day INTEGER NOT NULL DEFAULT 0,
    
    -- Metadata
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    PRIMARY KEY (user_id, model)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_model_usage_quota_user ON model_usage_quota(user_id);

-- ============================================================================
-- Table: model_usage_window
-- Tracks actual usage in different time windows
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_usage_window (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    model VARCHAR(50) NOT NULL,
    
    -- Time window tracking
    window_start TIMESTAMP WITH TIME ZONE NOT NULL, -- Truncated to 15-min blocks
    window_type VARCHAR(20) NOT NULL, -- 'hour', 'three_hour', 'day'
    
    -- Usage tracking
    request_count INTEGER NOT NULL DEFAULT 0,
    last_request_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Prevent duplicate windows
    UNIQUE(user_id, model, window_start, window_type)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_usage_window_user_model ON model_usage_window(user_id, model);
CREATE INDEX IF NOT EXISTS idx_usage_window_start ON model_usage_window(window_start);
CREATE INDEX IF NOT EXISTS idx_usage_window_cleanup ON model_usage_window(window_start, window_type);

-- ============================================================================
-- Table: referral_profiles
-- Each user gets a unique referral code
-- ============================================================================
CREATE TABLE IF NOT EXISTS referral_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    referral_code VARCHAR(20) UNIQUE NOT NULL,
    
    -- Stats
    total_successful_referrals INTEGER NOT NULL DEFAULT 0,
    bonus_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.0, -- 1.0 = base, 2.0 = doubled, etc.
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for referral code lookups
CREATE INDEX IF NOT EXISTS idx_referral_code ON referral_profiles(referral_code);

-- ============================================================================
-- Table: referral_events
-- Tracks each referral redemption
-- ============================================================================
CREATE TABLE IF NOT EXISTS referral_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Who referred whom
    referrer_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    referred_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    referral_code VARCHAR(20) NOT NULL,
    
    -- Anti-abuse tracking
    referral_ip_hash VARCHAR(64) NOT NULL, -- HMAC-SHA256 of IP
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    rejection_reason VARCHAR(255),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_referral_events_referrer ON referral_events(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referral_events_referred ON referral_events(referred_id);
CREATE INDEX IF NOT EXISTS idx_referral_events_ip ON referral_events(referral_ip_hash);
CREATE INDEX IF NOT EXISTS idx_referral_events_status ON referral_events(status);

-- ============================================================================
-- Table: ip_referral_blocklist
-- Prevents the same IP from being used for multiple referrals
-- ============================================================================
CREATE TABLE IF NOT EXISTS ip_referral_blocklist (
    ip_hash VARCHAR(64) PRIMARY KEY, -- HMAC-SHA256 of IP
    referral_count INTEGER NOT NULL DEFAULT 1,
    last_referral_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Allow one referral per IP per 30 days
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '30 days')
);

-- Index for cleanup
CREATE INDEX IF NOT EXISTS idx_ip_blocklist_expires ON ip_referral_blocklist(expires_at);

-- ============================================================================
-- Function: initialize_user_quotas
-- Called when a new user signs up to set default quotas
-- ============================================================================
CREATE OR REPLACE FUNCTION initialize_user_quotas()
RETURNS TRIGGER AS $$
BEGIN
    -- Orzion Pro - Strict limits (ChatGPT Free style)
    INSERT INTO model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Pro', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Turbo - Strict limits (ChatGPT Free style)
    INSERT INTO model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Turbo', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Mini - More generous limits
    INSERT INTO model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Mini', 30, 100, 300)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-create quotas for new users
DROP TRIGGER IF EXISTS trigger_initialize_user_quotas ON auth.users;
CREATE TRIGGER trigger_initialize_user_quotas
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION initialize_user_quotas();

-- ============================================================================
-- Function: initialize_referral_profile
-- Creates a unique referral code for each new user
-- ============================================================================
CREATE OR REPLACE FUNCTION initialize_referral_profile()
RETURNS TRIGGER AS $$
DECLARE
    new_code VARCHAR(20);
    code_exists BOOLEAN;
BEGIN
    -- Generate unique 8-character code (lowercase alphanumeric)
    LOOP
        new_code := lower(substr(md5(random()::text || NEW.id::text), 1, 8));
        
        -- Check if code already exists
        SELECT EXISTS(SELECT 1 FROM referral_profiles WHERE referral_code = new_code) INTO code_exists;
        
        -- Exit loop if code is unique
        EXIT WHEN NOT code_exists;
    END LOOP;
    
    -- Create referral profile
    INSERT INTO referral_profiles (user_id, referral_code)
    VALUES (NEW.id, new_code)
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-create referral profile for new users
DROP TRIGGER IF EXISTS trigger_initialize_referral_profile ON auth.users;
CREATE TRIGGER trigger_initialize_referral_profile
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION initialize_referral_profile();

-- ============================================================================
-- Function: increment_usage
-- Thread-safe function to increment usage counter for a window
-- ============================================================================
CREATE OR REPLACE FUNCTION increment_usage(
    p_user_id UUID,
    p_model VARCHAR(50),
    p_window_start TIMESTAMP WITH TIME ZONE,
    p_window_type VARCHAR(20)
)
RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    INSERT INTO model_usage_window (user_id, model, window_start, window_type, request_count, last_request_at)
    VALUES (p_user_id, p_model, p_window_start, p_window_type, 1, NOW())
    ON CONFLICT (user_id, model, window_start, window_type)
    DO UPDATE SET
        request_count = model_usage_window.request_count + 1,
        last_request_at = NOW()
    RETURNING request_count INTO new_count;
    
    RETURN new_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: apply_referral_bonus
-- Applies bonus to a user's limits when they successfully refer someone
-- ============================================================================
CREATE OR REPLACE FUNCTION apply_referral_bonus(
    p_user_id UUID,
    p_bonus_factor DECIMAL(5,2) DEFAULT 2.0,
    p_max_multiplier DECIMAL(5,2) DEFAULT 10.0
)
RETURNS BOOLEAN AS $$
DECLARE
    current_multiplier DECIMAL(5,2);
    new_multiplier DECIMAL(5,2);
BEGIN
    -- Get current multiplier
    SELECT bonus_multiplier INTO current_multiplier
    FROM referral_profiles
    WHERE user_id = p_user_id;
    
    -- Calculate new multiplier (capped at max)
    new_multiplier := LEAST(current_multiplier * p_bonus_factor, p_max_multiplier);
    
    -- Update referral profile
    UPDATE referral_profiles
    SET bonus_multiplier = new_multiplier,
        total_successful_referrals = total_successful_referrals + 1,
        updated_at = NOW()
    WHERE user_id = p_user_id;
    
    -- Update quotas for Pro and Turbo only (double the limits)
    UPDATE model_usage_quota
    SET bonus_limit_hour = base_limit_hour * (new_multiplier - 1.0),
        bonus_limit_three_hour = base_limit_three_hour * (new_multiplier - 1.0),
        bonus_limit_day = base_limit_day * (new_multiplier - 1.0),
        updated_at = NOW()
    WHERE user_id = p_user_id
    AND model IN ('Orzion Pro', 'Orzion Turbo');
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: cleanup_old_usage_windows
-- Removes usage windows older than 7 days
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_old_usage_windows()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM model_usage_window
    WHERE window_start < NOW() - INTERVAL '7 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: cleanup_expired_ip_blocks
-- Removes expired IP blocks
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_expired_ip_blocks()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM ip_referral_blocklist
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- RLS (Row Level Security) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE model_usage_quota ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_usage_window ENABLE ROW LEVEL SECURITY;
ALTER TABLE referral_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE referral_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ip_referral_blocklist ENABLE ROW LEVEL SECURITY;

-- Drop existing policies to avoid conflicts
DROP POLICY IF EXISTS "Users can view own quota" ON model_usage_quota;
DROP POLICY IF EXISTS "Users can view own windows" ON model_usage_window;
DROP POLICY IF EXISTS "Users can view own referral profile" ON referral_profiles;
DROP POLICY IF EXISTS "Users can view related referral events" ON referral_events;
DROP POLICY IF EXISTS "Service role full access to all tables" ON model_usage_quota;
DROP POLICY IF EXISTS "Service role full access to windows" ON model_usage_window;
DROP POLICY IF EXISTS "Service role full access to referrals" ON referral_profiles;
DROP POLICY IF EXISTS "Service role full access to events" ON referral_events;
DROP POLICY IF EXISTS "Service role full access to blocklist" ON ip_referral_blocklist;

-- Users can only see their own quota
CREATE POLICY "Users can view own quota" ON model_usage_quota
    FOR SELECT USING (auth.uid() = user_id);

-- Users can only see their own usage windows
CREATE POLICY "Users can view own windows" ON model_usage_window
    FOR SELECT USING (auth.uid() = user_id);

-- Users can only see their own referral profile
CREATE POLICY "Users can view own referral profile" ON referral_profiles
    FOR SELECT USING (auth.uid() = user_id);

-- Users can see referral events where they're the referrer or referred
CREATE POLICY "Users can view related referral events" ON referral_events
    FOR SELECT USING (auth.uid() = referrer_id OR auth.uid() = referred_id);

-- Service role has full access to all tables
CREATE POLICY "Service role full access to quotas" ON model_usage_quota
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to windows" ON model_usage_window
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to referrals" ON referral_profiles
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to events" ON referral_events
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to blocklist" ON ip_referral_blocklist
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- Grant permissions to authenticated users
-- ============================================================================
GRANT SELECT ON model_usage_quota TO authenticated;
GRANT SELECT ON model_usage_window TO authenticated;
GRANT SELECT ON referral_profiles TO authenticated;
GRANT SELECT ON referral_events TO authenticated;

-- ============================================================================
-- Comments for documentation
-- ============================================================================
COMMENT ON TABLE model_usage_quota IS 'Stores base and bonus usage limits for each user per AI model';
COMMENT ON TABLE model_usage_window IS 'Tracks actual API usage in rolling time windows';
COMMENT ON TABLE referral_profiles IS 'Unique referral codes and stats for each user';
COMMENT ON TABLE referral_events IS 'Log of all referral redemptions with anti-abuse tracking';
COMMENT ON TABLE ip_referral_blocklist IS 'Prevents same IP from being used for multiple referrals';
