import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { parseJsonObject, readTrimmedString } from "../../../lib/server/request-validation";
import { getVaultSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

const API_BASE_URL =
  (process.env.MISSION_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100").trim();

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }
  try {
    const payload = await parseJsonObject(request);
    if (!payload) {
      return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
    }
    const missionId = readTrimmedString(payload, "mission_id");
    const newState = readTrimmedString(payload, "new_state");
    const expectedState = readTrimmedString(payload, "expected_state");
    if (!missionId || !newState) {
      return NextResponse.json(
        { detail: "mission_id and new_state are required." },
        { status: 400 },
      );
    }

    const operatorKey = await getVaultSecret("OPERATOR-API-KEY");
    const internalKey = process.env.INTERNAL_SERVICE_API_KEY ?? "";
    const activeKey = operatorKey || internalKey;
    if (!activeKey) {
      return NextResponse.json(
        { detail: "Internal service key is not configured for mission state updates." },
        { status: 400 },
      );
    }

    const upstream = await fetch(`${API_BASE_URL}/v1/missions/${encodeURIComponent(missionId)}/state`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": activeKey,
      },
      body: JSON.stringify({
        new_state: newState,
        expected_state: expectedState || undefined,
      }),
      cache: "no-store",
    });

    const text = await upstream.text();
    let parsed: unknown = {};
    try {
      parsed = text ? JSON.parse(text) : {};
    } catch {
      parsed = { detail: text || "Unexpected upstream response." };
    }

    if (!upstream.ok) {
      return NextResponse.json(parsed, { status: upstream.status });
    }
    return NextResponse.json(parsed);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Mission state update failed." },
      { status: 500 },
    );
  }
}
