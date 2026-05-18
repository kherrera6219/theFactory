// Golden fixture — TypeScript source used by test_language_extractor_golden.py.
// Do NOT edit without updating expected values in the golden test.

import { fetchData } from "./utils";

interface MissionPayload {
  id: string;
  prompt: string;
}

type MissionResult = {
  status: string;
};

export class TypeScriptMissionRunner {
  constructor(private readonly apiBaseUrl: string) {}

  async runMission(payload: MissionPayload): Promise<MissionResult> {
    const response = await fetchData(`${this.apiBaseUrl}/missions/${payload.id}`);
    return { status: response.status };
  }

  validate(payload: MissionPayload): boolean {
    return Boolean(payload.id && payload.prompt);
  }
}

export async function submitMission(payload: MissionPayload): Promise<Response> {
  return fetch("/api/missions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const normalizeMission = (payload: MissionPayload): MissionPayload => {
  return {
    ...payload,
    prompt: payload.prompt.trim(),
  };
};
