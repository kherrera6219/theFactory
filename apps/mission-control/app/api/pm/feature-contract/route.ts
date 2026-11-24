import { NextResponse } from "next/server";

import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { parseJsonObject, readTrimmedString } from "../../../lib/server/request-validation";
import { getActiveLlmRoute, getVaultSecret } from "../../../lib/server/vault";

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
    const prompt = readTrimmedString(payload, "prompt") || readTrimmedString(payload, "request");
    if (prompt.length < 3) {
      return NextResponse.json(
        { detail: "prompt must be at least 3 characters." },
        { status: 400 },
      );
    }

    const operatorKey = await getVaultSecret("OPERATOR-API-KEY");
    const internalKey = process.env.INTERNAL_SERVICE_API_KEY ?? "";
    const activeKey = operatorKey || internalKey;
    if (!activeKey) {
      return NextResponse.json(
        {
          detail:
            "Internal service key is not configured. Set INTERNAL_SERVICE_API_KEY for the local Mission Control stack.",
        },
        { status: 400 },
      );
    }

    const geminiKey = await getVaultSecret("GEMINI-API-KEY");
    const openaiKey = await getVaultSecret("OPENAI-API-KEY");
    const anthropicKey = await getVaultSecret("ANTHROPIC-API-KEY");
    const activeRoute = await getActiveLlmRoute();

    const modifiedPayload = {
      ...payload,
      prompt,
      vault: {
        gemini_api_key: geminiKey || "",
        openai_api_key: openaiKey || "",
        anthropic_api_key: anthropicKey || "",
        ...(activeRoute
          ? { llm_provider: activeRoute.provider, llm_model: activeRoute.model }
          : {}),
      },
    };

    const upstream = await fetch(`${API_BASE_URL}/v1/pm/feature-contract`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": activeKey,
      },
      body: JSON.stringify(modifiedPayload),
      cache: "no-store",
      // Above the gateway's 220 s upstream timeout, below the browser's 240 s.
      signal: AbortSignal.timeout(230_000),
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
        { detail: "The PM Agent did not finish drafting the Statement of Work in time. Your message is kept; send it again to retry." },
        { status: 504 },
      );
    }
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "PM feature-contract request failed." },
      { status: 500 },
    );
  }
}
