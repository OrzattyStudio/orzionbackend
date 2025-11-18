-- ====================================================================
-- STRIPE PAYMENT SYSTEM SCHEMA
-- ====================================================================
-- This schema creates tables for Stripe payment integration
-- Tracks customers, subscriptions, and payment history
-- Run this in Supabase SQL Editor
-- ====================================================================

-- Create stripe_customers table (maps users to Stripe customers)
CREATE TABLE IF NOT EXISTS public.stripe_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Create stripe_subscriptions table (tracks Stripe subscriptions)
CREATE TABLE IF NOT EXISTS public.stripe_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT NOT NULL,
    stripe_subscription_id TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL CHECK (plan IN ('free', 'pro', 'teams')),
    status TEXT NOT NULL CHECK (status IN ('active', 'cancelled', 'past_due', 'unpaid', 'incomplete')),
    current_period_end TIMESTAMP WITH TIME ZONE,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create stripe_payments table (payment history)
CREATE TABLE IF NOT EXISTS public.stripe_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_payment_id TEXT NOT NULL,
    stripe_subscription_id TEXT,
    amount DECIMAL(10, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'pending', 'failed', 'refunded')),
    payment_method TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_stripe_customers_user_id ON public.stripe_customers(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_customers_stripe_id ON public.stripe_customers(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_user_id ON public.stripe_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_stripe_id ON public.stripe_subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_stripe_subscriptions_status ON public.stripe_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_stripe_payments_user_id ON public.stripe_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_stripe_payments_status ON public.stripe_payments(status);

-- Enable Row Level Security
ALTER TABLE public.stripe_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stripe_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stripe_payments ENABLE ROW LEVEL SECURITY;

-- RLS Policies for stripe_customers
CREATE POLICY "Users can view their own Stripe customer data"
ON public.stripe_customers FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- RLS Policies for stripe_subscriptions
CREATE POLICY "Users can view their own Stripe subscriptions"
ON public.stripe_subscriptions FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- RLS Policies for stripe_payments
CREATE POLICY "Users can view their own Stripe payments"
ON public.stripe_payments FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Service role has full access
CREATE POLICY "Service role full access to stripe customers"
ON public.stripe_customers FOR ALL
TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to stripe subscriptions"
ON public.stripe_subscriptions FOR ALL
TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to stripe payments"
ON public.stripe_payments FOR ALL
TO service_role
USING (true) WITH CHECK (true);

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_stripe_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS trigger_stripe_customers_updated_at ON public.stripe_customers;
CREATE TRIGGER trigger_stripe_customers_updated_at
BEFORE UPDATE ON public.stripe_customers
FOR EACH ROW
EXECUTE FUNCTION public.update_stripe_updated_at();

DROP TRIGGER IF EXISTS trigger_stripe_subscriptions_updated_at ON public.stripe_subscriptions;
CREATE TRIGGER trigger_stripe_subscriptions_updated_at
BEFORE UPDATE ON public.stripe_subscriptions
FOR EACH ROW
EXECUTE FUNCTION public.update_stripe_updated_at();

-- Add comments for documentation
COMMENT ON TABLE public.stripe_customers IS 'Maps Orzion users to Stripe customers';
COMMENT ON TABLE public.stripe_subscriptions IS 'Tracks active Stripe subscriptions for users';
COMMENT ON TABLE public.stripe_payments IS 'Payment transaction history from Stripe';

-- Success message
DO $$ 
BEGIN 
    RAISE NOTICE '✅ Stripe payment schema created successfully!';
    RAISE NOTICE 'Tables: stripe_customers, stripe_subscriptions, stripe_payments';
    RAISE NOTICE 'All tables have RLS enabled with appropriate policies';
END $$;
