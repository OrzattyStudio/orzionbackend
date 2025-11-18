
-- Magic link tokens table
CREATE TABLE IF NOT EXISTS public.magic_link_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Reauthentication tokens table
CREATE TABLE IF NOT EXISTS public.reauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    ip_address TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_token ON public.magic_link_tokens(token);
CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_user_id ON public.magic_link_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_reauth_tokens_token ON public.reauth_tokens(token);
CREATE INDEX IF NOT EXISTS idx_reauth_tokens_user_id ON public.reauth_tokens(user_id);

-- Row Level Security (RLS)
ALTER TABLE public.magic_link_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reauth_tokens ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view their own magic links" ON public.magic_link_tokens
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own reauth tokens" ON public.reauth_tokens
    FOR SELECT USING (auth.uid() = user_id);
