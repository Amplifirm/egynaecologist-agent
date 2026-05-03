import { createClient, SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

/**
 * Returns a server-only Supabase client using the service role key.
 * NEVER call this from a client component or expose the result to the browser.
 */
export function getSupabase(): SupabaseClient {
  if (client) return client;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.");
  client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return client;
}

export type Escalation = {
  id: string;
  caller_phone: string;
  callback_phone: string;
  reason: string;
  during_hours: boolean;
  transferred: boolean;
  call_sid: string | null;
  status: "pending" | "resolved" | "dismissed";
  resolved_at: string | null;
  resolved_by: string | null;
  notes: string | null;
  created_at: string;
};

export type AppSetting = {
  key: string;
  value: string;
  updated_at: string;
};

export type Booking = {
  id: string;
  booking_ref: string;
  service_code: string;
  service_name: string;
  service_price_pence: number;
  appointment_date: string | null; // YYYY-MM-DD — null until team schedules in Meddbase
  appointment_time: string | null; // HH:MM:SS — null until team schedules in Meddbase
  duration_minutes: number;
  requested_ranges: string | null; // caller-provided availability windows
  title: string | null;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  email: string;
  phone: string;
  reason_for_visit: string | null;
  notes: string | null;
  status: "pending" | "invited" | "scheduled" | "confirmed" | "cancelled" | "declined";
  during_hours: boolean | null;
  transfer_attempted: boolean;
  transfer_succeeded: boolean | null;
  call_sid: string | null;
  created_at: string;
  updated_at: string;
};
