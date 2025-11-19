
-- Agregar columnas faltantes a audit_logs
ALTER TABLE audit_logs 
ADD COLUMN IF NOT EXISTS resource_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS resource_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS details TEXT;

-- Crear índices para mejor rendimiento
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
