import { describe, expect, it } from "vitest";

import {
  MAX_GRAPH_NODES,
  buildLogicNodeGraph,
  readGroup,
  type LogicNodeRecordLike,
} from "./logicnode-graph";

function record(
  nodeId: string,
  node: Record<string, unknown>,
  missionId = "mission-1",
): LogicNodeRecordLike {
  return { mission_id: missionId, node_id: nodeId, node };
}

function typed(
  nodeId: string,
  typesIn: string[],
  typesOut: string[],
  extra: Record<string, unknown> = {},
): LogicNodeRecordLike {
  return record(nodeId, {
    concept: nodeId,
    domain: "parsing",
    types: { in: typesIn, out: typesOut },
    ...extra,
  });
}

describe("buildLogicNodeGraph", () => {
  it("draws a type-flow edge from producer to consumer", () => {
    const graph = buildLogicNodeGraph([
      typed("a", ["str"], ["int"]),
      typed("b", ["int"], ["bool"]),
    ]);

    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0]).toMatchObject({ from: "a", to: "b", via: ["int"] });
  });

  it("does not fabricate edges when nodes carry no types", () => {
    // Regex-extracted languages produce empty types. The honest result is an
    // empty edge set the UI can explain, not a guessed layout.
    const graph = buildLogicNodeGraph([
      typed("a", [], []),
      typed("b", [], []),
    ]);

    expect(graph.edges).toHaveLength(0);
    expect(graph.untyped).toBe(true);
  });

  it("reports untyped=false as soon as any node carries types", () => {
    const graph = buildLogicNodeGraph([typed("a", [], ["int"]), typed("b", [], [])]);
    expect(graph.untyped).toBe(false);
  });

  it("excludes self-edges", () => {
    // A node consuming its own output type is not a dependency on itself.
    const graph = buildLogicNodeGraph([typed("a", ["int"], ["int"])]);
    expect(graph.edges).toHaveLength(0);
  });

  it("merges duplicate edges and unions the justifying types", () => {
    const graph = buildLogicNodeGraph([
      typed("a", [], ["int", "str"]),
      typed("b", ["int", "str"], []),
    ]);

    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0].via.sort()).toEqual(["int", "str"]);
  });

  it("matches types case-insensitively", () => {
    const graph = buildLogicNodeGraph([typed("a", [], ["Int"]), typed("b", ["int"], [])]);
    expect(graph.edges).toHaveLength(1);
  });

  it("layers nodes by longest path", () => {
    const graph = buildLogicNodeGraph([
      typed("a", [], ["t1"]),
      typed("b", ["t1"], ["t2"]),
      typed("c", ["t2"], []),
    ]);

    const layerOf = (id: string) => graph.nodes.find((n) => n.id === id)?.layer;
    expect(layerOf("a")).toBe(0);
    expect(layerOf("b")).toBe(1);
    expect(layerOf("c")).toBe(2);
  });

  it("terminates on a cycle rather than recursing forever", () => {
    // Mutually recursive functions produce a genuine cycle. Refusing to render
    // one would be worse than an approximate layout.
    const graph = buildLogicNodeGraph([
      typed("a", ["t2"], ["t1"]),
      typed("b", ["t1"], ["t2"]),
    ]);

    expect(graph.edges).toHaveLength(2);
    expect(graph.nodes.every((n) => Number.isFinite(n.layer))).toBe(true);
  });

  it("groups nodes by their enclosing function", () => {
    const graph = buildLogicNodeGraph([
      typed("a", [], ["int"], { payload: { types_source: "ast_signature:add" } }),
      typed("b", ["int"], [], { payload: { types_source: "ast_signature:add" } }),
      typed("c", [], [], { payload: { types_source: "ast_signature:save" } }),
    ]);

    expect(graph.groups).toEqual(["add", "save"]);
  });

  it("caps the graph and reports how many nodes were omitted", () => {
    const many = Array.from({ length: MAX_GRAPH_NODES + 7 }, (_, i) => typed(`n${i}`, [], []));
    const graph = buildLogicNodeGraph(many);

    expect(graph.nodes).toHaveLength(MAX_GRAPH_NODES);
    expect(graph.truncated).toBe(7);
  });

  it("surfaces the promoted Phase 3/4 fields", () => {
    const graph = buildLogicNodeGraph([
      typed("a", ["int"], ["int"], {
        confidence: 0.9,
        purity: "IMPURE",
        extraction_method: "ast",
      }),
    ]);

    expect(graph.nodes[0]).toMatchObject({
      confidence: 0.9,
      purity: "IMPURE",
      extractionMethod: "ast",
    });
  });

  it("tolerates malformed node payloads without throwing", () => {
    const graph = buildLogicNodeGraph([
      record("a", {}),
      record("b", { types: "not-an-object" }),
      record("c", { types: { in: [1, null], out: "nope" } }),
      record("d", { payload: "not-an-object" }),
    ]);

    expect(graph.nodes).toHaveLength(4);
    expect(graph.edges).toHaveLength(0);
  });

  it("falls back through concept, cmd, then node id for the label", () => {
    const graph = buildLogicNodeGraph([
      record("podA.x.m.h.1", { concept: "csv_reader" }),
      record("podA.y.m.h.2", { cmd: "csv" }),
      record("podA.z.m.h.3", {}),
    ]);

    expect(graph.nodes.map((n) => n.label)).toEqual(["csv_reader", "csv", "3"]);
  });
});

describe("readGroup", () => {
  it("extracts the function name from an ast_signature marker", () => {
    expect(readGroup({ payload: { types_source: "ast_signature:add" } })).toBe("add");
  });

  it("returns null for a non-signature source", () => {
    expect(readGroup({ payload: { types_source: "regex" } })).toBeNull();
    expect(readGroup({ payload: { types_source: "ast_signature:?" } })).toBeNull();
    expect(readGroup({ payload: {} })).toBeNull();
    expect(readGroup({})).toBeNull();
  });
});
