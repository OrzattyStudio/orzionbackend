
-- ============================================================================
-- TRIGGERS PARA auth.users EN SUPABASE
-- ============================================================================
-- Este script crea los triggers necesarios que se ejecutan cuando se registra
-- un nuevo usuario en Supabase Auth
-- ============================================================================

-- Paso 1: Crear función para inicializar user_settings
-- ============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
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
        true,   -- orzion_mini_enabled (gratis)
        false,  -- orzion_turbo_enabled (requiere upgrade)
        false,  -- orzion_pro_enabled (requiere upgrade)
        true,   -- search_enabled
        30,     -- auto_archive_days
        false,  -- terms_accepted
        NULL,   -- terms_accepted_at
        NOW(),
        NOW()
    )
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error creando user_settings para usuario %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$;

-- Paso 2: Crear función para inicializar cuotas de uso
-- ============================================================================
CREATE OR REPLACE FUNCTION public.initialize_user_quotas()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    -- Orzion Pro - Límites estrictos (estilo ChatGPT Free)
    INSERT INTO public.model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Pro', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Turbo - Límites estrictos
    INSERT INTO public.model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Turbo', 5, 15, 50)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    -- Orzion Mini - Límites más generosos
    INSERT INTO public.model_usage_quota (user_id, model, base_limit_hour, base_limit_three_hour, base_limit_day)
    VALUES (NEW.id, 'Orzion Mini', 30, 100, 300)
    ON CONFLICT (user_id, model) DO NOTHING;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error en initialize_user_quotas para usuario %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$;

-- Paso 3: Crear función para inicializar perfil de referidos
-- ============================================================================
CREATE OR REPLACE FUNCTION public.initialize_referral_profile()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    new_code VARCHAR(20);
    code_exists BOOLEAN;
BEGIN
    -- Generar código único de 8 caracteres (lowercase alphanumeric)
    LOOP
        new_code := lower(substr(md5(random()::text || NEW.id::text), 1, 8));
        
        -- Verificar si el código ya existe
        SELECT EXISTS(SELECT 1 FROM public.referral_profiles WHERE referral_code = new_code) INTO code_exists;
        
        -- Salir del loop si el código es único
        EXIT WHEN NOT code_exists;
    END LOOP;
    
    -- Crear perfil de referidos
    INSERT INTO public.referral_profiles (user_id, referral_code)
    VALUES (NEW.id, new_code)
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error en initialize_referral_profile para usuario %: %', NEW.id, SQLERRM;
        RETURN NEW;
END;
$$;

-- Paso 4: Eliminar triggers existentes si existen
-- ============================================================================
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS trigger_initialize_user_quotas ON auth.users;
DROP TRIGGER IF EXISTS trigger_initialize_referral_profile ON auth.users;

-- Paso 5: Crear triggers en auth.users
-- ============================================================================

-- Trigger 1: Crear user_settings
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Trigger 2: Crear cuotas de uso
CREATE TRIGGER trigger_initialize_user_quotas
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.initialize_user_quotas();

-- Trigger 3: Crear perfil de referidos
CREATE TRIGGER trigger_initialize_referral_profile
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.initialize_referral_profile();

-- Paso 6: Verificar que los triggers se crearon correctamente
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ ========================================';
    RAISE NOTICE '✅ Triggers creados exitosamente!';
    RAISE NOTICE '✅ ========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Funciones creadas:';
    RAISE NOTICE '  1. public.handle_new_user()';
    RAISE NOTICE '  2. public.initialize_user_quotas()';
    RAISE NOTICE '  3. public.initialize_referral_profile()';
    RAISE NOTICE '';
    RAISE NOTICE 'Triggers en auth.users:';
    RAISE NOTICE '  1. on_auth_user_created';
    RAISE NOTICE '  2. trigger_initialize_user_quotas';
    RAISE NOTICE '  3. trigger_initialize_referral_profile';
    RAISE NOTICE '';
    RAISE NOTICE 'Ahora puedes registrar nuevos usuarios!';
END $$;

-- Paso 7: Consulta para verificar los triggers
-- ============================================================================
SELECT 
    trigger_name,
    event_object_schema,
    event_object_table,
    action_timing,
    event_manipulation
FROM information_schema.triggers
WHERE event_object_schema = 'auth'
AND event_object_table = 'users'
ORDER BY trigger_name;
