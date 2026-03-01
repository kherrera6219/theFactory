"use client";

import { useEffect, useMemo, useState } from "react";

const TARGET_LANGUAGES = ["python", "typescript", "go", "rust", "java", "csharp"];

export default function Home() {
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100", []);

  const [prompt, setPrompt] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("python");
  const [mission, setMission] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function submitMission(event) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiBase}/v1/missions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          requested_target_language: targetLanguage,
          metadata: { source: "mission-control" },
        }),
      });

      if (!response.ok) {
        throw new Error(`intake failed: ${response.status}`);
      }

      const data = await response.json();
      setMission(data);
      setEvents([]);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!mission) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const [missionResponse, eventsResponse] = await Promise.all([
          fetch(`${apiBase}/v1/missions/${mission.mission_id}`),
          fetch(`${apiBase}/v1/missions/${mission.mission_id}/events?limit=20`),
        ]);

        if (missionResponse.ok) {
          const data = await missionResponse.json();
          setMission(data);
        }
        if (eventsResponse.ok) {
          const eventData = await eventsResponse.json();
          setEvents(eventData);
        }
      } catch {
        // Keep current UI state if polling fails.
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [apiBase, mission]);

  return (
    <main className="page">
      <section className="panel hero">
        <p className="eyebrow">HolyGrail</p>
        <h1>Mission Control</h1>
        <p>
          Describe the application intent. The backend intake pipeline queues missions into Redis and
          orchestrates lifecycle state in Postgres.
        </p>
      </section>

      <section className="panel form-panel">
        <form onSubmit={submitMission}>
          <label htmlFor="prompt">Mission prompt</label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Build an internal API that translates payroll rules into testable logic nodes."
            rows={6}
            required
          />

          <label htmlFor="targetLanguage">Target language</label>
          <select
            id="targetLanguage"
            value={targetLanguage}
            onChange={(event) => setTargetLanguage(event.target.value)}
          >
            {TARGET_LANGUAGES.map((language) => (
              <option key={language} value={language}>
                {language}
              </option>
            ))}
          </select>

          <button type="submit" disabled={loading || prompt.trim().length < 3}>
            {loading ? "Submitting..." : "Launch Mission"}
          </button>
        </form>
      </section>

      <section className="panel status-panel">
        <h2>Mission Status</h2>
        {error && <p className="error">{error}</p>}
        {!mission && <p>No mission submitted yet.</p>}
        {mission && (
          <dl>
            <div>
              <dt>ID</dt>
              <dd>{mission.mission_id}</dd>
            </div>
            <div>
              <dt>State</dt>
              <dd>{mission.state}</dd>
            </div>
            <div>
              <dt>Target</dt>
              <dd>{mission.requested_target_language ?? "auto"}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{new Date(mission.created_at).toLocaleString()}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="panel">
        <h2>Transition Timeline</h2>
        {!mission && <p>Mission events appear after submission.</p>}
        {mission && events.length === 0 && <p>Waiting for state events...</p>}
        {events.length > 0 && (
          <dl>
            {events.map((event, index) => (
              <div key={`${event.ts}-${index}`}>
                <dt>{event.event_type}</dt>
                <dd>
                  {event.previous_state ? `${event.previous_state} -> ` : ""}
                  {event.new_state} at {new Date(event.ts).toLocaleTimeString()}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </main>
  );
}
