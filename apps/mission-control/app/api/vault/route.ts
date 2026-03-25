import { NextResponse } from "next/server";

import { deleteVaultSlot, listVaultSlots, upsertVaultSlot } from "../../lib/server/vault";

export const runtime = "nodejs";

// VAULT_ADMIN_KEY must be set server-side; vault routes are denied if absent.
const VAULT_ADMIN_KEY = process.env.VAULT_ADMIN_KEY?.trim() ?? "";

function isAuthorized(request: Request): boolean {
  if (!VAULT_ADMIN_KEY) {
    // No admin key configured — deny all access to prevent accidental exposure.
    return false;
  }
  const header = request.headers.get("x-vault-admin-key")?.trim() ?? "";
  return header.length > 0 && header === VAULT_ADMIN_KEY;
}

type VaultWritePayload = {
  slot_id?: string;
  provider?: string;
  secret?: string;
};

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ detail: "Unauthorized." }, { status: 401 });
  }
  return NextResponse.json({ slots: await listVaultSlots() });
}

export async function POST(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ detail: "Unauthorized." }, { status: 401 });
  }
  try {
    const payload = (await request.json()) as VaultWritePayload;
    const slotId = payload.slot_id?.trim() ?? "";
    const provider = payload.provider?.trim() ?? "";
    const secret = payload.secret?.trim() ?? "";
    if (!slotId || !provider || !secret) {
      return NextResponse.json(
        { detail: "slot_id, provider, and secret are required." },
        { status: 400 },
      );
    }
    const saved = await upsertVaultSlot(slotId, provider, secret);
    return NextResponse.json({ slot: saved });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Unable to write vault record." },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request) {
  if (!isAuthorized(request)) {
    return NextResponse.json({ detail: "Unauthorized." }, { status: 401 });
  }
  try {
    const payload = (await request.json()) as { slot_id?: string };
    const slotId = payload.slot_id?.trim() ?? "";
    if (!slotId) {
      return NextResponse.json({ detail: "slot_id is required." }, { status: 400 });
    }
    const removed = await deleteVaultSlot(slotId);
    return NextResponse.json({ removed });
  } catch {
    return NextResponse.json({ detail: "Unable to delete vault record." }, { status: 400 });
  }
}
