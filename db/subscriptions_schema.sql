-- ====================================================================
-- SUBSCRIPTION PLANS SYSTEM
-- ====================================================================
-- This schema creates tables for Free, Pro, and Teams subscription plans
-- Includes integration with referral rewards system
-- Run this in Supabase SQL Editor
-- ====================================================================

-- Create subscription_plans table (catalog of available plans)
CREATE TABLE IF NOT EXISTS public.subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_name TEXT NOT NULL UNIQUE CHECK (plan_name IN ('Free', 'Pro', 'Teams')),
    display_name TEXT NOT NULL,
    description TEXT,
    price_monthly DECIMAL(10, 2) NOT NULL DEFAULT 0,
    price_yearly DECIMAL(10, 2) NOT NULL DEFAULT 0,
    features JSONB DEFAULT '[]',
    limits JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create user_subscriptions table (tracks each user's subscription)
CREATE TABLE IF NOT EXISTS public.user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES public.subscription_plans(id),
    plan_name TEXT NOT NULL CHECK (plan_name IN ('Free', 'Pro', 'Teams')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled', 'trial')),
    payment_method TEXT CHECK (payment_method IN ('paypal', 'referral_bonus', 'free', 'manual')),
    payment_id TEXT,
    starts_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create subscription_history table (audit log of all subscription changes)
CREATE TABLE IF NOT EXISTS public.subscription_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES public.user_subscriptions(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('created', 'upgraded', 'downgraded', 'extended', 'expired', 'cancelled', 'renewed')),
    from_plan TEXT,
    to_plan TEXT,
    duration_days INTEGER,
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create payment_transactions table (for PayPal and other payment tracking)
CREATE TABLE IF NOT EXISTS public.payment_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES public.user_subscriptions(id) ON DELETE SET NULL,
    payment_provider TEXT NOT NULL CHECK (payment_provider IN ('paypal', 'referral', 'manual')),
    payment_id TEXT,
    payer_id TEXT,
    amount DECIMAL(10, 2),
    currency TEXT DEFAULT 'USD',
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    transaction_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default plan catalog
INSERT INTO public.subscription_plans (plan_name, display_name, description, price_monthly, price_yearly, features, limits)
VALUES
    ('Free', 'Free Plan', 'Acceso básico a Orzion con límites razonables', 0, 0, 
     '["Orzion Mini ilimitado", "Orzion Pro limitado", "Orzion Turbo limitado", "Búsqueda web básica"]',
     '{"pro_limit_3h": 15, "turbo_limit_3h": 15, "mini_limit_3h": 100}'),
    
    ('Pro', 'Pro Plan', 'Acceso completo a modelos premium con límites extendidos', 19.99, 199.99,
     '["Orzion Pro sin límites", "Orzion Turbo sin límites", "Orzion Mini ilimitado", "Búsqueda web avanzada", "Generación de imágenes", "Soporte prioritario"]',
     '{"pro_limit_3h": 100, "turbo_limit_3h": 100, "mini_limit_3h": -1}'),
    
    ('Teams', 'Teams Plan', 'Plan empresarial con funciones avanzadas para equipos', 49.99, 499.99,
     '["Todo lo de Pro", "Colaboración en equipo", "Administración de usuarios", "Analytics avanzados", "API access", "Soporte dedicado 24/7"]',
     '{"pro_limit_3h": -1, "turbo_limit_3h": -1, "mini_limit_3h": -1}')
ON CONFLICT (plan_name) DO NOTHING;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON public.user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON public.user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expires_at ON public.user_subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_subscription_history_user_id ON public.subscription_history(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_user_id ON public.payment_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_transactions_status ON public.payment_transactions(status);

-- Enable Row Level Security
ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_transactions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for subscription_plans (public read)
CREATE POLICY "Anyone can view subscription plans"
ON public.subscription_plans FOR SELECT
TO authenticated
USING (true);

-- RLS Policies for user_subscriptions
CREATE POLICY "Users can view their own subscriptions"
ON public.user_subscriptions FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- RLS Policies for subscription_history
CREATE POLICY "Users can view their own subscription history"
ON public.subscription_history FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- RLS Policies for payment_transactions
CREATE POLICY "Users can view their own payment transactions"
ON public.payment_transactions FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Service role has full access
CREATE POLICY "Service role full access to subscriptions"
ON public.user_subscriptions FOR ALL
TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to history"
ON public.subscription_history FOR ALL
TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to payments"
ON public.payment_transactions FOR ALL
TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to plans"
ON public.subscription_plans FOR ALL
TO service_role
USING (true) WITH CHECK (true);

-- Function: Initialize Free plan for new users
CREATE OR REPLACE FUNCTION public.initialize_free_subscription()
RETURNS TRIGGER AS $$
DECLARE
    free_plan_id UUID;
BEGIN
    -- Get Free plan ID
    SELECT id INTO free_plan_id
    FROM public.subscription_plans
    WHERE plan_name = 'Free'
    LIMIT 1;
    
    IF free_plan_id IS NOT NULL THEN
        -- Create Free subscription (no expiration)
        INSERT INTO public.user_subscriptions (user_id, plan_id, plan_name, status, payment_method)
        VALUES (NEW.id, free_plan_id, 'Free', 'active', 'free');
        
        -- Log subscription creation
        INSERT INTO public.subscription_history (user_id, action, to_plan, reason)
        VALUES (NEW.id, 'created', 'Free', 'New user registration');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger: Auto-create Free subscription for new users
DROP TRIGGER IF EXISTS trigger_initialize_free_subscription ON auth.users;
CREATE TRIGGER trigger_initialize_free_subscription
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.initialize_free_subscription();

-- Function: Grant subscription time (for referral rewards)
CREATE OR REPLACE FUNCTION public.grant_subscription_time(
    p_user_id UUID,
    p_plan_name TEXT,
    p_duration_days INTEGER,
    p_reason TEXT DEFAULT 'Referral bonus'
)
RETURNS JSONB AS $$
DECLARE
    v_plan_id UUID;
    v_subscription_id UUID;
    v_new_expires_at TIMESTAMP WITH TIME ZONE;
    v_current_expires_at TIMESTAMP WITH TIME ZONE;
    v_now TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    -- Get plan ID
    SELECT id INTO v_plan_id
    FROM public.subscription_plans
    WHERE plan_name = p_plan_name;
    
    IF v_plan_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Plan not found'
        );
    END IF;
    
    -- Check if user has an active subscription of this type
    SELECT id, expires_at INTO v_subscription_id, v_current_expires_at
    FROM public.user_subscriptions
    WHERE user_id = p_user_id
    AND plan_name = p_plan_name
    AND status = 'active'
    LIMIT 1;
    
    IF v_subscription_id IS NOT NULL THEN
        -- Extend existing subscription
        IF v_current_expires_at IS NULL OR v_current_expires_at < v_now THEN
            -- Subscription expired or has no expiry, start from now
            v_new_expires_at := v_now + (p_duration_days || ' days')::INTERVAL;
        ELSE
            -- Subscription still active, extend from current expiry
            v_new_expires_at := v_current_expires_at + (p_duration_days || ' days')::INTERVAL;
        END IF;
        
        UPDATE public.user_subscriptions
        SET expires_at = v_new_expires_at,
            status = 'active',
            updated_at = v_now
        WHERE id = v_subscription_id;
        
        -- Log extension
        INSERT INTO public.subscription_history (user_id, subscription_id, action, to_plan, duration_days, reason)
        VALUES (p_user_id, v_subscription_id, 'extended', p_plan_name, p_duration_days, p_reason);
    ELSE
        -- Create new subscription
        v_new_expires_at := v_now + (p_duration_days || ' days')::INTERVAL;
        
        INSERT INTO public.user_subscriptions (user_id, plan_id, plan_name, status, payment_method, starts_at, expires_at)
        VALUES (p_user_id, v_plan_id, p_plan_name, 'active', 'referral_bonus', v_now, v_new_expires_at)
        RETURNING id INTO v_subscription_id;
        
        -- Log creation
        INSERT INTO public.subscription_history (user_id, subscription_id, action, to_plan, duration_days, reason)
        VALUES (p_user_id, v_subscription_id, 'created', p_plan_name, p_duration_days, p_reason);
    END IF;
    
    RETURN jsonb_build_object(
        'success', true,
        'subscription_id', v_subscription_id,
        'expires_at', v_new_expires_at
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Get user's current active plan
CREATE OR REPLACE FUNCTION public.get_user_active_plan(p_user_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_plan TEXT;
    v_now TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    -- Check for active Pro or Teams subscription (ordered by priority)
    SELECT plan_name INTO v_plan
    FROM public.user_subscriptions
    WHERE user_id = p_user_id
    AND status = 'active'
    AND (expires_at IS NULL OR expires_at > v_now)
    ORDER BY 
        CASE plan_name
            WHEN 'Teams' THEN 1
            WHEN 'Pro' THEN 2
            WHEN 'Free' THEN 3
        END
    LIMIT 1;
    
    RETURN COALESCE(v_plan, 'Free');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: Expire old subscriptions (run periodically)
CREATE OR REPLACE FUNCTION public.expire_old_subscriptions()
RETURNS INTEGER AS $$
DECLARE
    v_expired_count INTEGER;
    v_now TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    UPDATE public.user_subscriptions
    SET status = 'expired',
        updated_at = v_now
    WHERE status = 'active'
    AND expires_at IS NOT NULL
    AND expires_at < v_now;
    
    GET DIAGNOSTICS v_expired_count = ROW_COUNT;
    
    RETURN v_expired_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Add comments for documentation
COMMENT ON TABLE public.subscription_plans IS 'Catalog of available subscription plans (Free, Pro, Teams)';
COMMENT ON TABLE public.user_subscriptions IS 'Tracks each user''s subscription status and expiration';
COMMENT ON TABLE public.subscription_history IS 'Audit log of all subscription changes';
COMMENT ON TABLE public.payment_transactions IS 'Payment transaction records for paid subscriptions';
COMMENT ON FUNCTION public.grant_subscription_time IS 'Grant or extend subscription time for referral rewards';
COMMENT ON FUNCTION public.get_user_active_plan IS 'Get user''s highest priority active plan';

-- Success message
DO $$ 
BEGIN 
    RAISE NOTICE '✅ Subscription plans schema created successfully!';
    RAISE NOTICE 'Tables: subscription_plans, user_subscriptions, subscription_history, payment_transactions';
    RAISE NOTICE 'Functions: initialize_free_subscription, grant_subscription_time, get_user_active_plan, expire_old_subscriptions';
    RAISE NOTICE 'Default plans: Free, Pro ($19.99/mo), Teams ($49.99/mo)';
END $$;
