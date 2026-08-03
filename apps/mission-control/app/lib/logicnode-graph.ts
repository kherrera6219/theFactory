/**
 * Derive a dependency graph from LogicNode records (UPG-70).
 *
 * Design Doc 15 §3.1 asked for an interactive LogicNode dependency graph. It was
 * never built, and the audit noted why: before Phase 3 the nodes carried no
 * relationships at all — `types.in`/`types.out` were always empty and everything
 * descriptive sat in a free-form `payload`. There was literally nothing to draw.
 *
 * Phases 3 and 4 changed that, so this module derives the two relationships that
 * genuinely exist in the data rather than inventing a layout:
 *
 * 1. **Co-location** — nodes sharing an enclosing function (`payload.types_source`,
 *    recorded as `ast_signature:<name>`) belong to the same unit of code.
 * 2. **Type flow** — a directed edge from A to B when a type in A's `types.out`
 *    appears in B's `types.in`. This is the closest honest analogue of a
 *    dependency: B can consume what A produces.
 *
 * Nothing here fabricates edges. A regex-extracted language produces nodes with
 * empty types, yields no type-flow edges, and the UI says so explicitly rather
 * than drawing a disconnected cloud that looks like a failure.
 *
 * Kept free of React so it is unit-testable without rendering, and free of any
 * graph library so the page stays within the CSP that forbids `unsafe-eval`.
 */

export interface LogicNodeRecordLike {
  mission_id: string;
  node_id: string;
  node: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  label: string;
  domain: string;
  /** Enclosing function name, when an AST signature was recovered. */
  group: string | null;
  typesIn: string[];
  typesOut: string[];
  confidence: number | null;
  purity: string | null;
  extractionMethod: string | null;
  /** Layer index assigned by longest-path layering; 0 = no inbound edges. */
  layer: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  /** The type names that justify this edge — shown on hover, never invented. */
  via: string[];
}

export interface LogicNodeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** Distinct enclosing functions present, for grouping affordances. */
  groups: string[];
  /** True when no node carried recoverable type data. */
  untyped: boolean;
  /** Nodes omitted because the graph was capped. */
  truncated: number;
}

/** Hard cap: a graph beyond this is unreadable and slow to lay out. */
export const MAX_GRAPH_NODES = 120;

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0);
}

function readTypes(node: Record<string, unknown>): { in: string[]; out: string[] } {
  const types = node.types;
  if (!types || typeof types !== "object") return { in: [], out: [] };
  const record = types as Record<string, unknown>;
  return { in: asStringArray(record.in), out: asStringArray(record.out) };
}

/**
 * Extract the enclosing function name from `payload.types_source`.
 *
 * Phase 4 writes it as `ast_signature:<function name>`; anything else means the
 * types were not recovered from a signature and the node has no group.
 */
export function readGroup(node: Record<string, unknown>): string | null {
  const payload = node.payload;
  if (!payload || typeof payload !== "object") return null;
  const source = asString((payload as Record<string, unknown>).types_source);
  if (!source || !source.startsWith("ast_signature:")) return null;
  const name = source.slice("ast_signature:".length).trim();
  return name && name !== "?" ? name : null;
}

function normaliseType(value: string): string {
  return value.trim().toLowerCase();
}

/**
 * Assign each node a layer via longest-path layering over the edge set.
 *
 * Cycles are tolerated: a node revisited while already on the current path keeps
 * its existing layer rather than recursing forever. Type-flow graphs can
 * legitimately contain cycles (mutually recursive functions), so refusing to
 * render one would be worse than laying it out approximately.
 */
function assignLayers(nodeIds: string[], edges: GraphEdge[]): Map<string, number> {
  const outgoing = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  for (const id of nodeIds) {
    outgoing.set(id, []);
    indegree.set(id, 0);
  }
  for (const edge of edges) {
    if (!outgoing.has(edge.from) || !indegree.has(edge.to)) continue;
    outgoing.get(edge.from)!.push(edge.to);
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
  }

  const layer = new Map<string, number>();
  for (const id of nodeIds) layer.set(id, 0);

  // Kahn-style relaxation. Nodes remaining in a cycle keep layer 0, which is
  // approximate but stable and never loops.
  const queue = nodeIds.filter((id) => (indegree.get(id) ?? 0) === 0);
  const remaining = new Map(indegree);
  const seen = new Set<string>(queue);
  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentLayer = layer.get(current) ?? 0;
    for (const next of outgoing.get(current) ?? []) {
      layer.set(next, Math.max(layer.get(next) ?? 0, currentLayer + 1));
      remaining.set(next, (remaining.get(next) ?? 1) - 1);
      if ((remaining.get(next) ?? 0) <= 0 && !seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }
  return layer;
}

/**
 * Build the dependency graph for a set of LogicNode records.
 *
 * Self-edges are excluded — a node consuming its own output type is not a
 * dependency — and duplicate edges between the same pair are merged, carrying
 * the union of the types that justify them.
 */
export function buildLogicNodeGraph(records: LogicNodeRecordLike[]): LogicNodeGraph {
  const capped = records.slice(0, MAX_GRAPH_NODES);
  const truncated = Math.max(0, records.length - capped.length);

  const nodes: Omit<GraphNode, "layer">[] = capped.map((record) => {
    const node = record.node ?? {};
    const types = readTypes(node);
    const confidenceRaw = node.confidence;
    return {
      id: record.node_id,
      label:
        asString(node.concept) ??
        asString(node.cmd) ??
        record.node_id.split(".").slice(-1)[0] ??
        record.node_id,
      domain: asString(node.domain) ?? "unknown",
      group: readGroup(node),
      typesIn: types.in,
      typesOut: types.out,
      confidence: typeof confidenceRaw === "number" ? confidenceRaw : null,
      purity: asString(node.purity),
      extractionMethod: asString(node.extraction_method),
    };
  });

  // Index producers by the types they emit, so edge building is linear rather
  // than quadratic in the common case.
  const producersByType = new Map<string, string[]>();
  for (const node of nodes) {
    for (const type of node.typesOut) {
      const key = normaliseType(type);
      if (!producersByType.has(key)) producersByType.set(key, []);
      producersByType.get(key)!.push(node.id);
    }
  }

  const edgeMap = new Map<string, GraphEdge>();
  for (const consumer of nodes) {
    for (const type of consumer.typesIn) {
      const key = normaliseType(type);
      for (const producerId of producersByType.get(key) ?? []) {
        if (producerId === consumer.id) continue; // self-edge is not a dependency
        const edgeKey = `${producerId}->${consumer.id}`;
        const existing = edgeMap.get(edgeKey);
        if (existing) {
          if (!existing.via.includes(type)) existing.via.push(type);
        } else {
          edgeMap.set(edgeKey, { from: producerId, to: consumer.id, via: [type] });
        }
      }
    }
  }

  const edges = Array.from(edgeMap.values());
  const layers = assignLayers(
    nodes.map((n) => n.id),
    edges,
  );

  const groups = Array.from(
    new Set(nodes.map((n) => n.group).filter((g): g is string => Boolean(g))),
  ).sort();

  return {
    nodes: nodes.map((node) => ({ ...node, layer: layers.get(node.id) ?? 0 })),
    edges,
    groups,
    untyped: nodes.every((node) => node.typesIn.length === 0 && node.typesOut.length === 0),
    truncated,
  };
}
