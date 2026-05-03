-- eGynaecologist booking schema
-- Run this once in the Supabase SQL editor for a new project.

-- ============================================================================
-- bookings table — the single source of truth
-- ============================================================================
CREATE TABLE IF NOT EXISTS bookings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref     TEXT UNIQUE NOT NULL,          -- e.g. EG-20260502-0001

    -- Service selected
    service_code    TEXT NOT NULL,
    service_name    TEXT NOT NULL,
    service_price_pence INT NOT NULL DEFAULT 0,

    -- Appointment slot
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration_minutes INT  NOT NULL DEFAULT 30,

    -- Patient details (special-category data — RLS enforced)
    title           TEXT,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    date_of_birth   DATE,
    email           TEXT NOT NULL,
    phone           TEXT NOT NULL,
    reason_for_visit TEXT,

    -- Audit
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | cancelled
    call_sid        TEXT,                             -- LiveKit / Twilio call identifier
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Atomic no-double-booking guarantee
    CONSTRAINT bookings_no_double_booking UNIQUE (appointment_date, appointment_time)
);

CREATE INDEX IF NOT EXISTS idx_bookings_date  ON bookings(appointment_date);
CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(email);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bookings_updated_at ON bookings;
CREATE TRIGGER bookings_updated_at BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- try_book_slot — atomic slot reservation
-- ============================================================================
-- Returns (success, error_code) where error_code is 'slot_taken' if the
-- (date, time) is already booked. Race-safe because of the UNIQUE constraint.
CREATE OR REPLACE FUNCTION try_book_slot(
    p_booking_ref       TEXT,
    p_service_code      TEXT,
    p_service_name      TEXT,
    p_service_price_pence INT,
    p_appointment_date  DATE,
    p_appointment_time  TIME,
    p_duration_minutes  INT,
    p_title             TEXT,
    p_first_name        TEXT,
    p_last_name         TEXT,
    p_date_of_birth     DATE,
    p_email             TEXT,
    p_phone             TEXT,
    p_reason_for_visit  TEXT,
    p_call_sid          TEXT
) RETURNS TABLE(success BOOL, error TEXT, booking_ref TEXT) AS $$
BEGIN
    INSERT INTO bookings (
        booking_ref, service_code, service_name, service_price_pence,
        appointment_date, appointment_time, duration_minutes,
        title, first_name, last_name, date_of_birth,
        email, phone, reason_for_visit, call_sid
    ) VALUES (
        p_booking_ref, p_service_code, p_service_name, p_service_price_pence,
        p_appointment_date, p_appointment_time, p_duration_minutes,
        p_title, p_first_name, p_last_name, p_date_of_birth,
        p_email, p_phone, p_reason_for_visit, p_call_sid
    );
    RETURN QUERY SELECT TRUE, NULL::TEXT, p_booking_ref;
EXCEPTION
    WHEN unique_violation THEN
        RETURN QUERY SELECT FALSE, 'slot_taken'::TEXT, p_booking_ref;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- available_slots — list free slots for a date (Mon-Fri 09:00-17:00, 30-min)
-- ============================================================================
CREATE OR REPLACE FUNCTION available_slots(
    p_date DATE,
    p_start_time TIME DEFAULT '09:00',
    p_end_time   TIME DEFAULT '17:00',
    p_step_minutes INT DEFAULT 30
) RETURNS TABLE(slot_time TIME) AS $$
DECLARE
    t TIME := p_start_time;
BEGIN
    -- Reject weekends entirely
    IF EXTRACT(DOW FROM p_date) IN (0, 6) THEN
        RETURN;
    END IF;

    WHILE t < p_end_time LOOP
        IF NOT EXISTS (
            SELECT 1 FROM bookings
            WHERE appointment_date = p_date
              AND appointment_time = t
        ) THEN
            RETURN QUERY SELECT t;
        END IF;
        t := t + (p_step_minutes || ' minutes')::INTERVAL;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Booking reference generator (yyyymmdd-NNNN per day)
-- ============================================================================
CREATE OR REPLACE FUNCTION next_booking_ref(p_date DATE DEFAULT CURRENT_DATE)
RETURNS TEXT AS $$
DECLARE
    v_count INT;
    v_date_str TEXT := TO_CHAR(p_date, 'YYYYMMDD');
BEGIN
    SELECT COUNT(*) + 1 INTO v_count
    FROM bookings
    WHERE booking_ref LIKE 'EG-' || v_date_str || '-%';
    RETURN 'EG-' || v_date_str || '-' || LPAD(v_count::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Row Level Security — patient data is special-category
-- ============================================================================
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (used by the agent backend)
-- Anon and authenticated roles get NO access by default.
-- Add policies here if you later add a front-desk dashboard with auth.

COMMENT ON TABLE bookings IS 'Patient bookings. Special-category data. Backend only via service role.';
