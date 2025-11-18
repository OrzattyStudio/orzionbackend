-- ====================================================================
-- USER FEEDBACK SYSTEM
-- ====================================================================
-- This schema creates the table and indexes for storing user feedback
-- Run this in Supabase SQL Editor to enable the feedback system
-- ====================================================================

-- Create user_feedback table
CREATE TABLE IF NOT EXISTS public.user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    message TEXT NOT NULL CHECK (char_length(message) <= 1000),
    category TEXT NOT NULL DEFAULT 'general',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT valid_category CHECK (category IN ('general', 'bug', 'feature', 'improvement', 'other'))
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON public.user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON public.user_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON public.user_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_feedback_category ON public.user_feedback(category);

-- Enable Row Level Security
ALTER TABLE public.user_feedback ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Users can insert their own feedback
CREATE POLICY "Users can insert their own feedback"
ON public.user_feedback
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- Users can view their own feedback
CREATE POLICY "Users can view their own feedback"
ON public.user_feedback
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Service role has full access (for admin stats)
CREATE POLICY "Service role has full access"
ON public.user_feedback
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Add comment for documentation
COMMENT ON TABLE public.user_feedback IS 'Stores user feedback with ratings and messages';
COMMENT ON COLUMN public.user_feedback.rating IS 'User rating from 1 to 5 stars';
COMMENT ON COLUMN public.user_feedback.category IS 'Feedback category: general, bug, feature, improvement, other';

-- Success message
DO $$ 
BEGIN 
    RAISE NOTICE '✅ User feedback schema created successfully!';
    RAISE NOTICE 'Table: user_feedback';
    RAISE NOTICE 'Indexes: Created for user_id, created_at, rating, category';
    RAISE NOTICE 'RLS: Enabled with policies for user access and service role';
END $$;
