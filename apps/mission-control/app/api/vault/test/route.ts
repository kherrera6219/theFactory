import { NextResponse } from "next/server";

import { isAuthorizedVaultRequest } from "../auth";
import { getVaultSecret, preflightProviderCall, testSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

type VaultTestPayload = {
  slot_id?: string;
  provider?: string;
  secret?: string;
  model?: string;
};

export async function POST(request: Request) {
  if (!isAuthorizedVaultRequest(request)) {
    return NextResponse.json({ detail: "Vault authentication required." }, { status: 401 });
  }
  try {
    const payload = (await request.json()) as VaultTestPayload;
    const slotId = payload.slot_id?.trim() ?? "";
    const provider = payload.provider?.trim() ?? "";
    const secret = payload.secret?.trim() || (slotId ? await getVaultSecret(slotId) : null);

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

    const result = await preflightProviderCall(provider, secret, payload.model);
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ detail: "Unable to test key." }, { status: 400 });
  }
}
