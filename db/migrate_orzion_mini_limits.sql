-- ============================================================================
-- MIGRATION: Fix Orzion Mini Limits (Legacy Data)
-- ============================================================================
-- Purpose: Update all existing Orzion Mini records with incorrect limits
--          from (5/15/50) to correct limits (30/100/300)
-- 
-- This migration is safe to run multiple times (idempotent)
-- It will only update records that have incorrect values
-- ============================================================================

-- Show records that will be updated (for verification)
SELECT 
    user_id,
    model,
    base_limit_hour,
    base_limit_three_hour,
    base_limit_day,
    updated_at
FROM model_usage_quota
WHERE model = 'Orzion Mini'
AND (
    base_limit_hour != 30 
    OR base_limit_three_hour != 100 
    OR base_limit_day != 300
);

-- Update incorrect Orzion Mini limits to correct values
UPDATE model_usage_quota
SET 
    base_limit_hour = 30,
    base_limit_three_hour = 100,
    base_limit_day = 300,
    updated_at = NOW()
WHERE model = 'Orzion Mini'
AND (
    base_limit_hour != 30 
    OR base_limit_three_hour != 100 
    OR base_limit_day != 300
);

-- Verify the update
SELECT 
    COUNT(*) as total_orzion_mini_users,
    COUNT(CASE WHEN base_limit_hour = 30 THEN 1 END) as correct_hour_limit,
    COUNT(CASE WHEN base_limit_three_hour = 100 THEN 1 END) as correct_three_hour_limit,
    COUNT(CASE WHEN base_limit_day = 300 THEN 1 END) as correct_day_limit
FROM model_usage_quota
WHERE model = 'Orzion Mini';

-- ============================================================================
-- Expected Result:
-- All four counts should be equal, meaning all Orzion Mini records now have
-- the correct limits (30/100/300)
-- ============================================================================
