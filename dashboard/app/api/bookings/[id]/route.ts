import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getSupabase } from "@/lib/supabase";

const EDITABLE = new Set([
  "title",
  "first_name",
  "last_name",
  "date_of_birth",
  "email",
  "phone",
  "reason_for_visit",
  "notes",
  "service_code",
  "service_name",
  "service_price_pence",
  "appointment_date",
  "appointment_time",
  "duration_minutes",
  "status",
]);

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await getSession())) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }

  const updates: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(body)) {
    if (EDITABLE.has(k)) updates[k] = v === "" ? null : v;
  }
  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "no_editable_fields" }, { status: 400 });
  }

  const sb = getSupabase();
  const { data, error } = await sb.from("bookings").update(updates).eq("id", id).select().single();

  if (error) {
    // Translate the UNIQUE(date, time) constraint into a friendlier client error.
    if (error.code === "23505") {
      return NextResponse.json({ error: "slot_taken" }, { status: 409 });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ booking: data });
}

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await getSession())) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const sb = getSupabase();
  const { error } = await sb.from("bookings").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
