'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { getMission, getMissionChainTrace } from '../../../../lib/api-client';
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
  loading: boolean;
  error: string | null;
}

/**
 * Fetches mission + chain-trace data for the Output page.
 * Re-fetches whenever missionId changes. All data is derived from
 * getMissionChainTrace — no new API endpoints are required.
 */
export function useArtifactData(missionId: string): ArtifactDataState {
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [chainTrace, setChainTrace] = useState<MissionChainTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Monotonic request id — a response for a superseded missionId (the user
  // navigated to a new mission before the previous fetch resolved) must
  // never overwrite state for the mission actually being viewed.
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    if (!missionId) {
      setLoading(false);
      return;
    }
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
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

  const allArtifacts: MissionBuildArtifactRecord[] = chainTrace?.build_artifacts ?? [];
  const generatedCodeArtifact =
    allArtifacts.find((a) => a.artifact_type === 'generated_code') ?? null;

  return { mission, chainTrace, generatedCodeArtifact, allArtifacts, loading, error };
}
