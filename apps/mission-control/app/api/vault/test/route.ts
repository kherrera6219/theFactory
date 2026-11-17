import { NextResponse } from "next/server";

import { isAuthorizedVaultRequest } from "../auth";
import { parseJsonObject, readTrimmedString } from "../../../lib/server/request-validation";
import { getVaultSecret, preflightProviderCall, testSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

export async function POST(request: Request) {
  if (!isAuthorizedVaultRequest(request)) {
    return NextResponse.json({ detail: "Vault authentication required." }, { status: 401 });
  }
  try {
    const payload = await parseJsonObject(request);
    if (!payload) {
      return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
    }
    const slotId = readTrimmedString(payload, "slot_id");
    const provider = readTrimmedString(payload, "provider");
    const model = readTrimmedString(payload, "model") || undefined;
    const rawSecret = readTrimmedString(payload, "secret");
    const secret = rawSecret || (slotId ? await getVaultSecret(slotId) : null);

    if (!provider) {
      return NextResponse.json({ detail: "provider is required." }, { status: 400 });
    }
    if (!secret) {
      return NextResponse.json({ detail: "No secret provided or stored for slot." }, { status: 400 });
    }

    // Fail fast on an obviously malformed secret before spending a real
    // outbound call on it.
    const formatResult = testSecret(provider, secret);
    if (!formatResult.valid) {
      return NextResponse.json({ ...formatResult, live_checked: false });
    }

    const result = await preflightProviderCall(provider, secret, model);
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ detail: "Unable to test key." }, { status: 400 });
  }
}
