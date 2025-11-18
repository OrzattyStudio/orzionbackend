-- ============================================================================
-- MIGRATION: Add Terms Acceptance Field to user_settings
-- ============================================================================
-- Purpose: Add terms_accepted field to track if users have accepted
--          the terms of service and privacy policy
-- 
-- This migration is safe to run multiple times (idempotent)
-- ============================================================================

-- Add terms_accepted column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' 
        AND column_name = 'terms_accepted'
    ) THEN
        ALTER TABLE user_settings 
        ADD COLUMN terms_accepted BOOLEAN DEFAULT false;
        
        -- Add timestamp for when terms were accepted
        ALTER TABLE user_settings 
        ADD COLUMN terms_accepted_at TIMESTAMP WITH TIME ZONE;
        
        RAISE NOTICE 'Added terms_accepted and terms_accepted_at columns to user_settings';
    ELSE
        RAISE NOTICE 'Column terms_accepted already exists, skipping';
    END IF;
END $$;

-- Create index for faster queries on terms acceptance
CREATE INDEX IF NOT EXISTS idx_user_settings_terms_accepted 
ON user_settings(terms_accepted);

-- Verify the migration
SELECT 
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name = 'user_settings'
AND column_name IN ('terms_accepted', 'terms_accepted_at')
ORDER BY column_name;

-- ============================================================================
-- Expected Result:
-- Should show two columns:
-- - terms_accepted (boolean, default false)
-- - terms_accepted_at (timestamp with time zone, no default)
-- ============================================================================
