
-- ============================================================================
-- LIMPIAR POLÍTICAS RLS DUPLICADAS
-- ============================================================================
-- Este script elimina políticas duplicadas que causan errores
-- ============================================================================

-- Paso 1: Eliminar políticas duplicadas en model_usage_quota
-- ============================================================================
DROP POLICY IF EXISTS "Users can view own quota" ON public.model_usage_quota;
DROP POLICY IF EXISTS "Users can insert own quota" ON public.model_usage_quota;
DROP POLICY IF EXISTS "Users can update own quota" ON public.model_usage_quota;
DROP POLICY IF EXISTS "Service role can manage all quotas" ON public.model_usage_quota;

-- Paso 2: Recrear políticas limpias en model_usage_quota
-- ============================================================================
CREATE POLICY "Users can view own quota"
    ON public.model_usage_quota
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own quota"
    ON public.model_usage_quota
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own quota"
    ON public.model_usage_quota
    FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage all quotas"
    ON public.model_usage_quota
    FOR ALL
    USING (auth.role() = 'service_role');

-- Paso 3: Eliminar políticas duplicadas en referral_profiles
-- ============================================================================
DROP POLICY IF EXISTS "Users can view own referral profile" ON public.referral_profiles;
DROP POLICY IF EXISTS "Users can update own referral profile" ON public.referral_profiles;
DROP POLICY IF EXISTS "Service role can manage all referral profiles" ON public.referral_profiles;

-- Paso 4: Recrear políticas limpias en referral_profiles
-- ============================================================================
CREATE POLICY "Users can view own referral profile"
    ON public.referral_profiles
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own referral profile"
    ON public.referral_profiles
    FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage all referral profiles"
    ON public.referral_profiles
    FOR ALL
    USING (auth.role() = 'service_role');

-- Paso 5: Verificar que los triggers estén en el esquema correcto
-- ============================================================================
SELECT 
    'TRIGGER' as tipo,
    t.tgname as nombre,
    n.nspname as esquema_tabla,
    c.relname as tabla,
    p.proname as funcion
FROM pg_trigger t
JOIN pg_class c ON t.tgrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
JOIN pg_proc p ON t.tgfoid = p.oid
WHERE c.relname = 'users' AND n.nspname = 'auth'
ORDER BY t.tgname;

-- Paso 6: Verificar que las funciones estén en public
-- ============================================================================
SELECT 
    'FUNCION' as tipo,
    p.proname as nombre,
    n.nspname as esquema
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE p.proname IN (
    'handle_new_user',
    'initialize_user_quotas',
    'initialize_referral_profile'
)
ORDER BY p.proname;

-- Paso 7: Mensaje de confirmación
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ ========================================';
    RAISE NOTICE '✅ Políticas RLS limpiadas correctamente!';
    RAISE NOTICE '✅ ========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Estado actual:';
    RAISE NOTICE '  - Triggers: en esquema auth.users ✓';
    RAISE NOTICE '  - Funciones: en esquema public ✓';
    RAISE NOTICE '  - Políticas RLS: recreadas sin duplicados ✓';
    RAISE NOTICE '';
    RAISE NOTICE 'Ahora puedes registrar usuarios sin errores!';
END $$;
