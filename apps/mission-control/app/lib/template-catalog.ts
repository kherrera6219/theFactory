import type { TemplateRecord } from "./types";

export const TEMPLATE_CATALOG: TemplateRecord[] = [
  {
    id: "tpl-modernize-legacy",
    title: "Legacy Modernization Plan",
    category: "Modernization",
    summary: "Analyze legacy systems, extract LogicNodes, and build phased migration tasks.",
  },
  {
    id: "tpl-quality-audit",
    title: "Enterprise Quality Audit",
    category: "Audit",
    summary: "Run correctness, security, and performance checks with production-grade reporting.",
  },
  {
    id: "tpl-cross-language",
    title: "Cross-Language Equivalence",
    category: "Verification",
    summary: "Compare implementations across languages and generate equivalence proof artifacts.",
  },
];
