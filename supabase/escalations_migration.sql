-- Settings + escalations schema for working-hours-aware escalation flow.
-- Apply once in the Supabase SQL editor.

-- ============================================================================
-- app_settings — single-row config (key/value)
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO app_settings (key, value) VALUES
    ('hours_mode', 'auto'),                    -- auto | open | closed
    ('escalation_phone', '+447554477038')
ON CONFLICT (key) DO NOTHING;

DROP TRIGGER IF EXISTS app_settings_updated_at ON app_settings;
CREATE TRIGGER app_settings_updated_at BEFORE UPDATE ON app_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- escalations — log of out-of-hours callback requests (or in-hours fallbacks)
-- ============================================================================
CREATE TABLE IF NOT EXISTS escalations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_phone    TEXT NOT NULL,
    callback_phone  TEXT NOT NULL,        -- caller-confirmed best number
    reason          TEXT NOT NULL,
    during_hours    BOOL NOT NULL,        -- false if logged outside working hours
    transferred     BOOL NOT NULL DEFAULT FALSE,  -- true if a live transfer was attempted
    call_sid        TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | resolved | dismissed
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escalations_created ON escalations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_escalations_status  ON escalations(status);

DROP TRIGGER IF EXISTS escalations_updated_at ON escalations;
CREATE TRIGGER escalations_updated_at BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE escalations IS 'Callback requests logged when the bot needs human intervention.';
