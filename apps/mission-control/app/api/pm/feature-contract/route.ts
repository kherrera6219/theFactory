import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { getVaultSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

const API_BASE_URL =
  process.env.MISSION_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

type FeatureContractPayload = {
  prompt?: string;
  request?: string;
  mission_type?: string;
  depth_mode?: string;
  output_mode?: string;
  requested_target_language?: string | null;
};

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) {
    return unauthorized;
  }

  try {
    const payload = (await request.json()) as FeatureContractPayload;
    const prompt = (payload.prompt ?? payload.request ?? "").trim();
    if (prompt.length < 3) {
      return NextResponse.json(
        { detail: "prompt must be at least 3 characters." },
        { status: 400 },
      );
    }

    const operatorKey = await getVaultSecret("OPERATOR-API-KEY");
    if (!operatorKey) {
      return NextResponse.json(
        {
          detail:
            "Operator API key not found in vault slot OPERATOR-API-KEY. Open Settings, unlock Mission Control, and configure the Operator Runtime Key.",
        },
        { status: 400 },
      );
    }

    const upstream = await fetch(`${API_BASE_URL}/v1/pm/feature-contract`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": operatorKey,
      },
      body: JSON.stringify({ ...payload, prompt }),
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
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
    const marker = error instanceof Error ? `${error.name} ${error.message}`.toLowerCase() : "";
    if (marker.includes("abort") || marker.includes("timeout") || marker.includes("timed out")) {
      return NextResponse.json(
        { detail: "The PM feature-contract request timed out while the runtime was warming up." },
        { status: 504 },
      );
    }
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "PM feature-contract request failed." },
      { status: 500 },
    );
  }
}
