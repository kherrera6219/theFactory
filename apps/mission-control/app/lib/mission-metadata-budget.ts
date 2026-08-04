/**
 * Keep mission metadata under the API gateway's hard size limit.
 *
 * `MissionCreate` in the gateway rejects the whole request with HTTP 422 when
 * the serialized `metadata` object exceeds 4096 bytes
 * (`_METADATA_MAX_BYTES`, api-gateway/main.py).
 *
 * The chat launch path previously capped each field individually — 6 transcript
 * entries of 2000 chars, 12 decision-memory items of 500, a 4000-char scope —
 * which permits roughly 24 KB, six times the limit. Nothing measured the total.
 *
 * The practical effect was that **PM clarification made missions unlaunchable**:
 * the clarification flow writes three fully-worded questions and then echoes
 * them back with answers, so any mission thorough enough to need clarification
 * produced a transcript that blew the cap. The launch failed with a raw 422 and
 * no indication that size was the cause — the better the PM performed, the more
 * certain the failure.
 *
 * This module fixes that by budgeting the *serialized* object rather than its
 * parts: shed the least valuable content first and stop as soon as it fits.
 */

/** Must match `_METADATA_MAX_BYTES` in services/api-gateway/api_gateway/main.py. */
export const METADATA_MAX_BYTES = 4096;

/**
 * Leave headroom so a later field addition doesn't silently re-break launch.
 * Sized to absorb a few extra keys without another 422.
 */
export const METADATA_SAFETY_MARGIN_BYTES = 256;

export const METADATA_BUDGET_BYTES = METADATA_MAX_BYTES - METADATA_SAFETY_MARGIN_BYTES;

/** Byte length of the value as the gateway will serialize and measure it. */
export function serializedByteLength(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value ?? null)).length;
}

export function fitsBudget(value: unknown, budget = METADATA_BUDGET_BYTES): boolean {
  return serializedByteLength(value) <= budget;
}

interface TranscriptEntry {
  role: string;
  text: string;
  ts?: string;
}

interface ConversationContextLike {
  transcript?: TranscriptEntry[];
  decision_memory?: string[];
  working_contract?: { title?: string; languages?: string; scope?: string; source?: string };
  attached_files?: string[];
  user_intent?: string;
  [key: string]: unknown;
}

function truncate(text: string, max: number): string {
  if (max <= 1) return "";
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

/**
 * Progressively shed conversation context until the whole metadata object fits.
 *
 * Order is chosen so the most decision-relevant content survives longest. The
 * `working_contract` is preserved to the end because it is the distilled result
 * the transcript exists to produce — losing the raw conversation costs little
 * once the contract is settled, whereas losing the contract costs the mission
 * its scope.
 *
 * `buildMetadata` receives the progressively reduced context and must return the
 * full metadata object, so the budget is measured against what is actually sent
 * rather than against the fragment.
 */
export function fitConversationContext<T>(
  context: ConversationContextLike,
  buildMetadata: (context: ConversationContextLike) => T,
  budget = METADATA_BUDGET_BYTES,
): { metadata: T; context: ConversationContextLike; reduced: boolean } {
  let current: ConversationContextLike = { ...context };
  let reduced = false;

  const attempt = () => buildMetadata(current);
  if (fitsBudget(attempt(), budget)) {
    return { metadata: attempt(), context: current, reduced };
  }

  const steps: Array<() => void> = [
    // 1. Drop per-message text to a summary length — usually enough on its own.
    () => {
      current = {
        ...current,
        transcript: (current.transcript ?? []).map((entry) => ({
          ...entry,
          text: truncate(entry.text, 400),
        })),
      };
    },
    // 2. Keep only the most recent exchanges.
    () => {
      current = { ...current, transcript: (current.transcript ?? []).slice(-4) };
    },
    // 3. Trim decision memory, which is largely restated by the contract scope.
    () => {
      current = {
        ...current,
        decision_memory: (current.decision_memory ?? [])
          .slice(-6)
          .map((item) => truncate(item, 160)),
      };
    },
    // 4. Keep only the final exchange.
    () => {
      current = {
        ...current,
        transcript: (current.transcript ?? []).slice(-2).map((entry) => ({
          ...entry,
          text: truncate(entry.text, 200),
        })),
      };
    },
    // 5. Drop the raw transcript entirely; the contract carries the outcome.
    () => {
      current = { ...current, transcript: [], decision_memory: [] };
    },
    // 6. Last resort: shorten the contract scope itself.
    () => {
      const contract = current.working_contract;
      if (contract?.scope) {
        current = {
          ...current,
          working_contract: { ...contract, scope: truncate(contract.scope, 600) },
        };
      }
      current = { ...current, attached_files: (current.attached_files ?? []).slice(0, 5) };
    },
  ];

  for (const step of steps) {
    step();
    reduced = true;
    if (fitsBudget(attempt(), budget)) break;
  }

  return { metadata: attempt(), context: current, reduced };
}
