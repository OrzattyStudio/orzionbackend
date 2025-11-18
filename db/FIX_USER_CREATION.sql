-- ============================================================================
-- FIX: Database Error Saving New User
-- ============================================================================
-- Purpose: Fix the "Database error saving new user" issue by:
--   1. Creating the trigger function that automatically creates user_settings
--   2. Setting up proper RLS policies
--   3. Ensuring all required tables exist
-- 
-- Run this in your Supabase SQL Editor to fix the registration issue
-- ============================================================================

-- Step 1: Ensure user_settings table exists with all required columns
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    theme VARCHAR(10) DEFAULT 'dark' CHECK (theme IN ('dark', 'light')),
    language VARCHAR(10) DEFAULT 'es',
    orzion_mini_enabled BOOLEAN DEFAULT true,
    orzion_turbo_enabled BOOLEAN DEFAULT false,
    orzion_pro_enabled BOOLEAN DEFAULT false,
    search_enabled BOOLEAN DEFAULT true,
    auto_archive_days INTEGER DEFAULT 30,
    terms_accepted BOOLEAN DEFAULT false,
    terms_accepted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Step 2: Create or replace the trigger function
-- ============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert a new row in user_settings for the new user
    INSERT INTO public.user_settings (
        user_id,
        theme,
        language,
        orzion_mini_enabled,
        orzion_turbo_enabled,
        orzion_pro_enabled,
        search_enabled,
        auto_archive_days,
        terms_accepted,
        terms_accepted_at,
        created_at,
        updated_at
    ) VALUES (
        NEW.id,
        'dark',
        'es',
        true,   -- orzion_mini_enabled (free tier)
        false,  -- orzion_turbo_enabled (requires upgrade)
        false,  -- orzion_pro_enabled (requires upgrade)
        true,   -- search_enabled
        30,     -- auto_archive_days
        false,  -- terms_accepted
        NULL,   -- terms_accepted_at
        NOW(),
        NOW()
    );
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error but don't fail the user creation
        RAISE WARNING 'Error creating user_settings for user %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 3: Drop existing trigger if it exists and recreate it
-- ============================================================================
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Step 4: Enable Row Level Security (RLS)
-- ============================================================================
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Step 5: Drop existing policies and create new ones
-- ============================================================================
DROP POLICY IF EXISTS "Users can view their own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can update their own settings" ON user_settings;
DROP POLICY IF EXISTS "Users can insert their own settings" ON user_settings;
DROP POLICY IF EXISTS "Service role can do anything" ON user_settings;

-- Policy: Users can view their own settings
CREATE POLICY "Users can view their own settings"
    ON user_settings
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Users can update their own settings
CREATE POLICY "Users can update their own settings"
    ON user_settings
    FOR UPDATE
    USING (auth.uid() = user_id);

-- Policy: Users can insert their own settings
CREATE POLICY "Users can insert their own settings"
    ON user_settings
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Policy: Service role can do everything (for the trigger)
CREATE POLICY "Service role can do anything"
    ON user_settings
    FOR ALL
    USING (auth.role() = 'service_role');

-- Step 6: Create indexes for better performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_created_at ON user_settings(created_at);

-- Step 7: Grant permissions
-- ============================================================================
GRANT ALL ON user_settings TO authenticated;
GRANT ALL ON user_settings TO service_role;

-- Step 8: Verify the setup
-- ============================================================================
SELECT 
    'Trigger Function' as object_type,
    proname as name,
    'EXISTS' as status
FROM pg_proc 
WHERE proname = 'handle_new_user'

UNION ALL

SELECT 
    'Trigger' as object_type,
    tgname as name,
    'EXISTS' as status
FROM pg_trigger 
WHERE tgname = 'on_auth_user_created'

UNION ALL

SELECT 
    'Table' as object_type,
    tablename as name,
    'EXISTS' as status
FROM pg_tables 
WHERE tablename = 'user_settings' AND schemaname = 'public'

UNION ALL

SELECT 
    'RLS Enabled' as object_type,
    tablename as name,
    CASE WHEN rowsecurity THEN 'YES' ELSE 'NO' END as status
FROM pg_tables 
WHERE tablename = 'user_settings' AND schemaname = 'public';

-- ============================================================================
-- Success Message
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '✅ ========================================';
    RAISE NOTICE '✅ User creation fix applied successfully!';
    RAISE NOTICE '✅ ========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'The following has been configured:';
    RAISE NOTICE '  1. user_settings table created/verified';
    RAISE NOTICE '  2. Trigger function created';
    RAISE NOTICE '  3. Trigger attached to auth.users';
    RAISE NOTICE '  4. RLS policies configured';
    RAISE NOTICE '  5. Indexes created';
    RAISE NOTICE '';
    RAISE NOTICE 'You can now test user registration!';
    RAISE NOTICE '';
END $$;
