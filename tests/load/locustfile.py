from locust import HttpUser, between, task


class MissionLoadUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def submit_and_check_mission(self) -> None:
        create = self.client.post(
            "/v1/missions",
            json={
                "prompt": "Load test mission for orchestration throughput",
                "requested_target_language": "python",
                "metadata": {"source": "locust"},
            },
        )
        if create.status_code >= 400:
            return
        mission_id = create.json().get("mission_id")
        if not mission_id:
            return
        self.client.get(f"/v1/missions/{mission_id}")
        self.client.get(f"/v1/missions/{mission_id}/events?limit=10")
