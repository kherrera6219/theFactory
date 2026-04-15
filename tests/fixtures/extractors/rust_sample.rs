// Golden fixture — Rust source used by test_language_extractor_golden.py.
// Do NOT edit without updating expected values in the golden test.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct Mission {
    pub id: String,
    pub prompt: String,
    pub state: MissionState,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum MissionState {
    Queued,
    Running,
    Complete,
    Failed,
}

pub fn create_mission(prompt: &str) -> Mission {
    Mission {
        id: uuid::Uuid::new_v4().to_string(),
        prompt: prompt.to_string(),
        state: MissionState::Queued,
    }
}

async fn advance_mission(mission: &mut Mission) -> Result<(), String> {
    match mission.state {
        MissionState::Queued => {
            mission.state = MissionState::Running;
            Ok(())
        }
        _ => Err("invalid transition".to_string()),
    }
}
