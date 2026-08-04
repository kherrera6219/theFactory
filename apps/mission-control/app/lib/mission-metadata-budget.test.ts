import { describe, expect, it } from "vitest";

import {
  METADATA_BUDGET_BYTES,
  METADATA_MAX_BYTES,
  fitConversationContext,
  fitsBudget,
  serializedByteLength,
} from "./mission-metadata-budget";

/**
 * The gateway rejects a mission when serialized metadata exceeds 4096 bytes.
 *
 * The launch path capped each field separately (6 transcript entries x 2000
 * chars, 12 decision-memory items x 500, a 4000-char scope) which permits ~24 KB
 * — six times the limit — and never measured the total. So any mission that went
 * through PM clarification, which writes three fully-worded questions and then
 * echoes them back with answers, produced a payload over the cap and failed to
 * launch with a bare 422.
 *
 * The fixture below is the real conversation that reproduced it live.
 */

function realWorldContext() {
  const q1 =
    "Should output be written to standard output (stdout) by default or require an explicit output file path via `-o/--output`, and should the JSON be formatted as a pretty-printed array of objects or JSON Lines (NDJSON)? (Recommended default: write pretty-printed JSON array to stdout or to file if `-o` is specified).";
  const q2 =
    "Should data types (integers, floats, booleans, nulls) be automatically inferred during conversion, or should all CSV fields remain as strings in the resulting JSON? (Recommended default: auto-infer numeric/boolean values and convert empty strings to null).";
  const q3 =
    "Should the tool rely strictly on the Python Standard Library (`argparse`, `csv`, `json`) for zero-dependency deployment, or leverage external libraries like `click` or `pandas`? (Recommended default: Python Standard Library only).";

  return {
    transcript: [
      { role: "user", text: "Build a Python command-line tool that converts CSV files to JSON.", ts: "2026-08-04T04:47:03.276Z" },
      { role: "pm", text: `I drafted the current scope and need a few product decisions before launch:\n1. ${q1}\n2. ${q2}\n3. ${q3}\nAnswer these, edit the defaults, or proceed with the recommended defaults.`, ts: "2026-08-04T04:47:12.871Z" },
      { role: "user", text: `Proceed with recommended defaults.\n\n1. ${q1}\nAnswer: write pretty-printed JSON array to stdout or to file if \`-o\` is specified\n\n2. ${q2}\nAnswer: auto-infer numeric/boolean values and convert empty strings to null\n\n3. ${q3}\nAnswer: Python Standard Library only`, ts: "2026-08-04T04:48:10.379Z" },
      { role: "pm", text: "I drafted a feature contract for review. A zero-dependency Python command-line utility that converts CSV files into structured JSON arrays. The tool automatically infers data types and outputs pretty-printed JSON either to stdout or to a destination file using -o/--output.", ts: "2026-08-04T04:48:18.399Z" },
      { role: "user", text: "Build a Python command-line tool that converts CSV files to JSON.", ts: "2026-08-04T05:24:25.660Z" },
    ],
    decision_memory: [q1, q2, q3],
    working_contract: {
      title: "CSV to JSON CLI Converter",
      languages: "python",
      scope:
        "A zero-dependency Python command-line utility that parses CSV files and converts them into structured JSON arrays of objects. The tool automatically infers primitive data types (integers, floats, booleans, and nulls for empty fields) and writes pretty-printed JSON directly to standard output or to a target output file specified via the -o/--output option.",
      source: "llm",
    },
    attached_files: [],
    user_intent: "finalize_plan",
  };
}

/** Mirrors the metadata the chat launch path actually sends. */
function buildMetadata(conversationContext: unknown) {
  return {
    source: "mission-control-chat",
    attached_files: [],
    inferred_requested_target_language: "python",
    conversation_context: conversationContext,
    user_intent: "finalize_plan",
    launch_confirmed_at: "2026-08-04T05:24:58.483Z",
    launch_source: "feature-contract-confirmation",
    continued_from_mission_id: null,
    contract: {
      title: "CSV to JSON CLI Converter",
      languages: "python",
      scope: realWorldContext().working_contract.scope,
      estimated_duration: "~6 minutes",
    },
  };
}

describe("mission metadata budget", () => {
  it("reproduces the real 422: the unbudgeted payload exceeds the gateway cap", () => {
    const oversized = buildMetadata(realWorldContext());
    expect(serializedByteLength(oversized)).toBeGreaterThan(METADATA_MAX_BYTES);
  });

  it("brings that same payload under the limit", () => {
    const { metadata, reduced } = fitConversationContext(realWorldContext(), buildMetadata);
    expect(reduced).toBe(true);
    expect(serializedByteLength(metadata)).toBeLessThanOrEqual(METADATA_BUDGET_BYTES);
    expect(serializedByteLength(metadata)).toBeLessThan(METADATA_MAX_BYTES);
  });

  it("preserves the contract, which is what the mission actually needs", () => {
    const { context } = fitConversationContext(realWorldContext(), buildMetadata);
    expect(context.working_contract?.title).toBe("CSV to JSON CLI Converter");
    expect(context.working_contract?.languages).toBe("python");
    expect(context.working_contract?.scope).toBeTruthy();
  });

  it("leaves a small payload untouched", () => {
    const small = {
      transcript: [{ role: "user", text: "Build a hello world script.", ts: "2026-08-04T00:00:00Z" }],
      decision_memory: [],
      working_contract: { title: "Hello", languages: "python", scope: "Print hello.", source: "llm" },
      attached_files: [],
      user_intent: "finalize_plan",
    };
    const { context, reduced } = fitConversationContext(small, buildMetadata);
    expect(reduced).toBe(false);
    expect(context.transcript).toHaveLength(1);
    expect(context.transcript?.[0].text).toBe("Build a hello world script.");
  });

  it("fits even a pathologically long conversation", () => {
    const huge = {
      transcript: Array.from({ length: 60 }, (_, i) => ({
        role: i % 2 ? "pm" : "user",
        text: "x".repeat(2000),
        ts: "2026-08-04T00:00:00Z",
      })),
      decision_memory: Array.from({ length: 40 }, () => "y".repeat(500)),
      working_contract: { title: "T".repeat(200), languages: "python", scope: "z".repeat(8000), source: "llm" },
      attached_files: Array.from({ length: 50 }, (_, i) => `file-${i}.py`),
      user_intent: "finalize_plan",
    };
    const { metadata } = fitConversationContext(huge, buildMetadata);
    expect(serializedByteLength(metadata)).toBeLessThanOrEqual(METADATA_BUDGET_BYTES);
  });

  it("keeps headroom below the hard cap so a new field cannot silently re-break launch", () => {
    expect(METADATA_BUDGET_BYTES).toBeLessThan(METADATA_MAX_BYTES);
    expect(METADATA_MAX_BYTES - METADATA_BUDGET_BYTES).toBeGreaterThanOrEqual(128);
  });

  it("measures bytes, not characters, so multi-byte text cannot slip past", () => {
    // "é" and "→" are 2 and 3 bytes; a length check would undercount them.
    const text = "é→".repeat(100);
    expect(serializedByteLength(text)).toBeGreaterThan(text.length);
    expect(fitsBudget({ text: "a".repeat(10) })).toBe(true);
  });
});
