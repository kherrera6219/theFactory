'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  getMission,
  getMissionBuildArtifact,
  getMissionChainTrace,
  getMissionWorkspaceDiff,
  getMissionWorkspaceFile,
  getMissionWorkspaceTree,
} from '../../../../lib/api-client';
import {
  parseMultiFileBundle,
  type VirtualFileEntry,
} from '../../../../lib/file-tree';
import { requestedLanguageFromPath } from '../../../../lib/language';
import type {
  MissionRecord,
  MissionChainTrace,
  MissionBuildArtifactRecord,
  WorkspaceDiffResponse,
  WorkspaceFileResponse,
  WorkspaceTreeResponse,
} from '../../../../lib/types';

export interface ArtifactDataState {
  mission: MissionRecord | null;
  chainTrace: MissionChainTrace | null;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
  allArtifacts: MissionBuildArtifactRecord[];
  virtualFiles: VirtualFileEntry[];
  sourceFilesByPath: Record<string, string>;
  workspaceTree: WorkspaceTreeResponse | null;
  workspaceDiff: WorkspaceDiffResponse | null;
  modifiedPaths: string[];
  loadWorkspaceFile: (filePath: string) => Promise<void>;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches mission + chain-trace data + Git workspace tree/diff for the Output page,
 * hydrating full artifact_text and per-file workspace contents + baseline revisions.
 */
export function useArtifactData(missionId: string): ArtifactDataState {
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [chainTrace, setChainTrace] = useState<MissionChainTrace | null>(null);
  const [hydratedArtifact, setHydratedArtifact] = useState<MissionBuildArtifactRecord | null>(null);
  const [workspaceTree, setWorkspaceTree] = useState<WorkspaceTreeResponse | null>(null);
  const [workspaceDiff, setWorkspaceDiff] = useState<WorkspaceDiffResponse | null>(null);
  const [workspaceFilesByPath, setWorkspaceFilesByPath] = useState<Record<string, WorkspaceFileResponse>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const loadWorkspaceFile = useCallback(
    async (filePath: string) => {
      if (!missionId || !filePath) return;
      const loaded = await getMissionWorkspaceFile(missionId, filePath);
      if (loaded) {
        setWorkspaceFilesByPath((prev) => ({ ...prev, [loaded.path]: loaded }));
      }
    },
    [missionId],
  );

  const load = useCallback(async () => {
    if (!missionId) {
      setLoading(false);
      return;
    }
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setHydratedArtifact(null);
    setWorkspaceTree(null);
    setWorkspaceDiff(null);
    setWorkspaceFilesByPath({});
    try {
      const [missionData, traceData, treeData, diffData] = await Promise.all([
        getMission(missionId),
        getMissionChainTrace(missionId),
        getMissionWorkspaceTree(missionId),
        getMissionWorkspaceDiff(missionId),
      ]);
      if (requestIdRef.current !== requestId) {
        return;
      }
      setMission(missionData);
      setChainTrace(traceData);
      setWorkspaceTree(treeData);
      setWorkspaceDiff(diffData);

      const initialPath =
        treeData?.modified_files?.[0] ?? treeData?.files?.[0]?.path ?? null;
      if (initialPath) {
        void getMissionWorkspaceFile(missionId, initialPath).then((fileData) => {
          if (requestIdRef.current === requestId && fileData) {
            setWorkspaceFilesByPath((prev) => ({ ...prev, [fileData.path]: fileData }));
          }
        });
      }

      const traceArtifacts: MissionBuildArtifactRecord[] = traceData.build_artifacts ?? [];
      const primary =
        traceArtifacts.find((a) => a.artifact_type === 'generated_code') ??
        traceArtifacts[0] ??
        null;
      if (primary && !primary.artifact_text) {
        try {
          const fullRecord = await getMissionBuildArtifact(missionId, primary.artifact_id);
          if (requestIdRef.current === requestId) {
            setHydratedArtifact(fullRecord);
          }
        } catch {
          // Keep summary artifact if detail fetch fails
        }
      }
    } catch (err) {
      if (requestIdRef.current !== requestId) {
        return;
      }
      setError(err instanceof Error ? err.message : 'Failed to load artifact data.');
    } finally {
      if (requestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  }, [missionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const allArtifacts: MissionBuildArtifactRecord[] = useMemo(() => {
    const raw = chainTrace?.build_artifacts ?? [];
    if (!hydratedArtifact) return raw;
    return raw.map((item) =>
      item.artifact_id === hydratedArtifact.artifact_id ? hydratedArtifact : item,
    );
  }, [chainTrace, hydratedArtifact]);

  const generatedCodeArtifact =
    allArtifacts.find((a) => a.artifact_type === 'generated_code') ??
    allArtifacts[0] ??
    null;

  const bundleFiles = useMemo(() => {
    if (!generatedCodeArtifact?.artifact_text) return [];
    const fallbackFilename = String(
      (generatedCodeArtifact.manifest as { filename?: string } | undefined)?.filename ??
        generatedCodeArtifact.artifact_id ??
        'output.txt',
    );
    const fallbackLanguage = String(
      (generatedCodeArtifact.manifest as { language?: string } | undefined)?.language ??
        mission?.requested_target_language ??
        'text',
    );
    return parseMultiFileBundle(
      generatedCodeArtifact.artifact_text,
      fallbackFilename,
      fallbackLanguage,
    );
  }, [generatedCodeArtifact, mission?.requested_target_language]);

  const virtualFiles = useMemo(() => {
    if (!workspaceTree?.files?.length) {
      return bundleFiles;
    }
    const bundleByPath = new Map(bundleFiles.map((f) => [f.path, f]));
    return workspaceTree.files.map((entry): VirtualFileEntry => {
      const loaded = workspaceFilesByPath[entry.path];
      const bundled = bundleByPath.get(entry.path);
      const content = loaded?.content ?? bundled?.content ?? '';
      const slashIdx = entry.path.lastIndexOf('/');
      const name = slashIdx >= 0 ? entry.path.slice(slashIdx + 1) : entry.path;
      const directory = slashIdx >= 0 ? entry.path.slice(0, slashIdx) : '';
      return {
        path: entry.path,
        name,
        directory,
        content,
        sizeBytes: loaded?.size_bytes ?? entry.size_bytes ?? entry.bytes ?? content.length,
        lineCount: content ? content.split('\n').length : entry.estimated_lines,
        language: requestedLanguageFromPath(entry.path) ?? entry.language ?? 'text',
      };
    });
  }, [workspaceTree, bundleFiles, workspaceFilesByPath]);

  const modifiedPaths = useMemo(
    () => workspaceDiff?.modified_files ?? workspaceTree?.modified_files ?? [],
    [workspaceDiff, workspaceTree],
  );

  const sourceFilesByPath = useMemo(() => {
    const map: Record<string, string> = {};
    const rawSource =
      typeof mission?.metadata?.source_code === 'string'
        ? mission.metadata.source_code
        : '';
    if (rawSource.trim()) {
      const parsed = parseMultiFileBundle(
        rawSource,
        'source.txt',
        mission?.requested_target_language ?? 'text',
      );
      for (const entry of parsed) {
        map[entry.path] = entry.content;
        map[entry.name] = entry.content;
      }
    }
    for (const [path, fileData] of Object.entries(workspaceFilesByPath)) {
      if (typeof fileData.baseline_content === 'string') {
        map[path] = fileData.baseline_content;
      }
    }
    return map;
  }, [mission, workspaceFilesByPath]);

  return {
    mission,
    chainTrace,
    generatedCodeArtifact,
    allArtifacts,
    virtualFiles,
    sourceFilesByPath,
    workspaceTree,
    workspaceDiff,
    modifiedPaths,
    loadWorkspaceFile,
    loading,
    error,
  };
}
