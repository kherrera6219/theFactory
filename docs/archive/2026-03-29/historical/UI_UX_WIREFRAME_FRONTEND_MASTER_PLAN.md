# UI/UX Wireframe Gap Analysis and Frontend Master Plan

> Historical note (2026-03-29): This document predates the current 38-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

Date: 2026-03-01  
Scope root: `C:\software\Holygrail`  
Target repo: `C:\software\Holygrail\theFactory`

## 1) Assumptions

- Application runs locally on Windows.
- Standard account login/signup/reset pages are not required.
- Security still applies for local secrets, API keys, and service controls.

## 2) Documentation Reviewed

Primary UI/UX sources:
- `15_Mission_Control_UI_Specification.md`
- `61_User_Stories_Use_Cases.md`
- `62_User_Interaction_Guide.md`
- `63_Graphics_Visual_Design_Style_Guide.md`
- `59_User_Guide.md`
- `01_Product_Requirements_Document.md`
- `04_Product_Roadmap_Phasing_Strategy.md`
- Wireframe notes in `Untitled13` (Section 5.7 flows)

## 3) Current Coverage vs Missing Coverage

### A. Wireframes Already Present (Good Baseline)

- Vibe-driven new app creation flow.
- Repository completion/import flow.
- Application modification and change-review flow.
- Application preview flow.
- Settings/configuration flow.

### B. Missing or Partial Wireframes (Critical Gaps)

1. Mission Control Home Dashboard (`Missing`)
- Needed: overall health, active missions summary, phase/timeline status, quick actions.

2. Agent and Pod Monitoring Views (`Missing`)
- Needed: 35-agent roster, pod-level drill-down, workload/status detail.

3. LogicNode Explorer (`Missing`)
- Needed: graph canvas, filters/search, node detail side panel, lineage/context.

4. Semantic Bus Monitor (`Missing`)
- Needed: live event stream, topic/protocol filters, search, pause/export.

5. Performance/Capacity Views (`Missing`)
- Needed: throughput/latency cards, resource charts, bottleneck indicators.

6. Alerts Center (`Missing`)
- Needed: active alerts, severity states, acknowledgement and resolution history.

7. Mission Results Workspace (`Missing`)
- Needed: quality/optimization findings, artifacts, reports, export actions.

8. Builder Workspace Shell (`Missing`)
- Needed: integrated chat + preview + tabs (code/logs/dependencies/agents).

9. Projects and Templates Management (`Partial`)
- Needed: project catalog, status filters, template gallery, recent/open actions.

## 4) Missing UI Component Inventory (To Design and Build)

Enterprise component gaps:
- App shell: top nav, left nav, breadcrumbs, command palette, status bar.
- Data display: tables with sorting/filtering/pinning, virtualized lists, empty states.
- Observability widgets: timeline rail, event log row, sparkline/line charts, gauges.
- Mission components: mission card, stage progress, dependency graph node/panel.
- Agent components: agent card, pod board, utilization meter.
- Alert components: toast, alert drawer, incident detail panel.
- Workspace components: diff viewer, split preview, activity console, task panel.
- Input/system components: advanced forms, inline validation, confirmation dialogs.
- Accessibility components: skip links, live regions, keyboard shortcut help, focus traps.

## 5) Information Architecture (Enterprise Target, No Login)

Top-level pages:
1. Dashboard
2. Missions
3. Agents & Pods
4. LogicNodes
5. Semantic Bus
6. Performance
7. Alerts
8. Builder Workspace
9. Projects & Templates
10. Settings

Cross-cutting views:
- Mission detail
- Mission results/report
- Artifact viewer
- System logs

## 6) Phased Delivery Plan

### Phase 0: Foundation Alignment (1 week)

- Finalize IA and route map for all pages above.
- Freeze design token strategy from style guide into reusable CSS/token package.
- Define UX acceptance criteria per key flow (submit, monitor, modify, export, recover).

Deliverables:
- Site map v1
- Route contract
- Component taxonomy v1

### Phase 1: Wireframe Completion (2 weeks)

Create low-fidelity wireframes for all missing pages/components:
- Dashboard, Agents & Pods, LogicNodes, Semantic Bus, Performance, Alerts,
  Mission Results, Builder shell, Projects/Templates.

Deliverables:
- Full low-fi wireframe deck
- Interaction states (loading/empty/error/success/stale)
- Mobile + tablet + desktop variants

Exit criteria:
- 100% page coverage against IA
- 100% component coverage for P0/P1 workflows

### Phase 2: Hi-Fi UX + Design System (2 weeks)

- Convert approved wireframes to high-fidelity screens.
- Build reusable component specs: anatomy, variants, states, behavior.
- Define motion and transition rules.

Deliverables:
- High-fidelity UI pack
- Component spec sheets
- Interaction spec (micro/macro behavior)

Exit criteria:
- WCAG 2.2 AA compliance checklist complete
- Design QA pass on consistency and responsiveness

### Phase 3: Frontend Implementation (3-5 weeks)

- Implement app shell + routing + state model.
- Build pages in priority order:
  1) Dashboard + Missions + Mission Results
  2) Agents/Pods + LogicNodes + Semantic Bus
  3) Performance + Alerts + Projects/Templates + Builder shell
- Integrate real data contracts and skeleton states.

Deliverables:
- Production-ready frontend routes
- Shared component library
- Storybook or component showcase (recommended)

Exit criteria:
- All P0/P1 flows functional end-to-end
- Accessibility and responsiveness verified
- No critical UX defects

### Phase 4: Enterprise Hardening (2 weeks)

- Add telemetry for UX events and failure paths.
- Add E2E regression coverage for primary journeys.
- Performance tuning and front-end budgets.
- Final UX audit and release checklist.

Deliverables:
- UX telemetry dashboard
- E2E suite and reliability report
- Release readiness report

## 7) Priority Backlog (Execution Order)

P0:
1. Dashboard wireframe + page
2. Missions list/detail/results wireframes + pages
3. Builder workspace shell wireframe + page frame
4. Agent/Pod monitoring wireframe + page

P1:
1. LogicNode explorer
2. Semantic bus monitor
3. Alerts center
4. Performance dashboard

P2:
1. Projects/templates deep management
2. Advanced export/report UX
3. Visual polish extensions and optional personalization

## 8) Enterprise Standards Checklist

- Accessibility: WCAG 2.2 AA, keyboard complete, screen-reader live updates.
- Resilience: explicit loading/error/retry/stale states on all data surfaces.
- Performance: route-level budgets, virtualization for heavy lists/streams.
- Observability: UX events, error instrumentation, latency/failure tracking.
- Consistency: token-driven design system and component reuse.
- Testability: unit + integration + E2E for all mission-critical flows.
- Local-ops friendly: no login dependency, secure local key handling, robust offline/startup behavior.



