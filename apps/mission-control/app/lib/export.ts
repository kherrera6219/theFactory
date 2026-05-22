/**
 * Client-side download utilities (5C).
 *
 * Both helpers work in the browser via the Blob + object-URL pattern.
 * In a future Electron port, replace the anchor-click path with
 * `window.electronAPI.showSaveDialog(blob)` via the IPC bridge.
 */

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Revoke after a tick so the browser has time to initiate the download.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Download any JSON-serialisable value as a pretty-printed .json file. */
export function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  triggerDownload(blob, filename.endsWith(".json") ? filename : `${filename}.json`);
}

/**
 * Download an array of flat objects as a .csv file.
 * Column order matches the keys of the first row.
 * Values are JSON-stringified so embedded commas/quotes survive.
 */
export function downloadCsv(rows: Record<string, unknown>[], filename: string): void {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => JSON.stringify(v ?? "");
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  triggerDownload(blob, filename.endsWith(".csv") ? filename : `${filename}.csv`);
}

/** Flatten a MissionRecord-shaped object to the columns most useful in a CSV export. */
export function missionsToCsvRows(
  missions: Array<Record<string, unknown>>,
): Record<string, unknown>[] {
  return missions.map((m) => ({
    mission_id: m.mission_id,
    name: (m.metadata as Record<string, unknown> | undefined)?.name ?? "",
    state: m.state,
    mission_type: m.mission_type ?? "",
    depth_mode: m.depth_mode ?? "",
    output_mode: m.output_mode ?? "",
    data_classification: m.data_classification ?? "",
    created_at: m.created_at,
  }));
}
