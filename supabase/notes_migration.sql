-- Adds an internal notes column for the front-desk dashboard.
-- Run once in the Supabase SQL editor.
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS notes TEXT;
