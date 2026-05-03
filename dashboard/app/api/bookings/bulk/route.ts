import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getSupabase } from "@/lib/supabase";

type Body = { ids: string[]; status: "pending" | "confirmed" | "cancelled" };

export async function POST(req: Request) {
  if (!(await getSession())) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  if (!Array.isArray(body.ids) || body.ids.length === 0) {
    return NextResponse.json({ error: "no_ids" }, { status: 400 });
  }
  if (!["pending", "confirmed", "cancelled"].includes(body.status)) {
    return NextResponse.json({ error: "bad_status" }, { status: 400 });
  }

  const sb = getSupabase();
  const { data, error } = await sb
    .from("bookings")
    .update({ status: body.status })
    .in("id", body.ids)
    .select();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ bookings: data, count: data?.length ?? 0 });
}
