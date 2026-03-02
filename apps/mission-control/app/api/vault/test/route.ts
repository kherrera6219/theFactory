import { NextResponse } from "next/server";

import { getVaultSecret, testSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

type VaultTestPayload = {
  slot_id?: string;
  provider?: string;
  secret?: string;
};

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as VaultTestPayload;
    const slotId = payload.slot_id?.trim() ?? "";
    const provider = payload.provider?.trim() ?? "";
    const secret = payload.secret?.trim() || (slotId ? getVaultSecret(slotId) : null);

    if (!provider) {
      return NextResponse.json({ detail: "provider is required." }, { status: 400 });
    }
    if (!secret) {
      return NextResponse.json({ detail: "No secret provided or stored for slot." }, { status: 400 });
    }

    const result = testSecret(provider, secret);
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ detail: "Unable to test key." }, { status: 400 });
  }
}

