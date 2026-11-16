import type {
  GithubPrResult,
  MissionSlicePlanItem,
  SliceCompletedRecord,
} from "./types";

export type SliceTimelineItem = {
  id: string;
  title: string;
  status: "verified" | "regressed" | "active" | "paused" | "pending";
  verdict: string | null;
  commitSha: string | null;
  files: string[];
  verifiedAt: string | null;
};

export function buildSliceTimelineItems(
  metadata: Record<string, unknown> | null | undefined,
  plannedSlices?: MissionSlicePlanItem[] | null,
): SliceTimelineItem[] {
  const completedRaw = Array.isArray(metadata?.slices_completed)
    ? (metadata.slices_completed as SliceCompletedRecord[])
    : [];
  const completedById = new Map<string, SliceCompletedRecord>();
  for (const entry of completedRaw) {
    if (entry && typeof entry.id === "string" && entry.id.trim()) {
      completedById.set(entry.id, entry);
    }
  }

  const metaSlices = Array.isArray(metadata?.slices)
    ? (metadata.slices as MissionSlicePlanItem[])
    : [];
  const basePlan =
    plannedSlices && plannedSlices.length > 0 ? plannedSlices : metaSlices;

  const activeSliceRaw = metadata?.active_slice as Record<string, unknown> | undefined;
  const activeSliceId =
    activeSliceRaw && typeof activeSliceRaw.id === "string" ? activeSliceRaw.id : null;
  const slicePaused = metadata?.slice_paused === true;

  const items: SliceTimelineItem[] = [];
  const seen = new Set<string>();

  for (const planned of basePlan) {
    if (!planned || !planned.id) continue;
    seen.add(planned.id);
    const done = completedById.get(planned.id);
    if (done) {
      const verdict = done.verdict ? String(done.verdict) : "PRESERVED";
      const regressed = verdict.toUpperCase() === "REGRESSED";
      items.push({
        id: planned.id,
        title: done.title ?? planned.title ?? planned.id,
        status: regressed ? "regressed" : "verified",
        verdict,
        commitSha: done.commit_sha ? String(done.commit_sha) : null,
        files: Array.isArray(done.files) && done.files.length > 0 ? done.files : planned.files ?? [],
        verifiedAt: done.verified_at ? String(done.verified_at) : null,
      });
    } else if (activeSliceId === planned.id) {
      items.push({
        id: planned.id,
        title: planned.title ?? planned.id,
        status: slicePaused ? "paused" : "active",
        verdict: null,
        commitSha: null,
        files: planned.files ?? [],
        verifiedAt: null,
      });
    } else {
      items.push({
        id: planned.id,
        title: planned.title ?? planned.id,
        status: "pending",
        verdict: null,
        commitSha: null,
        files: planned.files ?? [],
        verifiedAt: null,
      });
    }
  }

  for (const done of completedRaw) {
    if (!done || !done.id || seen.has(done.id)) continue;
    const verdict = done.verdict ? String(done.verdict) : "PRESERVED";
    items.push({
      id: done.id,
      title: done.title ?? done.id,
      status: verdict.toUpperCase() === "REGRESSED" ? "regressed" : "verified",
      verdict,
      commitSha: done.commit_sha ? String(done.commit_sha) : null,
      files: Array.isArray(done.files) ? done.files : [],
      verifiedAt: done.verified_at ? String(done.verified_at) : null,
    });
  }

  return items;
}

export function extractMigrationNotes(
  metadata: Record<string, unknown> | null | undefined,
): string | null {
  const raw = metadata?.migration_notes_md;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed.length > 0 ? raw : null;
}

export function extractGithubPrResult(
  metadata: Record<string, unknown> | null | undefined,
): GithubPrResult | null {
  const raw = metadata?.github_pr_result;
  if (!raw || typeof raw !== "object") return null;
  return raw as GithubPrResult;
}
