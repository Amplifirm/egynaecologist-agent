import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth";

export default async function Index() {
  const session = await getSession();
  redirect(session ? "/admin" : "/login");
}
