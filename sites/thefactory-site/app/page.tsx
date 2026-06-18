const metrics = [
  ["41", "agent registry"],
  ["22/22", "production audit"],
  ["97", "offline evals and unit tests"],
  ["23", "Playwright E2E specs"],
];

const lifecycle = [
  "Intake",
  "Fetch",
  "Smelt",
  "Gating",
  "Fusion",
  "Squeeze",
  "Delivery",
];

const capabilities = [
  {
    title: "Mission Control",
    body: "A local-first operator console for mission intake, agent telemetry, protocol-bus activity, data-plane health, and review approvals.",
  },
  {
    title: "Task-activated agents",
    body: "Interface, executive, support, and pod-specialist roles activate only when the mission needs them, then return to idle.",
  },
  {
    title: "Evidence-driven delivery",
    body: "Missions produce charters, plans, diffs, test results, runtime QC output, approvals, and audit records instead of untraceable prompt output.",
  },
  {
    title: "Local data plane",
    body: "Postgres, Redis, Qdrant, Milvus, Neo4j, MinIO, and the observability stack run in the local deployment profile.",
  },
];

const modes = [
  "Build new applications",
  "Modernize existing repos",
  "Port across platforms",
  "Debug and repair",
  "Security harden",
  "Reduce dependencies",
  "Run and QC",
  "Analyze and document",
];

export default function Home() {
  return (
    <main>
      <section className="hero">
        <nav className="nav" aria-label="Primary">
          <a className="brand" href="#top" aria-label="theFactory home">
            <span aria-hidden="true" />
            theFactory
          </a>
          <div className="nav-links">
            <a href="#system">System</a>
            <a href="#lifecycle">Lifecycle</a>
            <a href="#status">Status</a>
          </div>
        </nav>

        <div className="hero-grid" id="top">
          <div className="hero-copy">
            <p className="eyebrow">Local-first AI software production</p>
            <h1>theFactory</h1>
            <p className="lead">
              A governed software factory that turns natural-language missions
              into requirements, architecture, code, tests, runtime validation,
              and audit-ready evidence.
            </p>
            <div className="actions" aria-label="Project links">
              <a href="#lifecycle">See the pipeline</a>
              <a href="#status">Current baseline</a>
            </div>
          </div>

          <div className="console" aria-label="Mission Control product preview">
            <div className="console-top">
              <span />
              <strong>Mission Pipeline</strong>
              <small>Local runtime</small>
            </div>
            <div className="pipeline-board">
              {["Intake", "Planning", "Execution", "Verification"].map(
                (stage, index) => (
                  <div className="pipeline-column" key={stage}>
                    <div className="column-title">
                      {stage}
                      <span>{index + 2}</span>
                    </div>
                    {[0, 1, 2].map((item) => (
                      <div className="mission-row" key={item}>
                        <span />
                        <i />
                      </div>
                    ))}
                  </div>
                ),
              )}
            </div>
            <div className="console-lower">
              <div className="topology">
                {Array.from({ length: 10 }).map((_, index) => (
                  <span key={index} />
                ))}
              </div>
              <div className="health">
                {["Postgres", "Redis", "Qdrant", "MinIO"].map((item) => (
                  <div key={item}>
                    <span>{item}</span>
                    <strong>healthy</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="metric-band" aria-label="Implementation metrics">
        {metrics.map(([value, label]) => (
          <div key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>

      <section className="section" id="system">
        <div className="section-heading">
          <p className="eyebrow">What it is</p>
          <h2>Not a code-completion tool. A production system.</h2>
          <p>
            theFactory is built for work that needs traceability: modernization,
            porting, debugging, security hardening, dependency reduction, and
            release-ready implementation.
          </p>
        </div>

        <div className="capability-grid">
          {capabilities.map((capability) => (
            <article className="capability" key={capability.title}>
              <h3>{capability.title}</h3>
              <p>{capability.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section split" id="lifecycle">
        <div>
          <p className="eyebrow">Smelt-Cycle</p>
          <h2>Every mission moves through a visible delivery pipeline.</h2>
          <p>
            The current default runtime uses Mission Flow v2, a seven-phase
            lifecycle that moves work from operator intent to evidence-backed
            release handoff.
          </p>
        </div>
        <div className="lifecycle">
          {lifecycle.map((step, index) => (
            <div className="step" key={step}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="section modes">
        <div className="section-heading">
          <p className="eyebrow">Mission modes</p>
          <h2>Designed for more than greenfield generation.</h2>
        </div>
        <div className="mode-grid">
          {modes.map((mode) => (
            <span key={mode}>{mode}</span>
          ))}
        </div>
      </section>

      <section className="section status" id="status">
        <div>
          <p className="eyebrow">Current baseline</p>
          <h2>v1.2.0 is the implementation baseline.</h2>
          <p>
            Phases 1-27 are complete. The next validation target is a live
            Gemini-key operator run that proves a BUILD_NEW mission reaches
            COMPLETE with generated code.
          </p>
        </div>
        <aside>
          <strong>No phase-baseline release blockers</strong>
          <span>Gemini-first validation remains the public-launch proof point.</span>
        </aside>
      </section>
    </main>
  );
}
