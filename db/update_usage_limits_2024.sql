-- ============================================================================
-- ORZION AI - USAGE LIMITS UPDATE 2024
-- ============================================================================
-- This migration updates the usage limits system to support:
-- 1. Daily message and token limits (replacing hourly/3-hour limits)
-- 2. Plan-based limits (Free, Pro, Teams)
-- 3. Token tracking per message and per day
-- ============================================================================

-- ============================================================================
-- Step 1: Add new columns to model_usage_quota for daily limits
-- ============================================================================
ALTER TABLE model_usage_quota 
ADD COLUMN IF NOT EXISTS bonus_messages_daily INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS bonus_tokens_daily INTEGER NOT NULL DEFAULT 0;

-- ============================================================================
-- Step 2: Create new table for daily usage tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_usage_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    model VARCHAR(50) NOT NULL,
    
    -- Daily tracking (resets at midnight UTC)
    date DATE NOT NULL,
    
    -- Usage counters
    messages_used INTEGER NOT NULL DEFAULT 0,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    
    -- Last updated
    last_request_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Prevent duplicate daily records
    UNIQUE(user_id, model, date)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_usage_daily_user_model ON model_usage_daily(user_id, model);
CREATE INDEX IF NOT EXISTS idx_usage_daily_date ON model_usage_daily(date);

-- ============================================================================
-- Step 3: Create RPC function to increment daily usage (atomic, thread-safe)
-- ============================================================================
CREATE OR REPLACE FUNCTION increment_daily_usage(
    p_user_id UUID,
    p_model VARCHAR(50),
    p_date DATE,
    p_messages INTEGER DEFAULT 1,
    p_tokens INTEGER DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_messages_used INTEGER;
    v_tokens_used INTEGER;
BEGIN
    -- Insert or update daily usage record
    INSERT INTO model_usage_daily (user_id, model, date, messages_used, tokens_used, last_request_at)
    VALUES (p_user_id, p_model, p_date, p_messages, p_tokens, NOW())
    ON CONFLICT (user_id, model, date) 
    DO UPDATE SET
        messages_used = model_usage_daily.messages_used + p_messages,
        tokens_used = model_usage_daily.tokens_used + p_tokens,
        last_request_at = NOW()
    RETURNING messages_used, tokens_used INTO v_messages_used, v_tokens_used;
    
    -- Return updated counts
    RETURN jsonb_build_object(
        'messages_used', v_messages_used,
        'tokens_used', v_tokens_used
    );
END;
$$;

-- ============================================================================
-- Step 4: Create RPC function to cleanup old daily usage records
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_old_daily_usage()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Delete records older than 30 days
    DELETE FROM model_usage_daily
    WHERE date < CURRENT_DATE - INTERVAL '30 days';
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    RETURN v_deleted_count;
END;
$$;

-- ============================================================================
-- Step 5: Initialize bonus limits for existing users (set to 0)
-- ============================================================================
UPDATE model_usage_quota
SET 
    bonus_messages_daily = 0,
    bonus_tokens_daily = 0
WHERE bonus_messages_daily IS NULL OR bonus_tokens_daily IS NULL;

-- ============================================================================
-- Step 6: Grant permissions
-- ============================================================================
GRANT SELECT, INSERT, UPDATE ON model_usage_daily TO authenticated;

-- ============================================================================
-- Step 7: Add comments for documentation
-- ============================================================================
COMMENT ON TABLE model_usage_daily IS 'Tracks daily message and token usage per user per model';
COMMENT ON COLUMN model_usage_daily.date IS 'Date (UTC) for this usage record';
COMMENT ON COLUMN model_usage_daily.messages_used IS 'Number of messages sent on this date';
COMMENT ON COLUMN model_usage_daily.tokens_used IS 'Total tokens used on this date';
COMMENT ON FUNCTION increment_daily_usage IS 'Atomically increments daily usage counters for a user and model';
COMMENT ON FUNCTION cleanup_old_daily_usage IS 'Removes daily usage records older than 30 days';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- The old hourly/three_hour limits in model_usage_quota and model_usage_window
-- tables are kept for backward compatibility but are no longer used by the
-- new limit_service.py implementation.
--
-- New system uses:
-- - Plan-based limits (Free, Pro, Teams) defined in limit_service.py
-- - Daily message limits (messages_daily)
-- - Token limits (tokens_per_message, tokens_daily)
-- - Bonus limits stored in bonus_messages_daily and bonus_tokens_daily
-- ============================================================================
