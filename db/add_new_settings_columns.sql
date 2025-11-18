
-- Add new settings columns to user_settings table
ALTER TABLE public.user_settings 
ADD COLUMN IF NOT EXISTS auto_save BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS save_search_history BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS streaming_enabled BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS confirm_delete BOOLEAN DEFAULT TRUE;

-- Update existing records
UPDATE public.user_settings
SET 
    auto_save = TRUE,
    save_search_history = TRUE,
    streaming_enabled = TRUE,
    confirm_delete = TRUE
WHERE auto_save IS NULL;
