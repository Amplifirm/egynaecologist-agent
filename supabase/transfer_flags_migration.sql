-- Tracks whether a transfer was attempted on the call that produced this booking,
-- and whether it succeeded. Lets the dashboard tag bookings without needing a
-- separate "ghost" escalation row pre-created at dial time.
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS transfer_attempted BOOL NOT NULL DEFAULT FALSE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS transfer_succeeded BOOL;
