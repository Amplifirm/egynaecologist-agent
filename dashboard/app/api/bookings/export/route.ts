import { getSession } from "@/lib/auth";
import { getSupabase, type Booking } from "@/lib/supabase";

function csvEscape(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export async function GET(req: Request) {
  if (!(await getSession())) {
    return new Response("unauthorized", { status: 401 });
  }
  const { searchParams } = new URL(req.url);
  const range = searchParams.get("range");
  const status = searchParams.get("status");

  const sb = getSupabase();
  let query = sb
    .from("bookings")
    .select("*")
    .order("appointment_date", { ascending: true })
    .order("appointment_time", { ascending: true });

  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }).format(new Date());
  if (range === "today") query = query.eq("appointment_date", today);
  else if (range === "upcoming") query = query.gte("appointment_date", today);
  else if (range === "past") query = query.lt("appointment_date", today);
  if (status && status !== "all") query = query.eq("status", status);

  const { data, error } = await query;
  if (error) return new Response(`error: ${error.message}`, { status: 500 });

  const cols: (keyof Booking)[] = [
    "booking_ref",
    "status",
    "appointment_date",
    "appointment_time",
    "duration_minutes",
    "service_code",
    "service_name",
    "service_price_pence",
    "title",
    "first_name",
    "last_name",
    "date_of_birth",
    "email",
    "phone",
    "reason_for_visit",
    "notes",
    "created_at",
  ];
  const lines = [cols.join(",")];
  for (const row of (data ?? []) as Booking[]) {
    lines.push(cols.map((c) => csvEscape(row[c])).join(","));
  }
  const filename = `bookings-${new Date().toISOString().slice(0, 10)}.csv`;
  return new Response(lines.join("\n"), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
