import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(req: NextRequest) {
  const { passphrase } = await req.json();
  const expected = process.env.ACCESS_PASSPHRASE;

  if (!expected || passphrase !== expected) {
    return NextResponse.json({ error: "Invalid passphrase" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set("om_session", "authenticated", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: "/",
  });

  return NextResponse.json({ ok: true });
}
