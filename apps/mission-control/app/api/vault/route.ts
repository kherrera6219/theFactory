import { NextResponse } from "next/server";

import { isAuthorizedVaultRequest } from "./auth";
import { parseJsonObject, readTrimmedString } from "../../lib/server/request-validation";
import { deleteVaultSlot, listVaultSlots, upsertVaultSlot } from "../../lib/server/vault";

export const runtime = "nodejs";

function unauthorizedVaultResponse(): NextResponse {
  return NextResponse.json({ detail: "Vault authentication required." }, { status: 401 });
}

export async function GET(request: Request) {
  if (!isAuthorizedVaultRequest(request)) {
    return unauthorizedVaultResponse();
  }
  return NextResponse.json({ slots: await listVaultSlots() });
}

export async function POST(request: Request) {
  if (!isAuthorizedVaultRequest(request)) {
    return unauthorizedVaultResponse();
  }
  try {
    const payload = await parseJsonObject(request);
    if (!payload) {
      return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
    }
    const slotId = readTrimmedString(payload, "slot_id");
    const provider = readTrimmedString(payload, "provider");
    const model = readTrimmedString(payload, "model");
    const secret = readTrimmedString(payload, "secret");
    if (!slotId || !provider || !secret) {
      return NextResponse.json(
        { detail: "slot_id, provider, and secret are required." },
        { status: 400 },
      );
    }
    const saved = await upsertVaultSlot(slotId, provider, secret, model);
    return NextResponse.json({ slot: saved });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Unable to write vault record." },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request) {
  if (!isAuthorizedVaultRequest(request)) {
    return unauthorizedVaultResponse();
  }
  try {
    const payload = await parseJsonObject(request);
    if (!payload) {
      return NextResponse.json({ detail: "Invalid JSON payload." }, { status: 400 });
    }
    const slotId = readTrimmedString(payload, "slot_id");
    if (!slotId) {
      return NextResponse.json({ detail: "slot_id is required." }, { status: 400 });
    }
    const removed = await deleteVaultSlot(slotId);
    return NextResponse.json({ removed });
  } catch {
    return NextResponse.json({ detail: "Unable to delete vault record." }, { status: 400 });
  }
}
