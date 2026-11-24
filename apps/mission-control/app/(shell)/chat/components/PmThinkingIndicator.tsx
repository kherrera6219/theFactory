"use client";

import { useEffect, useState } from "react";

import {
  PM_SLOW_AFTER_SECONDS,
  estimatedPmProgress,
  formatElapsed,
  pmStage,
} from "../../../lib/pm-progress";

/**
 * Live "the PM is still working" indicator: elapsed timer, estimated progress
 * bar, and the stage a draft is typically in. Without it a 30–60 s draft looked
 * like a hang. Progress is estimated from time — the PM call has no server-side
 * progress events — and is labelled as such.
 */
export function PmThinkingIndicator() {
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(interval);
  }, []);

  const elapsed = (now - startedAt) / 1000;
  const percent = estimatedPmProgress(elapsed);
  const stage = pmStage(elapsed);
  const slow = elapsed >= PM_SLOW_AFTER_SECONDS;

  return (
    <article className="chat-item pm pm-thinking" aria-label="PM Agent is preparing a response">
      <div className="chat-meta">
        <strong>PM Agent</strong>
        <span className="pm-thinking-elapsed" aria-label={`${Math.floor(elapsed)} seconds elapsed`}>
          <span className="pm-thinking-pulse" aria-hidden="true" />
          {formatElapsed(elapsed)} elapsed
        </span>
      </div>
      <p className="pm-thinking-stage">
        <strong>{stage.label}</strong>
        <span className="muted"> — {stage.detail}</span>
      </p>
      <div
        className={`pm-thinking-meter${slow ? " slow" : ""}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-valuetext={`About ${percent}% (estimated)`}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <p className="muted pm-thinking-note">
        ~{percent}% (estimated) · a Statement of Work usually takes 30–60 seconds
      </p>
    </article>
  );
}
