-- Migration: shift from "real bookings" to "appointment requests" since we don't
-- have access to Meddbase's calendar. Run once in the Supabase SQL editor.

-- 1) Make appointment_date / appointment_time nullable (the team will fill these
--    in once they schedule the actual appointment in Meddbase).
ALTER TABLE bookings ALTER COLUMN appointment_date DROP NOT NULL;
ALTER TABLE bookings ALTER COLUMN appointment_time DROP NOT NULL;

-- 2) Drop the no-double-booking constraint (we don't book slots anymore).
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_no_double_booking;

-- 3) Add a free-form column for the availability windows the caller offers
--    (e.g. "Tuesday 10–12, Wednesday 1–3").
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS requested_ranges TEXT;

-- 4) Allow new status values used by the team workflow.
--    pending  → just captured by the agent
--    invited  → team sent a calendar invite within the requested range
--    scheduled → team booked a specific time in Meddbase (filled date/time)
--    declined → team can't honour the request
--    cancelled → caller cancelled
-- (No CHECK constraint — we keep status as free text for flexibility.)

-- 5) New master toggle: is Sophia enabled to take calls right now?
INSERT INTO app_settings (key, value) VALUES ('agent_enabled', 'true')
ON CONFLICT (key) DO NOTHING;
