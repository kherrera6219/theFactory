// Golden fixture — JavaScript source used by test_language_extractor_golden.py.
// Do NOT edit without updating expected values in the golden test.

import { fetchData } from './utils';
const redis = require('redis');

class MissionRunner {
  constructor(config) {
    this.config = config;
  }

  async run(missionId) {
    const data = await fetchData(missionId);
    return this.process(data);
  }

  process(data) {
    return { result: data };
  }
}

async function submitMission(payload) {
  return fetch('/api/missions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

const validateMission = (mission) => {
  return mission && mission.id && mission.prompt;
};
