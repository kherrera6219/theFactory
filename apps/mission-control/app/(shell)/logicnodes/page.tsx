"use client";

import { useEffect, useMemo, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { LogicNodeGraph } from "../../components/logicnode-graph";
import { PageHeader } from "../../components/page-header";
import { Panel } from "../../components/panel";
import { EmptyState, SystemMessage } from "../../components/status";
import { listOperationsLogicNodes } from "../../lib/api-client";
import { formatDateTime } from "../../lib/format";
import type { OperationsLogicNodeRecord } from "../../lib/types";

function extractNodeSummary(node: Record<string, unknown>): {
  intent: string;
  domain: string;
  status: string;
  confidence: string;
} {
  const intent = typeof node.intent === "string" ? node.intent : "Intent not provided";
  const domain = typeof node.domain === "string" ? node.domain : "Unknown";
  const status = typeof node.status === "string" ? node.status : "Unknown";
  const confidenceRaw = node.confidence;
  const confidence =
    typeof confidenceRaw === "number"
      ? `${Math.round(confidenceRaw * 100)}%`
      : typeof confidenceRaw === "string"
        ? confidenceRaw
        : "N/A";
  return { intent, domain, status, confidence };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "string" ? item : asRecord(item).op ?? asRecord(item).kind))
      .filter((item): item is string => typeof item === "string" && item.length > 0);
  }
  return typeof value === "string" && value.length > 0 ? [value] : [];
}

/** Refined-IR fields (Phase 2 enrichment) read defensively from node, payload, or refined_ir. */
function extractRefinedIr(node: Record<string, unknown>): {
  purity: string | null;
  argTypes: string[];
  returnType: string | null;
  sideEffects: string[];
  ops: string[];
} {
  const payload = asRecord(node.payload);
  const refined = asRecord(node.refined_ir);
  const types = asRecord(node.types);
  const pick = (key: string): unknown => node[key] ?? payload[key] ?? refined[key];
  const purityRaw = pick("purity");
  const returnRaw = types.out ?? pick("return_type");
  return {
    purity: typeof purityRaw === "string" ? purityRaw : null,
    argTypes: asStringList(types.in ?? pick("arg_types")),
    returnType: typeof returnRaw === "string" ? returnRaw : null,
    sideEffects: asStringList(pick("side_effects")),
    ops: asStringList(payload.op_stream ?? pick("ops")),
  };
}

function LogicNodesPageContent() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState("");
  const [missionFilter, setMissionFilter] = useState(searchParams.get("mission") ?? "");
  const [nodes, setNodes] = useState<OperationsLogicNodeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const mission = searchParams.get("mission");
    if (mission !== null && mission !== missionFilter) {
      setMissionFilter(mission);
    }
  }, [searchParams, missionFilter]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await listOperationsLogicNodes({
          limit: 300,
          missionId: missionFilter.trim().length > 0 ? missionFilter.trim() : undefined,
        });
        if (!cancelled) {
          setNodes(data);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load LogicNodes.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [missionFilter]);

  const filteredNodes = useMemo(() => {
    const lower = query.trim().toLowerCase();
    return nodes.filter((node) => {
      if (lower.length === 0) {
        return true;
      }
      return (
        node.node_id.toLowerCase().includes(lower) ||
        node.mission_id.toLowerCase().includes(lower) ||
        JSON.stringify(node.node).toLowerCase().includes(lower)
      );
    });
  }, [nodes, query]);

  return (
    <div className="page shell-page">
      <PageHeader
        compact
        eyebrow="LogicNodes"
        title="LogicNode Explorer"
        description="Review extracted logic artifacts, verification confidence, and source lineage for each mission."
      />

      <Panel title="Search and Filters">
        <div className="filters-grid">
          <label>
            Search
            <input
              type="text"
              placeholder="Search by mission id, node id, or node payload"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label>
            Mission ID filter
            <input
              type="text"
              placeholder="Optional mission id"
              value={missionFilter}
              onChange={(event) => setMissionFilter(event.target.value)}
            />
          </label>
        </div>
      </Panel>

      <Panel title="Dependency Graph">
        {loading && <p className="muted">Loading logicnodes...</p>}
        {!loading && !error && filteredNodes.length === 0 && (
          <EmptyState title="Nothing to graph" compact>
            Adjust the search or mission filter to select LogicNodes.
          </EmptyState>
        )}
        {!loading && !error && filteredNodes.length > 0 && (
          <LogicNodeGraph records={filteredNodes} />
        )}
      </Panel>

      <Panel title="Node List">
        {loading && <p className="muted">Loading logicnodes...</p>}
        {error && (
          <SystemMessage tone="critical" title="LogicNode data is unavailable">
            {error} Extracted artifacts will appear after missions can run against the live backend.
          </SystemMessage>
        )}
        {!loading && !error && filteredNodes.length === 0 && (
          <EmptyState title="No LogicNodes match the current criteria" compact>
            {missionFilter.trim().length > 0
              ? "This mission has no LogicNodes. Only missions that extract from existing " +
                "source (IMPORT_MODERNIZE, PORT, DEBUG_REPAIR, ANALYZE_ONLY) produce them — " +
                "a BUILD_NEW mission generates its logic from the mission contract instead, " +
                "and an empty result here is expected."
              : "Run a mission that extracts logic artifacts, or clear the search and mission filters."}
          </EmptyState>
        )}
        {!loading && !error && filteredNodes.length > 0 && (
          <ul className="card-list">
            {filteredNodes.map((node) => {
              const summary = extractNodeSummary(node.node);
              const ir = extractRefinedIr(node.node);
              return (
                <li key={`${node.mission_id}-${node.node_id}`} className="info-card">
                  <h3>{node.node_id}</h3>
                  <p>{summary.intent}</p>
                  <dl className="card-meta">
                    <div>
                      <dt>Mission</dt>
                      <dd>{node.mission_id}</dd>
                    </div>
                    <div>
                      <dt>Domain</dt>
                      <dd>{summary.domain}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>{summary.status}</dd>
                    </div>
                    <div>
                      <dt>Confidence</dt>
                      <dd>{summary.confidence}</dd>
                    </div>
                    <div>
                      <dt>Created</dt>
                      <dd>{formatDateTime(node.created_at)}</dd>
                    </div>
                    {ir.purity && (
                      <div>
                        <dt>Purity</dt>
                        <dd>{ir.purity}</dd>
                      </div>
                    )}
                    {(ir.argTypes.length > 0 || ir.returnType) && (
                      <div>
                        <dt>Signature</dt>
                        <dd>
                          <code>
                            ({ir.argTypes.join(", ")}) → {ir.returnType ?? "?"}
                          </code>
                        </dd>
                      </div>
                    )}
                    {ir.sideEffects.length > 0 && (
                      <div>
                        <dt>Side effects</dt>
                        <dd>{ir.sideEffects.join(", ")}</dd>
                      </div>
                    )}
                    {ir.ops.length > 0 && (
                      <div>
                        <dt>Ops</dt>
                        <dd>{ir.ops.slice(0, 12).join(" · ")}</dd>
                      </div>
                    )}
                  </dl>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}

export default function LogicNodesPage() {
  return (
    <Suspense fallback={<div className="panel-loading-state"><p>Loading logic nodes...</p></div>}>
      <LogicNodesPageContent />
    </Suspense>
  );
}
