"use client";

import { useEffect, useState } from "react";
import { OperatorAuthErrorAction } from "../../../components/operator-auth-error-action";
import { Panel } from "../../../components/panel";
import { SystemMessage } from "../../../components/status";
import type { OfficialFactoryMissionType } from "../../../lib/chat-repo-import";
import type { RepoReviewResponse } from "../../../lib/types";
import { isRasterImageFile, safeFileName } from "../chat-helpers";

function FileChipPreview({ file }: { file: File }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!isRasterImageFile(file)) return;

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  const sizeKb = Math.max(1, Math.round(file.size / 1024));
  const label = safeFileName(file);

  return (
    <li
      className="chip-item"
      style={{
        display: "inline-flex",
        flexDirection: "column",
        gap: "6px",
        padding: "12px",
        border: "1px solid var(--border-strong)",
        borderRadius: "8px",
        background: "var(--bg-elevated)",
        color: "var(--ink)",
      }}
    >
      <span style={{ fontSize: "12px", fontWeight: "bold" }}>
        {label} ({sizeKb}KB)
      </span>
      {previewUrl && (
        <img
          src={previewUrl}
          alt={label}
          style={{
            maxWidth: "200px",
            maxHeight: "150px",
            objectFit: "contain",
            borderRadius: "4px",
            marginTop: "4px",
          }}
        />
      )}
    </li>
  );
}

export interface ChatInputAreaProps {
  input: string;
  setInput: (value: string) => void;
  files: File[];
  addFiles: (fileList: FileList | File[]) => void;
  repoImporting: boolean;
  repoImport: RepoReviewResponse | null;
  preferredOfficialType: OfficialFactoryMissionType | null;
  importAttachedZip: (zip: File) => Promise<void>;
  sendMessage: () => Promise<void>;
  thinking: boolean;
  launching: boolean;
  error: string | null;
}

export function ChatInputArea({
  input,
  setInput,
  files,
  addFiles,
  repoImporting,
  repoImport,
  preferredOfficialType,
  importAttachedZip,
  sendMessage,
  thinking,
  launching,
  error,
}: ChatInputAreaProps) {
  return (
    <Panel title="Message & Files">
      <div
        className="drop-zone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          addFiles(event.dataTransfer.files);
        }}
      >
        Drag and drop files here, or attach a project ZIP to import existing software.
      </div>
      <label className="file-input-label">
        <span>Choose files</span>
        <input
          type="file"
          multiple
          accept=".zip,application/zip,text/plain,text/*,.py,.js,.ts,.go,.rs,.java"
          className="sr-only"
          aria-label="Choose files or a project ZIP to attach"
          onChange={(event) => {
            if (event.target.files) {
              addFiles(event.target.files);
            }
          }}
        />
      </label>
      <label className="file-input-label" style={{ marginLeft: "8px" }}>
        <span>{repoImporting ? "Importing ZIP..." : "Attach project (ZIP)"}</span>
        <input
          type="file"
          accept=".zip,application/zip"
          className="sr-only"
          aria-label="Attach a project ZIP for rework, port, or update"
          disabled={repoImporting || launching}
          onChange={(event) => {
            const zip = event.target.files?.[0];
            if (zip) {
              void importAttachedZip(zip);
            }
            event.currentTarget.value = "";
          }}
        />
      </label>
      {repoImport && (
        <p className="muted" style={{ marginTop: "8px" }}>
          Imported project: {repoImport.repository.display_name} · {repoImport.source_stats.bundled_files} files
          {preferredOfficialType ? ` · ${preferredOfficialType}` : ""}
        </p>
      )}
      {files.length > 0 && (
        <ul
          className="chip-list"
          aria-label="Attached files"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "10px",
            listStyle: "none",
            padding: 0,
            marginTop: "12px",
            marginBottom: "12px",
          }}
        >
          {files.map((file, idx) => (
            <FileChipPreview key={`${file.name}-${idx}`} file={file} />
          ))}
        </ul>
      )}
      <label htmlFor="chat-input">Message</label>
      <textarea
        id="chat-input"
        value={input}
        rows={4}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void sendMessage();
          }
        }}
        placeholder="Analyze this repository and identify reliability risks before delivery."
        autoFocus
      />
      <div className="chat-send-row">
        <button type="button" onClick={() => void sendMessage()} disabled={thinking || launching}>
          {thinking ? "Sending..." : "Send"}
        </button>
      </div>
      {error && (
        <SystemMessage tone="warning" title="Message needs attention">
          <p>{error}</p>
          <OperatorAuthErrorAction error={error} />
        </SystemMessage>
      )}
    </Panel>
  );
}
