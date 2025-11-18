
-- Add missing columns to user_settings table for appearance and notifications

-- Appearance settings
ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS accent_color VARCHAR(7) DEFAULT '#10a37f';

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS font_size INTEGER DEFAULT 16;

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS line_height DECIMAL(3,2) DEFAULT 1.6;

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS chat_width INTEGER DEFAULT 70;

-- Notification settings
ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS message_sounds BOOLEAN DEFAULT true;

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS desktop_notifications BOOLEAN DEFAULT false;

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS mobile_vibration BOOLEAN DEFAULT false;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_user_settings_updated_at ON user_settings(updated_at DESC);

-- Add comment
COMMENT ON COLUMN user_settings.accent_color IS 'UI accent color in hex format';
COMMENT ON COLUMN user_settings.font_size IS 'Font size in pixels';
COMMENT ON COLUMN user_settings.line_height IS 'Line height multiplier';
COMMENT ON COLUMN user_settings.chat_width IS 'Chat width percentage';
