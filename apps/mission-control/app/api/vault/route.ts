import { NextResponse } from "next/server";

import { deleteVaultSlot, listVaultSlots, upsertVaultSlot } from "../../lib/server/vault";

export const runtime = "nodejs";

type VaultWritePayload = {
  slot_id?: string;
  provider?: string;
  secret?: string;
};

export async function GET() {
  return NextResponse.json({ slots: listVaultSlots() });
}

export async function POST(request: Request) {
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
    const saved = upsertVaultSlot(slotId, provider, secret);
    return NextResponse.json({ slot: saved });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Unable to write vault record." },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request) {
  try {
    const payload = (await request.json()) as { slot_id?: string };
    const slotId = payload.slot_id?.trim() ?? "";
    if (!slotId) {
      return NextResponse.json({ detail: "slot_id is required." }, { status: 400 });
    }
    const removed = deleteVaultSlot(slotId);
    return NextResponse.json({ removed });
  } catch {
    return NextResponse.json({ detail: "Unable to delete vault record." }, { status: 400 });
  }
}

