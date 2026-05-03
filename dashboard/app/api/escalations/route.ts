import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getSupabase, type Escalation } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  if (!(await getSession())) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const sb = getSupabase();
  const { searchParams } = new URL(req.url);
  const status = searchParams.get("status");

  let q = sb.from("escalations").select("*").order("created_at", { ascending: false }).limit(50);
  if (status && status !== "all") q = q.eq("status", status);

  const { data, error } = await q;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ escalations: (data ?? []) as Escalation[] });
}
