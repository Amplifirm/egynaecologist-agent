-- Adds a flag so the dashboard can show whether each request was captured during
-- working hours (IVR fallback) or out of hours.
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS during_hours BOOL;
