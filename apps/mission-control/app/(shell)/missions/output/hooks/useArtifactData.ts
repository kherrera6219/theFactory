'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  getMission,
  getMissionChainTrace,
} from '../../../../lib/api-client';
import type {
  MissionBuildArtifactRecord,
  MissionChainTrace,
  MissionRecord,
} from '../../../../lib/types';

export type ArtifactDataState = {
  mission: MissionRecord | null;
  chainTrace: MissionChainTrace | null;
  generatedCodeArtifact: MissionBuildArtifactRecord | null;
  allArtifacts: MissionBuildArtifactRecord[];
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export function useArtifactData(missionId: string): ArtifactDataState {
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [chainTrace, setChainTrace] = useState<MissionChainTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!missionId) return;
    setLoading(true);
    setError(null);
    try {
      const [missionData, trace] = await Promise.all([
        getMission(missionId),
        getMissionChainTrace(missionId),
      ]);
      setMission(missionData);
      setChainTrace(trace);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load artifact data.');
    } finally {
      setLoading(false);
    }
  }, [missionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const allArtifacts = chainTrace?.build_artifacts ?? [];
  const generatedCodeArtifact =
    allArtifacts.find((a) => a.artifact_type === 'generated_code') ?? null;

  return {
    mission,
    chainTrace,
    generatedCodeArtifact,
    allArtifacts,
    loading,
    error,
    reload: () => void load(),
  };
}
