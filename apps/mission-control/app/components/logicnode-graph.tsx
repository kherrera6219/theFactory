"use client";

import { useMemo } from "react";

import {
  buildLogicNodeGraph,
  type GraphNode,
  type LogicNodeRecordLike,
} from "../lib/logicnode-graph";

/**
 * LogicNode dependency graph (UPG-70, design Doc 15 §3.1).
 *
 * Rendered as plain SVG with no graph library. Two reasons: the page runs under
 * a CSP that forbids `unsafe-eval`, which several layout libraries rely on; and
 * the layout this data needs — layered left-to-right by type flow — is simple
 * enough that a dependency would cost more than it saves.
 *
 * The graph is only as good as the underlying data, and says so: when no node
 * carries recovered types there are no edges to draw, and the component
 * explains why instead of rendering a disconnected cloud that reads as a bug.
 */

const NODE_WIDTH = 168;
const NODE_HEIGHT = 46;
const LAYER_GAP = 96;
const ROW_GAP = 18;
const PADDING = 24;

interface PositionedNode extends GraphNode {
  x: number;
  y: number;
}

function purityTone(purity: string | null): string {
  if (purity === "PURE") return "var(--success, #2e7d32)";
  if (purity === "IMPURE") return "var(--warning, #b26a00)";
  return "var(--muted-foreground, #6b7280)";
}

export function LogicNodeGraph({ records }: { records: LogicNodeRecordLike[] }) {
  const graph = useMemo(() => buildLogicNodeGraph(records), [records]);

  const { positioned, width, height } = useMemo(() => {
    const byLayer = new Map<number, GraphNode[]>();
    for (const node of graph.nodes) {
      if (!byLayer.has(node.layer)) byLayer.set(node.layer, []);
      byLayer.get(node.layer)!.push(node);
    }
    const layers = Array.from(byLayer.keys()).sort((a, b) => a - b);
    const placed: PositionedNode[] = [];
    let tallest = 0;

    for (const layer of layers) {
      const column = byLayer.get(layer)!;
      column.forEach((node, index) => {
        placed.push({
          ...node,
          x: PADDING + layer * (NODE_WIDTH + LAYER_GAP),
          y: PADDING + index * (NODE_HEIGHT + ROW_GAP),
        });
      });
      tallest = Math.max(tallest, column.length);
    }

    return {
      positioned: placed,
      width: PADDING * 2 + Math.max(1, layers.length) * (NODE_WIDTH + LAYER_GAP) - LAYER_GAP,
      height: PADDING * 2 + Math.max(1, tallest) * (NODE_HEIGHT + ROW_GAP) - ROW_GAP,
    };
  }, [graph]);

  const positionById = useMemo(() => {
    const map = new Map<string, PositionedNode>();
    for (const node of positioned) map.set(node.id, node);
    return map;
  }, [positioned]);

  if (graph.nodes.length === 0) {
    return <p className="muted">No LogicNodes to graph for the current filter.</p>;
  }

  return (
    <div>
      {graph.untyped && (
        <p className="muted">
          These LogicNodes carry no recovered I/O types, so there are no dependency
          edges to draw. Type recovery currently covers Python, Java, and Haskell —
          nodes extracted from other languages are shown without connections. This
          is the real state of the data, not a rendering failure.
        </p>
      )}
      {graph.truncated > 0 && (
        <p className="muted">
          Showing the first {graph.nodes.length} nodes; {graph.truncated} more are
          omitted to keep the graph readable. Narrow the filter to see them.
        </p>
      )}
      <div style={{ overflowX: "auto", maxWidth: "100%" }}>
        <svg
          role="img"
          aria-label={`LogicNode dependency graph: ${graph.nodes.length} nodes, ${graph.edges.length} type-flow edges`}
          viewBox={`0 0 ${width} ${height}`}
          width={width}
          height={height}
          style={{ maxWidth: "none" }}
        >
          <defs>
            <marker
              id="logicnode-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--border, #9ca3af)" />
            </marker>
          </defs>

          {graph.edges.map((edge) => {
            const from = positionById.get(edge.from);
            const to = positionById.get(edge.to);
            if (!from || !to) return null;
            const x1 = from.x + NODE_WIDTH;
            const y1 = from.y + NODE_HEIGHT / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_HEIGHT / 2;
            const midX = (x1 + x2) / 2;
            return (
              <path
                key={`${edge.from}->${edge.to}`}
                d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="var(--border, #9ca3af)"
                strokeWidth={1.5}
                markerEnd="url(#logicnode-arrow)"
              >
                <title>{`${edge.from} → ${edge.to} via ${edge.via.join(", ")}`}</title>
              </path>
            );
          })}

          {positioned.map((node) => (
            <g key={node.id}>
              <rect
                x={node.x}
                y={node.y}
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={6}
                fill="var(--card, #ffffff)"
                stroke={purityTone(node.purity)}
                strokeWidth={1.5}
              />
              <text
                x={node.x + 10}
                y={node.y + 18}
                fontSize={12}
                fill="var(--foreground, #111827)"
              >
                {node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}
              </text>
              <text
                x={node.x + 10}
                y={node.y + 34}
                fontSize={10}
                fill="var(--muted-foreground, #6b7280)"
              >
                {node.typesIn.length > 0 || node.typesOut.length > 0
                  ? `(${node.typesIn.join(", ")}) → ${node.typesOut.join(", ") || "—"}`
                  : node.domain}
              </text>
              <title>
                {[
                  node.id,
                  node.group ? `function: ${node.group}` : null,
                  `domain: ${node.domain}`,
                  node.purity ? `purity: ${node.purity}` : null,
                  node.extractionMethod ? `extraction: ${node.extractionMethod}` : null,
                  node.confidence !== null
                    ? `confidence: ${Math.round(node.confidence * 100)}%`
                    : null,
                ]
                  .filter(Boolean)
                  .join("\n")}
              </title>
            </g>
          ))}
        </svg>
      </div>
      <p className="muted">
        Edges are <strong>type flow</strong>: an arrow from A to B means a type in
        A&rsquo;s outputs appears in B&rsquo;s inputs. Border colour shows purity —
        green is verified side-effect free, amber has detected effects, grey means
        not analysed. Hover a node or edge for detail.
      </p>
    </div>
  );
}
