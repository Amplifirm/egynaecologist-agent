import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getSupabase, type Booking } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  if (!(await getSession())) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const sb = getSupabase();
  const { searchParams } = new URL(req.url);
  const status = searchParams.get("status");
  const range = searchParams.get("range"); // today | upcoming | past | all
  const q = searchParams.get("q");

  let query = sb
    .from("bookings")
    .select("*")
    .order("appointment_date", { ascending: true })
    .order("appointment_time", { ascending: true });

  if (status && status !== "all") query = query.eq("status", status);

  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }).format(new Date());
  if (range === "today") query = query.eq("appointment_date", today);
  else if (range === "upcoming") query = query.gte("appointment_date", today);
  else if (range === "past") query = query.lt("appointment_date", today);

  if (q) {
    const like = `%${q.replace(/[%_]/g, "")}%`;
    query = query.or(
      `booking_ref.ilike.${like},first_name.ilike.${like},last_name.ilike.${like},email.ilike.${like},phone.ilike.${like}`
    );
  }

  const { data, error } = await query;
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  return NextResponse.json({ bookings: data as Booking[] });
}
