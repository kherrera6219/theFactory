import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { getVaultSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

const API_BASE_URL =
  process.env.MISSION_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

type MissionStatePayload = {
  mission_id?: string;
  new_state?: string;
  expected_state?: string;
};

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }
  try {
    const payload = (await request.json()) as MissionStatePayload;
    const missionId = payload.mission_id?.trim() ?? "";
    const newState = payload.new_state?.trim() ?? "";
    if (!missionId || !newState) {
      return NextResponse.json(
        { detail: "mission_id and new_state are required." },
        { status: 400 },
      );
    }

    const operatorKey = await getVaultSecret("OPERATOR-API-KEY");
    if (!operatorKey) {
      return NextResponse.json(
        { detail: "Internal service key is not configured for mission state updates." },
        { status: 400 },
      );
    }

    const upstream = await fetch(`${API_BASE_URL}/v1/missions/${encodeURIComponent(missionId)}/state`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": operatorKey,
      },
      body: JSON.stringify({
        new_state: newState,
        expected_state: payload.expected_state ?? undefined,
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
