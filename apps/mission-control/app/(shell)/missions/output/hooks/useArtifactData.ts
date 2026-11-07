'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  getMission,
  getMissionBuildArtifact,
  getMissionChainTrace,
} from '../../../../lib/api-client';
import {
  parseMultiFileBundle,
  type VirtualFileEntry,
} from '../../../../lib/file-tree';
import type {
  MissionRecord,
  MissionChainTrace,
  MissionBuildArtifactRecord,
} from '../../../../lib/types';

export interface ArtifactDataState {
  mission: MissionRecord | null;
  chainTrace: MissionChainTrace | null;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
  allArtifacts: MissionBuildArtifactRecord[];
  virtualFiles: VirtualFileEntry[];
  sourceFilesByPath: Record<string, string>;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches mission + chain-trace data for the Output page, hydrating full
 * artifact_text when omitted from the summary list and unpacking multi-file
 * `## FILE` bundles into navigable VirtualFileEntry items.
 */
export function useArtifactData(missionId: string): ArtifactDataState {
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [chainTrace, setChainTrace] = useState<MissionChainTrace | null>(null);
  const [hydratedArtifact, setHydratedArtifact] = useState<MissionBuildArtifactRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    if (!missionId) {
      setLoading(false);
      return;
    }
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setHydratedArtifact(null);
    try {
      const [missionData, traceData] = await Promise.all([
        getMission(missionId),
        getMissionChainTrace(missionId),
      ]);
      if (requestIdRef.current !== requestId) {
        return;
      }
      setMission(missionData);
      setChainTrace(traceData);

      const primary =
        (traceData.build_artifacts ?? []).find((a) => a.artifact_type === 'generated_code') ??
        (traceData.build_artifacts ?? [])[0] ??
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

  const virtualFiles = useMemo(() => {
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

  const sourceFilesByPath = useMemo(() => {
    const rawSource =
      typeof mission?.metadata?.source_code === 'string'
        ? mission.metadata.source_code
        : '';
    if (!rawSource.trim()) return {};
    const parsed = parseMultiFileBundle(
      rawSource,
      'source.txt',
      mission?.requested_target_language ?? 'text',
    );
    const map: Record<string, string> = {};
    for (const entry of parsed) {
      map[entry.path] = entry.content;
      map[entry.name] = entry.content;
    }
    return map;
  }, [mission]);

  return {
    mission,
    chainTrace,
    generatedCodeArtifact,
    allArtifacts,
    virtualFiles,
    sourceFilesByPath,
    loading,
    error,
  };
}
