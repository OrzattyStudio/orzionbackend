
-- Crear tabla rate_limits en Supabase
CREATE TABLE IF NOT EXISTS rate_limits (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    model VARCHAR(100) NOT NULL,
    request_count INTEGER DEFAULT 0,
    last_request TIMESTAMPTZ DEFAULT NOW(),
    reset_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para rendimiento
CREATE INDEX IF NOT EXISTS idx_rate_limits_user_model ON rate_limits(user_id, model);
CREATE INDEX IF NOT EXISTS idx_rate_limits_reset_at ON rate_limits(reset_at);

-- Habilitar RLS (opcional)
ALTER TABLE rate_limits ENABLE ROW LEVEL SECURITY;

-- Policy para que usuarios vean solo sus propios rate limits
CREATE POLICY "Users can view their own rate limits"
ON rate_limits FOR SELECT
USING (auth.uid() = user_id);

-- Policy para que el backend pueda insertar/actualizar (usando service role key)
CREATE POLICY "Service role can manage rate limits"
ON rate_limits FOR ALL
USING (true);
