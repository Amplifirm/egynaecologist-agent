import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { getSupabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

const ALLOWED_KEYS = new Set(["hours_mode", "escalation_phone", "agent_enabled"]);
const ALLOWED_VALUES_BY_KEY: Record<string, Set<string> | "free"> = {
  hours_mode: new Set(["auto", "open", "closed"]),
  escalation_phone: "free",
  agent_enabled: new Set(["true", "false"]),
};

export async function GET() {
  if (!(await getSession())) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const sb = getSupabase();
  const { data, error } = await sb.from("app_settings").select("*");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  const map: Record<string, string> = {};
  for (const row of data ?? []) map[row.key] = row.value;
  return NextResponse.json({ settings: map });
}

export async function POST(req: Request) {
  if (!(await getSession())) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }

  const sb = getSupabase();
  const updates: { key: string; value: string }[] = [];
  for (const [k, v] of Object.entries(body)) {
    if (!ALLOWED_KEYS.has(k)) continue;
    const value = String(v);
    const allowed = ALLOWED_VALUES_BY_KEY[k];
    if (allowed !== "free" && !allowed.has(value)) {
      return NextResponse.json({ error: `bad_value_for_${k}` }, { status: 400 });
    }
    updates.push({ key: k, value });
  }

  if (updates.length === 0) return NextResponse.json({ error: "no_updates" }, { status: 400 });

  const { error } = await sb.from("app_settings").upsert(updates, { onConflict: "key" });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, updated: updates.length });
}
