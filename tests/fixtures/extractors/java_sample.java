// Golden fixture — Java source used by test_language_extractor_golden.py.
// Do NOT edit without updating expected values in the golden test.

package com.factory.mission;

import java.util.List;
import java.util.Map;
import java.util.Optional;

public class MissionOrchestrator {

    private final MissionRepository repository;

    public MissionOrchestrator(MissionRepository repository) {
        this.repository = repository;
    }

    public Mission createMission(String prompt, String targetLanguage) {
        return repository.save(new Mission(prompt, targetLanguage));
    }

    public Optional<Mission> findById(String missionId) {
        return repository.findById(missionId);
    }

    private boolean isComplete(Mission mission) {
        return "COMPLETE".equals(mission.getState());
    }
}

class MissionRepository {
    public Mission save(Mission m) { return m; }
    public Optional<Mission> findById(String id) { return Optional.empty(); }
}
