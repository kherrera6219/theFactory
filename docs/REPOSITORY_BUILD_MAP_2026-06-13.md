# Repository Build Map

Document version: 2026.03.29
Generated at: 2026-06-13T19:43:53+00:00
Repository root: `C:\software\Holygrail\theFactory`

This map is generated from the current filesystem so it can be reproduced and reviewed as code.

## Inclusion Rules

- Includes all files and folders under the repository root except cache/vendor directories that are not part of the maintained application source tree.
- Excludes `.claude`, `.git`, `.pytest_cache`, `.ruff_cache`, `.next`, `.venv`, `node_modules`, `playwright-report`, `test-results`, and `__pycache__` directories.
- Paths are shown exactly as present at generation time.

## Summary

- Directories included: `315`
- Files included: `1902`

## Tree

```text
theFactory
├── .github
│   ├── ISSUE_TEMPLATE
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── security_report.md
│   ├── workflows
│   │   ├── ci.yml
│   │   ├── qualification.yml
│   │   ├── release.yml
│   │   └── security.yml
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── apps
│   └── mission-control
│       ├── app
│       │   ├── (shell)
│       │   │   ├── agents
│       │   │   │   └── page.tsx
│       │   │   ├── alerts
│       │   │   │   └── page.tsx
│       │   │   ├── audit
│       │   │   │   └── page.tsx
│       │   │   ├── builder
│       │   │   │   └── page.tsx
│       │   │   ├── chat
│       │   │   │   └── page.tsx
│       │   │   ├── dashboard
│       │   │   │   └── page.tsx
│       │   │   ├── databases
│       │   │   │   └── page.tsx
│       │   │   ├── logicnodes
│       │   │   │   └── page.tsx
│       │   │   ├── missions
│       │   │   │   ├── detail
│       │   │   │   │   ├── panels
│       │   │   │   │   │   ├── intelligence
│       │   │   │   │   │   │   ├── AimPanel.tsx
│       │   │   │   │   │   │   ├── DependencyAbsorptionPanel.tsx
│       │   │   │   │   │   │   ├── EquivalenceReportPanel.tsx
│       │   │   │   │   │   │   ├── FusionPanel.tsx
│       │   │   │   │   │   │   ├── KnowledgeLakePanel.tsx
│       │   │   │   │   │   │   ├── LogicClustersPanel.tsx
│       │   │   │   │   │   │   ├── PodGroupStandardsPanel.tsx
│       │   │   │   │   │   │   ├── RuntimeQcPanel.tsx
│       │   │   │   │   │   │   └── SecurityCompliancePanel.tsx
│       │   │   │   │   │   ├── operational
│       │   │   │   │   │   │   ├── ActiveAgentsPanel.tsx
│       │   │   │   │   │   │   ├── ChainOfCommandTracePanel.tsx
│       │   │   │   │   │   │   ├── DeliveryPanel.tsx
│       │   │   │   │   │   │   ├── GeneratedOutputPanel.tsx
│       │   │   │   │   │   │   ├── LogicNodeProgressPanel.tsx
│       │   │   │   │   │   │   ├── MissionCharterPanel.tsx
│       │   │   │   │   │   │   ├── MissionContractPanel.tsx
│       │   │   │   │   │   │   ├── MissionSignalsPanel.tsx
│       │   │   │   │   │   │   ├── PmFeatureContractPanel.tsx
│       │   │   │   │   │   │   └── RouteProvenancePanel.tsx
│       │   │   │   │   │   ├── telemetry
│       │   │   │   │   │   │   ├── AuditEvidencePanel.tsx
│       │   │   │   │   │   │   ├── CostPanel.tsx
│       │   │   │   │   │   │   └── MissionEventLogPanel.tsx
│       │   │   │   │   │   └── index.ts
│       │   │   │   │   └── page.tsx
│       │   │   │   ├── history
│       │   │   │   │   └── page.tsx
│       │   │   │   ├── output
│       │   │   │   │   ├── components
│       │   │   │   │   │   ├── ArtifactMetaPane.tsx
│       │   │   │   │   │   ├── CodeViewerPane.tsx
│       │   │   │   │   │   ├── FileTreePane.tsx
│       │   │   │   │   │   └── OutputHeader.tsx
│       │   │   │   │   ├── hooks
│       │   │   │   │   │   └── useArtifactData.ts
│       │   │   │   │   └── page.tsx
│       │   │   │   └── page.tsx
│       │   │   ├── performance
│       │   │   │   └── page.tsx
│       │   │   ├── projects
│       │   │   │   └── page.tsx
│       │   │   ├── protocol-bus
│       │   │   │   └── page.tsx
│       │   │   ├── repo
│       │   │   │   └── page.tsx
│       │   │   ├── settings
│       │   │   │   └── page.tsx
│       │   │   ├── error.tsx
│       │   │   ├── layout.tsx
│       │   │   ├── loading.tsx
│       │   │   ├── not-found.tsx
│       │   │   └── page.tsx
│       │   ├── api
│       │   │   ├── builder
│       │   │   │   └── review
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   ├── gateway
│       │   │   │   └── [...path]
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   ├── operator
│       │   │   │   └── mission-state
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   ├── pm
│       │   │   │   └── feature-contract
│       │   │   │       └── route.ts
│       │   │   ├── repo
│       │   │   │   ├── import
│       │   │   │   │   ├── route.test.ts
│       │   │   │   │   └── route.ts
│       │   │   │   ├── review
│       │   │   │   │   ├── route.test.ts
│       │   │   │   │   └── route.ts
│       │   │   │   └── shared.ts
│       │   │   ├── review
│       │   │   │   ├── approve
│       │   │   │   │   ├── route.test.ts
│       │   │   │   │   └── route.ts
│       │   │   │   └── verify
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   ├── session
│       │   │   │   ├── logout
│       │   │   │   │   └── route.ts
│       │   │   │   └── unlock
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   └── vault
│       │   │       ├── test
│       │   │       │   ├── route.test.ts
│       │   │       │   └── route.ts
│       │   │       ├── auth.test.ts
│       │   │       ├── auth.ts
│       │   │       ├── route.test.ts
│       │   │       └── route.ts
│       │   ├── components
│       │   │   ├── command-palette.tsx
│       │   │   ├── copy-id.tsx
│       │   │   ├── dialog-provider.tsx
│       │   │   ├── electron-titlebar.tsx
│       │   │   ├── error-boundary.tsx
│       │   │   ├── global-search.tsx
│       │   │   ├── guided-tour.tsx
│       │   │   ├── keyboard-shortcuts.tsx
│       │   │   ├── logout-button.tsx
│       │   │   ├── notification-bell.tsx
│       │   │   ├── operator-unlock-form.tsx
│       │   │   ├── page-header.tsx
│       │   │   ├── panel.tsx
│       │   │   ├── reconnect-banner.tsx
│       │   │   ├── shell-header-meta.tsx
│       │   │   ├── shell-nav.tsx
│       │   │   ├── status.tsx
│       │   │   └── tooltip.tsx
│       │   ├── lib
│       │   │   ├── server
│       │   │   │   ├── operator-session.test.ts
│       │   │   │   ├── operator-session.ts
│       │   │   │   ├── review-approvals.ts
│       │   │   │   ├── vault.test.ts
│       │   │   │   └── vault.ts
│       │   │   ├── test
│       │   │   │   └── server-only.ts
│       │   │   ├── types
│       │   │   │   ├── api.gen.ts
│       │   │   │   └── api.ts
│       │   │   ├── api-client.test.ts
│       │   │   ├── api-client.ts
│       │   │   ├── electron-bridge.ts
│       │   │   ├── export.ts
│       │   │   ├── format.ts
│       │   │   ├── glossary.ts
│       │   │   ├── language.test.ts
│       │   │   ├── language.ts
│       │   │   ├── mock-data.ts
│       │   │   ├── navigation.ts
│       │   │   ├── security.ts
│       │   │   ├── smelt-cycle.test.ts
│       │   │   ├── smelt-cycle.ts
│       │   │   ├── template-catalog.ts
│       │   │   ├── types.ts
│       │   │   └── use-last-refreshed.ts
│       │   ├── unlock
│       │   │   └── page.tsx
│       │   ├── error.tsx
│       │   ├── generated-tokens.css
│       │   ├── globals.css
│       │   ├── layout.tsx
│       │   └── not-found.tsx
│       ├── dist
│       │   ├── electron
│       │   │   ├── app
│       │   │   │   └── lib
│       │   │   │       ├── electron-bridge.js
│       │   │   │       └── electron-bridge.js.map
│       │   │   └── electron
│       │   │       ├── diagnostics.js
│       │   │       ├── diagnostics.js.map
│       │   │       ├── main.js
│       │   │       ├── main.js.map
│       │   │       ├── preload.js
│       │   │       ├── preload.js.map
│       │   │       ├── tray.js
│       │   │       ├── tray.js.map
│       │   │       ├── updater.js
│       │   │       └── updater.js.map
│       │   └── installers
│       │       ├── win-unpacked
│       │       │   ├── locales
│       │       │   │   ├── af.pak
│       │       │   │   ├── am.pak
│       │       │   │   ├── ar.pak
│       │       │   │   ├── bg.pak
│       │       │   │   ├── bn.pak
│       │       │   │   ├── ca.pak
│       │       │   │   ├── cs.pak
│       │       │   │   ├── da.pak
│       │       │   │   ├── de.pak
│       │       │   │   ├── el.pak
│       │       │   │   ├── en-GB.pak
│       │       │   │   ├── en-US.pak
│       │       │   │   ├── es-419.pak
│       │       │   │   ├── es.pak
│       │       │   │   ├── et.pak
│       │       │   │   ├── fa.pak
│       │       │   │   ├── fi.pak
│       │       │   │   ├── fil.pak
│       │       │   │   ├── fr.pak
│       │       │   │   ├── gu.pak
│       │       │   │   ├── he.pak
│       │       │   │   ├── hi.pak
│       │       │   │   ├── hr.pak
│       │       │   │   ├── hu.pak
│       │       │   │   ├── id.pak
│       │       │   │   ├── it.pak
│       │       │   │   ├── ja.pak
│       │       │   │   ├── kn.pak
│       │       │   │   ├── ko.pak
│       │       │   │   ├── lt.pak
│       │       │   │   ├── lv.pak
│       │       │   │   ├── ml.pak
│       │       │   │   ├── mr.pak
│       │       │   │   ├── ms.pak
│       │       │   │   ├── nb.pak
│       │       │   │   ├── nl.pak
│       │       │   │   ├── pl.pak
│       │       │   │   ├── pt-BR.pak
│       │       │   │   ├── pt-PT.pak
│       │       │   │   ├── ro.pak
│       │       │   │   ├── ru.pak
│       │       │   │   ├── sk.pak
│       │       │   │   ├── sl.pak
│       │       │   │   ├── sr.pak
│       │       │   │   ├── sv.pak
│       │       │   │   ├── sw.pak
│       │       │   │   ├── ta.pak
│       │       │   │   ├── te.pak
│       │       │   │   ├── th.pak
│       │       │   │   ├── tr.pak
│       │       │   │   ├── uk.pak
│       │       │   │   ├── ur.pak
│       │       │   │   ├── vi.pak
│       │       │   │   ├── zh-CN.pak
│       │       │   │   └── zh-TW.pak
│       │       │   ├── resources
│       │       │   │   ├── app.asar.unpacked
│       │       │   │   ├── app.asar
│       │       │   │   └── elevate.exe
│       │       │   ├── chrome_100_percent.pak
│       │       │   ├── chrome_200_percent.pak
│       │       │   ├── d3dcompiler_47.dll
│       │       │   ├── ffmpeg.dll
│       │       │   ├── icudtl.dat
│       │       │   ├── libEGL.dll
│       │       │   ├── libGLESv2.dll
│       │       │   ├── LICENSE.electron.txt
│       │       │   ├── LICENSES.chromium.html
│       │       │   ├── resources.pak
│       │       │   ├── snapshot_blob.bin
│       │       │   ├── theFactory Mission Control.exe
│       │       │   ├── v8_context_snapshot.bin
│       │       │   ├── vk_swiftshader.dll
│       │       │   ├── vk_swiftshader_icd.json
│       │       │   └── vulkan-1.dll
│       │       ├── builder-debug.yml
│       │       ├── builder-effective-config.yaml
│       │       ├── theFactory-MissionControl-Setup-0.1.0.exe
│       │       └── theFactory-MissionControl-Setup-0.1.0.exe.blockmap
│       ├── e2e
│       │   ├── electron.spec.ts
│       │   ├── mission-build-new-complete.spec.ts
│       │   ├── mission-control-extended.spec.ts
│       │   ├── mission-control.spec.ts
│       │   ├── mission-cost-panel.spec.ts
│       │   ├── mission-reduce-deps.spec.ts
│       │   ├── mission-runtime-qc.spec.ts
│       │   └── test-helpers.ts
│       ├── electron
│       │   ├── diagnostics.ts
│       │   ├── main.ts
│       │   ├── preload.ts
│       │   ├── tray.ts
│       │   ├── tsconfig.json
│       │   └── updater.ts
│       ├── out
│       │   ├── __next.!KHNoZWxsKQ
│       │   │   └── __PAGE__.txt
│       │   ├── _next
│       │   │   ├── g2kRjtmg-aoWxFH5hrvUD
│       │   │   └── static
│       │   │       ├── chunks
│       │   │       │   ├── 05-c3ty_6dwfk.js
│       │   │       │   ├── 0cz1d0mv5g_q7.js
│       │   │       │   ├── 0qbc6eyes-ise.js
│       │   │       │   ├── 0splwci-z1urc.js
│       │   │       │   ├── 10cphzk12fks2.js
│       │   │       │   ├── 14mrh2-p_w84d.js
│       │   │       │   ├── 15qlryzbz13ew.js
│       │   │       │   ├── 16fpupwn61xij.js
│       │   │       │   ├── 19kpq7ev5oau3.css
│       │   │       │   ├── 1f5ercwt8w1y9.js
│       │   │       │   ├── 1rffn4-simh3h.js
│       │   │       │   ├── 1y_tq7jnlme5b.js
│       │   │       │   ├── 1zem98b9fc-pr.js
│       │   │       │   ├── 2-uk_f8gm25he.js
│       │   │       │   ├── 217c_476a1w06.js
│       │   │       │   ├── 22fbj8s58tmuw.js
│       │   │       │   ├── 27jktro2p5rq9.js
│       │   │       │   ├── 2gpq5dw3yif0j.js
│       │   │       │   ├── 2m7ngg3c8d5om.js
│       │   │       │   ├── 2n4iagiubmupb.js
│       │   │       │   ├── 2nykiepra7i1k.js
│       │   │       │   ├── 2ratf3801gnb-.js
│       │   │       │   ├── 2v5-9jlzk6cie.js
│       │   │       │   ├── 2z0_179zc336-.js
│       │   │       │   ├── 31gu187rittw8.js
│       │   │       │   ├── 35tvl9xodt0d4.js
│       │   │       │   ├── 36fjmnl9oavws.js
│       │   │       │   ├── 3ayvzvy64p-qg.js
│       │   │       │   ├── 3pbgfj9wh_yqk.js
│       │   │       │   ├── 3yiddnbtmgj46.js
│       │   │       │   ├── 40id8vn9gkhiz.js
│       │   │       │   ├── 40redzimf9xuy.js
│       │   │       │   └── turbopack-0ygosvi-zuufe.js
│       │   │       ├── g2kRjtmg-aoWxFH5hrvUD
│       │   │       │   ├── _buildManifest.js
│       │   │       │   ├── _clientMiddlewareManifest.js
│       │   │       │   └── _ssgManifest.js
│       │   │       └── media
│       │   │           ├── 04c5164763c40239-s.1kd-r_s9smv5m.woff2
│       │   │           ├── 051742360c26797e-s.1bkzbscqrt8rl.woff2
│       │   │           ├── 1bffadaabf893a1e-s.3-6t-g6q0vh0a.woff2
│       │   │           ├── 26f284dcc38c84c0-s.3hlisc-pwq13z.woff2
│       │   │           ├── 2bbe8d2671613f1f-s.0k62hbripvv8p.woff2
│       │   │           ├── 2c55a0e60120577a-s.0-dom-5bn10r2.woff2
│       │   │           ├── 5476f68d60460930-s.2uwcyprjm3xu3.woff2
│       │   │           ├── 6a5386fd6038edbe-s.3_z45zcoc-xoz.woff2
│       │   │           ├── 7e7f32a39836f228-s.0-oo9_1x_xmvg.woff2
│       │   │           ├── 83afe278b6a6bb3c-s.2bn3s6zvc0dyp.woff2
│       │   │           ├── 9c72aa0f40e4eef8-s.1y4-pdgsjb-pw.woff2
│       │   │           ├── ad66f9afd8947f86-s.3lvt2whj97whp.woff2
│       │   │           └── fa39153a3fc630ba-s.36fqqi66-3tjb.woff2
│       │   ├── _not-found
│       │   │   ├── __next._not-found
│       │   │   │   └── __PAGE__.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   ├── __next._not-found.txt
│       │   │   └── __next._tree.txt
│       │   ├── agents
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── agents
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── agents.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── alerts
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── alerts
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── alerts.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── audit
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── audit
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── audit.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── builder
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── builder
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── builder.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── chat
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── chat
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── chat.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── dashboard
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── dashboard
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── dashboard.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── databases
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── databases
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── databases.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── logicnodes
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── logicnodes
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── logicnodes.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── missions
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── missions
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── missions.txt
│       │   │   ├── detail
│       │   │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   │   ├── missions
│       │   │   │   │   │   ├── detail
│       │   │   │   │   │   │   └── __PAGE__.txt
│       │   │   │   │   │   └── detail.txt
│       │   │   │   │   └── missions.txt
│       │   │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   │   ├── __next._full.txt
│       │   │   │   ├── __next._head.txt
│       │   │   │   ├── __next._index.txt
│       │   │   │   └── __next._tree.txt
│       │   │   ├── history
│       │   │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   │   ├── missions
│       │   │   │   │   │   ├── history
│       │   │   │   │   │   │   └── __PAGE__.txt
│       │   │   │   │   │   └── history.txt
│       │   │   │   │   └── missions.txt
│       │   │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   │   ├── __next._full.txt
│       │   │   │   ├── __next._head.txt
│       │   │   │   ├── __next._index.txt
│       │   │   │   └── __next._tree.txt
│       │   │   ├── output
│       │   │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   │   ├── missions
│       │   │   │   │   │   ├── output
│       │   │   │   │   │   │   └── __PAGE__.txt
│       │   │   │   │   │   └── output.txt
│       │   │   │   │   └── missions.txt
│       │   │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   │   ├── __next._full.txt
│       │   │   │   ├── __next._head.txt
│       │   │   │   ├── __next._index.txt
│       │   │   │   └── __next._tree.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   ├── __next._tree.txt
│       │   │   ├── detail.html
│       │   │   ├── detail.txt
│       │   │   ├── history.html
│       │   │   ├── history.txt
│       │   │   ├── output.html
│       │   │   └── output.txt
│       │   ├── performance
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── performance
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── performance.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── projects
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── projects
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── projects.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── protocol-bus
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── protocol-bus
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── protocol-bus.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── repo
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── repo
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── repo.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── settings
│       │   │   ├── __next.!KHNoZWxsKQ
│       │   │   │   ├── settings
│       │   │   │   │   └── __PAGE__.txt
│       │   │   │   └── settings.txt
│       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   └── __next._tree.txt
│       │   ├── unlock
│       │   │   ├── __next.unlock
│       │   │   │   └── __PAGE__.txt
│       │   │   ├── __next._full.txt
│       │   │   ├── __next._head.txt
│       │   │   ├── __next._index.txt
│       │   │   ├── __next._tree.txt
│       │   │   └── __next.unlock.txt
│       │   ├── .gitkeep
│       │   ├── 404.html
│       │   ├── __next.!KHNoZWxsKQ.txt
│       │   ├── __next._full.txt
│       │   ├── __next._head.txt
│       │   ├── __next._index.txt
│       │   ├── __next._tree.txt
│       │   ├── _not-found.html
│       │   ├── _not-found.txt
│       │   ├── agents.html
│       │   ├── agents.txt
│       │   ├── alerts.html
│       │   ├── alerts.txt
│       │   ├── audit.html
│       │   ├── audit.txt
│       │   ├── builder.html
│       │   ├── builder.txt
│       │   ├── chat.html
│       │   ├── chat.txt
│       │   ├── dashboard.html
│       │   ├── dashboard.txt
│       │   ├── databases.html
│       │   ├── databases.txt
│       │   ├── index.html
│       │   ├── index.txt
│       │   ├── logicnodes.html
│       │   ├── logicnodes.txt
│       │   ├── missions.html
│       │   ├── missions.txt
│       │   ├── performance.html
│       │   ├── performance.txt
│       │   ├── projects.html
│       │   ├── projects.txt
│       │   ├── protocol-bus.html
│       │   ├── protocol-bus.txt
│       │   ├── repo.html
│       │   ├── repo.txt
│       │   ├── settings.html
│       │   ├── settings.txt
│       │   ├── tray-icon-win.ico
│       │   ├── unlock.html
│       │   └── unlock.txt
│       ├── output_extracted
│       │   ├── dist
│       │   │   └── electron
│       │   │       ├── app
│       │   │       │   └── lib
│       │   │       │       ├── electron-bridge.js
│       │   │       │       └── electron-bridge.js.map
│       │   │       └── electron
│       │   │           ├── main.js
│       │   │           ├── main.js.map
│       │   │           ├── preload.js
│       │   │           ├── preload.js.map
│       │   │           ├── tray.js
│       │   │           ├── tray.js.map
│       │   │           ├── updater.js
│       │   │           └── updater.js.map
│       │   └── out
│       │       ├── __next.!KHNoZWxsKQ
│       │       │   └── __PAGE__.txt
│       │       ├── _next
│       │       │   └── static
│       │       │       ├── chunks
│       │       │       │   ├── 0-0dcjf.asasg.js
│       │       │       │   ├── 01xlw8hd842-c.js
│       │       │       │   ├── 03~yq9q893hmn.js
│       │       │       │   ├── 060m..j8a5_xm.js
│       │       │       │   ├── 07lhk_q6pmm3r.js
│       │       │       │   ├── 09ixe49bq8527.js
│       │       │       │   ├── 0_hslrq_.~gb-.js
│       │       │       │   ├── 0ae9~zc5aq4w2.js
│       │       │       │   ├── 0b7e1hehvkymv.js
│       │       │       │   ├── 0c7pjnrvs.b6c.js
│       │       │       │   ├── 0d3shmwh5_nmn.js
│       │       │       │   ├── 0dha171epf-bp.js
│       │       │       │   ├── 0i20ag82pu0ft.js
│       │       │       │   ├── 0j20~icd-k3qd.js
│       │       │       │   ├── 0kj-ykgv75544.js
│       │       │       │   ├── 0m2_skg2weqws.js
│       │       │       │   ├── 0pe83294yscdg.js
│       │       │       │   ├── 0pkc6eu5atbxg.js
│       │       │       │   ├── 0pqt~8bl3ukh4.js
│       │       │       │   ├── 0pz1-xhhktvn_.js
│       │       │       │   ├── 0u7c526z~xy4u.js
│       │       │       │   ├── 0uincq-jpizfp.js
│       │       │       │   ├── 0v365bzc_wqzf.js
│       │       │       │   ├── 0xt4gbh-30r8v.css
│       │       │       │   ├── 11vgqffp-vbxp.js
│       │       │       │   ├── 125clp4hu337o.js
│       │       │       │   ├── 13vy55nu9nywm.js
│       │       │       │   ├── 14d11gevfk-v3.js
│       │       │       │   ├── 15pjn.n4_q6le.js
│       │       │       │   ├── 16w56q61ke-._.js
│       │       │       │   └── turbopack-0s~cihta.uwm9.js
│       │       │       ├── media
│       │       │       │   ├── 04c5164763c40239-s.0h-nw9_c8d~-_.woff2
│       │       │       │   ├── 051742360c26797e-s.0f97p8c3305p~.woff2
│       │       │       │   ├── 1bffadaabf893a1e-s.16ipb6fqu393i.woff2
│       │       │       │   ├── 26f284dcc38c84c0-s.10hk62x1-0d9n.woff2
│       │       │       │   ├── 2bbe8d2671613f1f-s.067x_6k0k23tk.woff2
│       │       │       │   ├── 2c55a0e60120577a-s.0bjc5tiuqdqro.woff2
│       │       │       │   ├── 5476f68d60460930-s.0wxq9webf.ew4.woff2
│       │       │       │   ├── 6a5386fd6038edbe-s.16fk0g~ypa53a.woff2
│       │       │       │   ├── 7e7f32a39836f228-s.0bmyfaahigzds.woff2
│       │       │       │   ├── 83afe278b6a6bb3c-s.0q-301v4kxxnr.woff2
│       │       │       │   ├── 9c72aa0f40e4eef8-s.0m6w47a4e5dy9.woff2
│       │       │       │   ├── ad66f9afd8947f86-s.11u06r12fd6v_.woff2
│       │       │       │   └── fa39153a3fc630ba-s.0-0ft90hthv3~.woff2
│       │       │       └── mKCKQBGTzAeqOJuOnTjEP
│       │       │           ├── _buildManifest.js
│       │       │           ├── _clientMiddlewareManifest.js
│       │       │           └── _ssgManifest.js
│       │       ├── _not-found
│       │       │   ├── __next._not-found
│       │       │   │   └── __PAGE__.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   ├── __next._not-found.txt
│       │       │   └── __next._tree.txt
│       │       ├── agents
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── agents
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── agents.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── alerts
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── alerts
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── alerts.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── audit
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── audit
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── audit.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── builder
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── builder
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── builder.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── chat
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── chat
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── chat.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── dashboard
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── dashboard
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── dashboard.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── databases
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── databases
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── databases.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── logicnodes
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── logicnodes
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── logicnodes.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── missions
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── missions
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── missions.txt
│       │       │   ├── detail
│       │       │   │   ├── __next.!KHNoZWxsKQ
│       │       │   │   │   ├── missions
│       │       │   │   │   │   ├── detail
│       │       │   │   │   │   │   └── __PAGE__.txt
│       │       │   │   │   │   └── detail.txt
│       │       │   │   │   └── missions.txt
│       │       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   │   ├── __next._full.txt
│       │       │   │   ├── __next._head.txt
│       │       │   │   ├── __next._index.txt
│       │       │   │   └── __next._tree.txt
│       │       │   ├── history
│       │       │   │   ├── __next.!KHNoZWxsKQ
│       │       │   │   │   ├── missions
│       │       │   │   │   │   ├── history
│       │       │   │   │   │   │   └── __PAGE__.txt
│       │       │   │   │   │   └── history.txt
│       │       │   │   │   └── missions.txt
│       │       │   │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   │   ├── __next._full.txt
│       │       │   │   ├── __next._head.txt
│       │       │   │   ├── __next._index.txt
│       │       │   │   └── __next._tree.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   ├── __next._tree.txt
│       │       │   ├── detail.html
│       │       │   ├── detail.txt
│       │       │   ├── history.html
│       │       │   └── history.txt
│       │       ├── performance
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── performance
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── performance.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── projects
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── projects
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── projects.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── repo
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── repo
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── repo.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── semantic-bus
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── semantic-bus
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── semantic-bus.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── settings
│       │       │   ├── __next.!KHNoZWxsKQ
│       │       │   │   ├── settings
│       │       │   │   │   └── __PAGE__.txt
│       │       │   │   └── settings.txt
│       │       │   ├── __next.!KHNoZWxsKQ.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   └── __next._tree.txt
│       │       ├── unlock
│       │       │   ├── __next.unlock
│       │       │   │   └── __PAGE__.txt
│       │       │   ├── __next._full.txt
│       │       │   ├── __next._head.txt
│       │       │   ├── __next._index.txt
│       │       │   ├── __next._tree.txt
│       │       │   └── __next.unlock.txt
│       │       ├── 404.html
│       │       ├── __next.!KHNoZWxsKQ.txt
│       │       ├── __next._full.txt
│       │       ├── __next._head.txt
│       │       ├── __next._index.txt
│       │       ├── __next._tree.txt
│       │       ├── _not-found.html
│       │       ├── _not-found.txt
│       │       ├── agents.html
│       │       ├── agents.txt
│       │       ├── alerts.html
│       │       ├── alerts.txt
│       │       ├── audit.html
│       │       ├── audit.txt
│       │       ├── builder.html
│       │       ├── builder.txt
│       │       ├── chat.html
│       │       ├── chat.txt
│       │       ├── dashboard.html
│       │       ├── dashboard.txt
│       │       ├── databases.html
│       │       ├── databases.txt
│       │       ├── index.html
│       │       ├── index.txt
│       │       ├── logicnodes.html
│       │       ├── logicnodes.txt
│       │       ├── missions.html
│       │       ├── missions.txt
│       │       ├── performance.html
│       │       ├── performance.txt
│       │       ├── projects.html
│       │       ├── projects.txt
│       │       ├── repo.html
│       │       ├── repo.txt
│       │       ├── semantic-bus.html
│       │       ├── semantic-bus.txt
│       │       ├── settings.html
│       │       ├── settings.txt
│       │       ├── tray-icon-win.ico
│       │       ├── unlock.html
│       │       └── unlock.txt
│       ├── public
│       │   ├── .gitkeep
│       │   └── tray-icon-win.ico
│       ├── scripts
│       │   ├── build-electron.mjs
│       │   ├── run-npm-exec-clean-env.mjs
│       │   └── sync-design-tokens.mjs
│       ├── .dockerignore
│       ├── .env.example
│       ├── .env.local
│       ├── .gitignore
│       ├── .npmrc
│       ├── Dockerfile
│       ├── lighthouserc.json
│       ├── next-env.d.ts
│       ├── next.config.mjs
│       ├── package-lock.json
│       ├── package.json
│       ├── playwright.config.ts
│       ├── playwright.electron.config.ts
│       ├── README.md
│       ├── tsconfig.json
│       ├── tsconfig.tsbuildinfo
│       └── vitest.config.ts
├── artifacts
│   └── refined-ir
│       └── index.json
├── assets
│   └── design-tokens
│       ├── tokens.css
│       └── tokens.json
├── backups
│   ├── ulr_20260519_232452.sql
│   ├── ulr_20260519_232452.sql.json
│   ├── ulr_20260519_232452.sql.sha256
│   ├── ulr_20260519_234143.sql
│   ├── ulr_20260519_234143.sql.json
│   ├── ulr_20260519_234143.sql.sha256
│   ├── ulr_20990101_04840cf2.sql.json
│   ├── ulr_20990101_04840cf2.sql.sha256
│   ├── ulr_20990101_0715babc.sql.json
│   ├── ulr_20990101_0715babc.sql.sha256
│   ├── ulr_20990101_08ca8b38.sql.json
│   ├── ulr_20990101_08ca8b38.sql.sha256
│   ├── ulr_20990101_098ec1ad.sql.json
│   ├── ulr_20990101_098ec1ad.sql.sha256
│   ├── ulr_20990101_0a0c873a.sql.json
│   ├── ulr_20990101_0a0c873a.sql.sha256
│   ├── ulr_20990101_0a472116.sql.json
│   ├── ulr_20990101_0a472116.sql.sha256
│   ├── ulr_20990101_0ab47b4f.sql.json
│   ├── ulr_20990101_0ab47b4f.sql.sha256
│   ├── ulr_20990101_0ade9ade.sql.json
│   ├── ulr_20990101_0ade9ade.sql.sha256
│   ├── ulr_20990101_0c6b7fdd.sql.json
│   ├── ulr_20990101_0c6b7fdd.sql.sha256
│   ├── ulr_20990101_0deef625.sql.json
│   ├── ulr_20990101_0deef625.sql.sha256
│   ├── ulr_20990101_119b2d09.sql.json
│   ├── ulr_20990101_119b2d09.sql.sha256
│   ├── ulr_20990101_11b27626.sql.json
│   ├── ulr_20990101_11b27626.sql.sha256
│   ├── ulr_20990101_12395854.sql.json
│   ├── ulr_20990101_12395854.sql.sha256
│   ├── ulr_20990101_12e80165.sql.json
│   ├── ulr_20990101_12e80165.sql.sha256
│   ├── ulr_20990101_1361e06a.sql.json
│   ├── ulr_20990101_1361e06a.sql.sha256
│   ├── ulr_20990101_13d6036e.sql.json
│   ├── ulr_20990101_13d6036e.sql.sha256
│   ├── ulr_20990101_14036ac1.sql.json
│   ├── ulr_20990101_14036ac1.sql.sha256
│   ├── ulr_20990101_16972898.sql.json
│   ├── ulr_20990101_16972898.sql.sha256
│   ├── ulr_20990101_17d06379.sql.json
│   ├── ulr_20990101_17d06379.sql.sha256
│   ├── ulr_20990101_18b6850a.sql.json
│   ├── ulr_20990101_18b6850a.sql.sha256
│   ├── ulr_20990101_1c145e96.sql.json
│   ├── ulr_20990101_1c145e96.sql.sha256
│   ├── ulr_20990101_1c2f148c.sql.json
│   ├── ulr_20990101_1c2f148c.sql.sha256
│   ├── ulr_20990101_1dcfafa2.sql.json
│   ├── ulr_20990101_1dcfafa2.sql.sha256
│   ├── ulr_20990101_1e70c720.sql.json
│   ├── ulr_20990101_1e70c720.sql.sha256
│   ├── ulr_20990101_1f176fcf.sql.json
│   ├── ulr_20990101_1f176fcf.sql.sha256
│   ├── ulr_20990101_1f2c6c38.sql.json
│   ├── ulr_20990101_1f2c6c38.sql.sha256
│   ├── ulr_20990101_1fad8c8a.sql.json
│   ├── ulr_20990101_1fad8c8a.sql.sha256
│   ├── ulr_20990101_20cac25b.sql.json
│   ├── ulr_20990101_20cac25b.sql.sha256
│   ├── ulr_20990101_25282cec.sql.json
│   ├── ulr_20990101_25282cec.sql.sha256
│   ├── ulr_20990101_26b62a1d.sql.json
│   ├── ulr_20990101_26b62a1d.sql.sha256
│   ├── ulr_20990101_289ca10b.sql.json
│   ├── ulr_20990101_289ca10b.sql.sha256
│   ├── ulr_20990101_29d5419b.sql.json
│   ├── ulr_20990101_29d5419b.sql.sha256
│   ├── ulr_20990101_29e090fa.sql.json
│   ├── ulr_20990101_29e090fa.sql.sha256
│   ├── ulr_20990101_2bd307f5.sql.json
│   ├── ulr_20990101_2bd307f5.sql.sha256
│   ├── ulr_20990101_2e994827.sql.json
│   ├── ulr_20990101_2e994827.sql.sha256
│   ├── ulr_20990101_3104831d.sql.json
│   ├── ulr_20990101_3104831d.sql.sha256
│   ├── ulr_20990101_32f86ac0.sql.json
│   ├── ulr_20990101_32f86ac0.sql.sha256
│   ├── ulr_20990101_335ac6a5.sql.json
│   ├── ulr_20990101_335ac6a5.sql.sha256
│   ├── ulr_20990101_33a3c3e0.sql.json
│   ├── ulr_20990101_33a3c3e0.sql.sha256
│   ├── ulr_20990101_3700b99c.sql.json
│   ├── ulr_20990101_3700b99c.sql.sha256
│   ├── ulr_20990101_38c481b7.sql.json
│   ├── ulr_20990101_38c481b7.sql.sha256
│   ├── ulr_20990101_3de36a30.sql.json
│   ├── ulr_20990101_3de36a30.sql.sha256
│   ├── ulr_20990101_3ded7cca.sql.json
│   ├── ulr_20990101_3ded7cca.sql.sha256
│   ├── ulr_20990101_3ee9759e.sql.json
│   ├── ulr_20990101_3ee9759e.sql.sha256
│   ├── ulr_20990101_427105f8.sql.json
│   ├── ulr_20990101_427105f8.sql.sha256
│   ├── ulr_20990101_4399ac05.sql.json
│   ├── ulr_20990101_4399ac05.sql.sha256
│   ├── ulr_20990101_440afe99.sql.json
│   ├── ulr_20990101_440afe99.sql.sha256
│   ├── ulr_20990101_475a55f6.sql.json
│   ├── ulr_20990101_475a55f6.sql.sha256
│   ├── ulr_20990101_49a187c6.sql.json
│   ├── ulr_20990101_49a187c6.sql.sha256
│   ├── ulr_20990101_49ed5a21.sql.json
│   ├── ulr_20990101_49ed5a21.sql.sha256
│   ├── ulr_20990101_4a5f2111.sql.json
│   ├── ulr_20990101_4a5f2111.sql.sha256
│   ├── ulr_20990101_4d65d55e.sql.json
│   ├── ulr_20990101_4d65d55e.sql.sha256
│   ├── ulr_20990101_4da57574.sql.json
│   ├── ulr_20990101_4da57574.sql.sha256
│   ├── ulr_20990101_4eaa0b4d.sql.json
│   ├── ulr_20990101_4eaa0b4d.sql.sha256
│   ├── ulr_20990101_519b0d62.sql.json
│   ├── ulr_20990101_519b0d62.sql.sha256
│   ├── ulr_20990101_548e5229.sql.json
│   ├── ulr_20990101_548e5229.sql.sha256
│   ├── ulr_20990101_54e3fd87.sql.json
│   ├── ulr_20990101_54e3fd87.sql.sha256
│   ├── ulr_20990101_563667b8.sql.json
│   ├── ulr_20990101_563667b8.sql.sha256
│   ├── ulr_20990101_57201dc4.sql.json
│   ├── ulr_20990101_57201dc4.sql.sha256
│   ├── ulr_20990101_5aa88654.sql.json
│   ├── ulr_20990101_5aa88654.sql.sha256
│   ├── ulr_20990101_5cddc085.sql.json
│   ├── ulr_20990101_5cddc085.sql.sha256
│   ├── ulr_20990101_5f3fe162.sql.json
│   ├── ulr_20990101_5f3fe162.sql.sha256
│   ├── ulr_20990101_66602978.sql.json
│   ├── ulr_20990101_66602978.sql.sha256
│   ├── ulr_20990101_675d10c9.sql.json
│   ├── ulr_20990101_675d10c9.sql.sha256
│   ├── ulr_20990101_67fc866d.sql.json
│   ├── ulr_20990101_67fc866d.sql.sha256
│   ├── ulr_20990101_6a5e6f36.sql.json
│   ├── ulr_20990101_6a5e6f36.sql.sha256
│   ├── ulr_20990101_6e8e2ca2.sql.json
│   ├── ulr_20990101_6e8e2ca2.sql.sha256
│   ├── ulr_20990101_706d68a5.sql.json
│   ├── ulr_20990101_706d68a5.sql.sha256
│   ├── ulr_20990101_73bd1b84.sql.json
│   ├── ulr_20990101_73bd1b84.sql.sha256
│   ├── ulr_20990101_73e7447a.sql.json
│   ├── ulr_20990101_73e7447a.sql.sha256
│   ├── ulr_20990101_7708421e.sql.json
│   ├── ulr_20990101_7708421e.sql.sha256
│   ├── ulr_20990101_775f213b.sql.json
│   ├── ulr_20990101_775f213b.sql.sha256
│   ├── ulr_20990101_77dd87f1.sql.json
│   ├── ulr_20990101_77dd87f1.sql.sha256
│   ├── ulr_20990101_787aba45.sql.json
│   ├── ulr_20990101_787aba45.sql.sha256
│   ├── ulr_20990101_7886d733.sql.json
│   ├── ulr_20990101_7886d733.sql.sha256
│   ├── ulr_20990101_7a242ee5.sql.json
│   ├── ulr_20990101_7a242ee5.sql.sha256
│   ├── ulr_20990101_7a4460b8.sql.json
│   ├── ulr_20990101_7a4460b8.sql.sha256
│   ├── ulr_20990101_7a9d898f.sql.json
│   ├── ulr_20990101_7a9d898f.sql.sha256
│   ├── ulr_20990101_7d954f96.sql.json
│   ├── ulr_20990101_7d954f96.sql.sha256
│   ├── ulr_20990101_806ec8da.sql.json
│   ├── ulr_20990101_806ec8da.sql.sha256
│   ├── ulr_20990101_80d75ab2.sql.json
│   ├── ulr_20990101_80d75ab2.sql.sha256
│   ├── ulr_20990101_813cdc74.sql.json
│   ├── ulr_20990101_813cdc74.sql.sha256
│   ├── ulr_20990101_81ba4388.sql.json
│   ├── ulr_20990101_81ba4388.sql.sha256
│   ├── ulr_20990101_8698601c.sql.json
│   ├── ulr_20990101_8698601c.sql.sha256
│   ├── ulr_20990101_884a2b17.sql.json
│   ├── ulr_20990101_884a2b17.sql.sha256
│   ├── ulr_20990101_8889e578.sql.json
│   ├── ulr_20990101_8889e578.sql.sha256
│   ├── ulr_20990101_8ab25ad0.sql.json
│   ├── ulr_20990101_8ab25ad0.sql.sha256
│   ├── ulr_20990101_8ba35aa7.sql.json
│   ├── ulr_20990101_8ba35aa7.sql.sha256
│   ├── ulr_20990101_8bc19ebf.sql.json
│   ├── ulr_20990101_8bc19ebf.sql.sha256
│   ├── ulr_20990101_8d3cc834.sql.json
│   ├── ulr_20990101_8d3cc834.sql.sha256
│   ├── ulr_20990101_8f5b63f8.sql.json
│   ├── ulr_20990101_8f5b63f8.sql.sha256
│   ├── ulr_20990101_8fbc430d.sql.json
│   ├── ulr_20990101_8fbc430d.sql.sha256
│   ├── ulr_20990101_903c7b41.sql.json
│   ├── ulr_20990101_903c7b41.sql.sha256
│   ├── ulr_20990101_90bcd05f.sql.json
│   ├── ulr_20990101_90bcd05f.sql.sha256
│   ├── ulr_20990101_9111bbdd.sql.json
│   ├── ulr_20990101_9111bbdd.sql.sha256
│   ├── ulr_20990101_94d320a3.sql.json
│   ├── ulr_20990101_94d320a3.sql.sha256
│   ├── ulr_20990101_958091c9.sql.json
│   ├── ulr_20990101_958091c9.sql.sha256
│   ├── ulr_20990101_9814bb4e.sql.json
│   ├── ulr_20990101_9814bb4e.sql.sha256
│   ├── ulr_20990101_9904529b.sql.json
│   ├── ulr_20990101_9904529b.sql.sha256
│   ├── ulr_20990101_9bf448a0.sql.json
│   ├── ulr_20990101_9bf448a0.sql.sha256
│   ├── ulr_20990101_9d7d3eea.sql.json
│   ├── ulr_20990101_9d7d3eea.sql.sha256
│   ├── ulr_20990101_9f1a901a.sql.json
│   ├── ulr_20990101_9f1a901a.sql.sha256
│   ├── ulr_20990101_a2a4f2c0.sql.json
│   ├── ulr_20990101_a2a4f2c0.sql.sha256
│   ├── ulr_20990101_a42be0c2.sql.json
│   ├── ulr_20990101_a42be0c2.sql.sha256
│   ├── ulr_20990101_a43ea632.sql.json
│   ├── ulr_20990101_a43ea632.sql.sha256
│   ├── ulr_20990101_a5deb517.sql.json
│   ├── ulr_20990101_a5deb517.sql.sha256
│   ├── ulr_20990101_a7d7c2a9.sql.json
│   ├── ulr_20990101_a7d7c2a9.sql.sha256
│   ├── ulr_20990101_aa79b724.sql.json
│   ├── ulr_20990101_aa79b724.sql.sha256
│   ├── ulr_20990101_adbf1464.sql.json
│   ├── ulr_20990101_adbf1464.sql.sha256
│   ├── ulr_20990101_adc50a9b.sql.json
│   ├── ulr_20990101_adc50a9b.sql.sha256
│   ├── ulr_20990101_b19c6795.sql.json
│   ├── ulr_20990101_b19c6795.sql.sha256
│   ├── ulr_20990101_b4b8521b.sql.json
│   ├── ulr_20990101_b4b8521b.sql.sha256
│   ├── ulr_20990101_b9113d6c.sql.json
│   ├── ulr_20990101_b9113d6c.sql.sha256
│   ├── ulr_20990101_b9406a84.sql.json
│   ├── ulr_20990101_b9406a84.sql.sha256
│   ├── ulr_20990101_ba1522d2.sql.json
│   ├── ulr_20990101_ba1522d2.sql.sha256
│   ├── ulr_20990101_ba28d066.sql.json
│   ├── ulr_20990101_ba28d066.sql.sha256
│   ├── ulr_20990101_bb6bc280.sql.json
│   ├── ulr_20990101_bb6bc280.sql.sha256
│   ├── ulr_20990101_bb9834ae.sql.json
│   ├── ulr_20990101_bb9834ae.sql.sha256
│   ├── ulr_20990101_bca3be34.sql.json
│   ├── ulr_20990101_bca3be34.sql.sha256
│   ├── ulr_20990101_bd1bb011.sql.json
│   ├── ulr_20990101_bd1bb011.sql.sha256
│   ├── ulr_20990101_bf3a08c1.sql.json
│   ├── ulr_20990101_bf3a08c1.sql.sha256
│   ├── ulr_20990101_bfc3f316.sql.json
│   ├── ulr_20990101_bfc3f316.sql.sha256
│   ├── ulr_20990101_c0a797ed.sql.json
│   ├── ulr_20990101_c0a797ed.sql.sha256
│   ├── ulr_20990101_c452aa1c.sql.json
│   ├── ulr_20990101_c452aa1c.sql.sha256
│   ├── ulr_20990101_c5f71d96.sql.json
│   ├── ulr_20990101_c5f71d96.sql.sha256
│   ├── ulr_20990101_c69fe24c.sql.json
│   ├── ulr_20990101_c69fe24c.sql.sha256
│   ├── ulr_20990101_c7cac49f.sql.json
│   ├── ulr_20990101_c7cac49f.sql.sha256
│   ├── ulr_20990101_c7eab9a4.sql.json
│   ├── ulr_20990101_c7eab9a4.sql.sha256
│   ├── ulr_20990101_c92508a2.sql.json
│   ├── ulr_20990101_c92508a2.sql.sha256
│   ├── ulr_20990101_c961935e.sql.json
│   ├── ulr_20990101_c961935e.sql.sha256
│   ├── ulr_20990101_cafe756b.sql.json
│   ├── ulr_20990101_cafe756b.sql.sha256
│   ├── ulr_20990101_cb8b27d2.sql.json
│   ├── ulr_20990101_cb8b27d2.sql.sha256
│   ├── ulr_20990101_cd810be1.sql.json
│   ├── ulr_20990101_cd810be1.sql.sha256
│   ├── ulr_20990101_cf1aa9f1.sql.json
│   ├── ulr_20990101_cf1aa9f1.sql.sha256
│   ├── ulr_20990101_cfa51233.sql.json
│   ├── ulr_20990101_cfa51233.sql.sha256
│   ├── ulr_20990101_d0c71579.sql.json
│   ├── ulr_20990101_d0c71579.sql.sha256
│   ├── ulr_20990101_d1fcb6dc.sql.json
│   ├── ulr_20990101_d1fcb6dc.sql.sha256
│   ├── ulr_20990101_d349f4f6.sql.json
│   ├── ulr_20990101_d349f4f6.sql.sha256
│   ├── ulr_20990101_d4fe2718.sql.json
│   ├── ulr_20990101_d4fe2718.sql.sha256
│   ├── ulr_20990101_d72af514.sql.json
│   ├── ulr_20990101_d72af514.sql.sha256
│   ├── ulr_20990101_d7899ae8.sql.json
│   ├── ulr_20990101_d7899ae8.sql.sha256
│   ├── ulr_20990101_d847cf61.sql.json
│   ├── ulr_20990101_d847cf61.sql.sha256
│   ├── ulr_20990101_d88f1b94.sql.json
│   ├── ulr_20990101_d88f1b94.sql.sha256
│   ├── ulr_20990101_d8e04cb0.sql.json
│   ├── ulr_20990101_d8e04cb0.sql.sha256
│   ├── ulr_20990101_d8faaae6.sql.json
│   ├── ulr_20990101_d8faaae6.sql.sha256
│   ├── ulr_20990101_d9b24d27.sql.json
│   ├── ulr_20990101_d9b24d27.sql.sha256
│   ├── ulr_20990101_da60b35c.sql.json
│   ├── ulr_20990101_da60b35c.sql.sha256
│   ├── ulr_20990101_dbaa3154.sql.json
│   ├── ulr_20990101_dbaa3154.sql.sha256
│   ├── ulr_20990101_dbab5e5d.sql.json
│   ├── ulr_20990101_dbab5e5d.sql.sha256
│   ├── ulr_20990101_dd13da33.sql.json
│   ├── ulr_20990101_dd13da33.sql.sha256
│   ├── ulr_20990101_dea062eb.sql.json
│   ├── ulr_20990101_dea062eb.sql.sha256
│   ├── ulr_20990101_df3bb365.sql.json
│   ├── ulr_20990101_df3bb365.sql.sha256
│   ├── ulr_20990101_e29a4494.sql.json
│   ├── ulr_20990101_e29a4494.sql.sha256
│   ├── ulr_20990101_e45aa314.sql.json
│   ├── ulr_20990101_e45aa314.sql.sha256
│   ├── ulr_20990101_e518e53a.sql.json
│   ├── ulr_20990101_e518e53a.sql.sha256
│   ├── ulr_20990101_e6874029.sql.json
│   ├── ulr_20990101_e6874029.sql.sha256
│   ├── ulr_20990101_e8e851ec.sql.json
│   ├── ulr_20990101_e8e851ec.sql.sha256
│   ├── ulr_20990101_ea0a9e57.sql.json
│   ├── ulr_20990101_ea0a9e57.sql.sha256
│   ├── ulr_20990101_eb0d6b79.sql.json
│   ├── ulr_20990101_eb0d6b79.sql.sha256
│   ├── ulr_20990101_eb830b1e.sql.json
│   ├── ulr_20990101_eb830b1e.sql.sha256
│   ├── ulr_20990101_eb833f44.sql.json
│   ├── ulr_20990101_eb833f44.sql.sha256
│   ├── ulr_20990101_f24a9e09.sql.json
│   ├── ulr_20990101_f24a9e09.sql.sha256
│   ├── ulr_20990101_f3d1d811.sql.json
│   ├── ulr_20990101_f3d1d811.sql.sha256
│   ├── ulr_20990101_f86d6d09.sql.json
│   ├── ulr_20990101_f86d6d09.sql.sha256
│   ├── ulr_20990101_f980fb7e.sql.json
│   ├── ulr_20990101_f980fb7e.sql.sha256
│   ├── ulr_20990101_fa0a89c6.sql.json
│   ├── ulr_20990101_fa0a89c6.sql.sha256
│   ├── ulr_20990101_fa7ef26b.sql.json
│   ├── ulr_20990101_fa7ef26b.sql.sha256
│   ├── ulr_20990101_fd6252e9.sql.json
│   ├── ulr_20990101_fd6252e9.sql.sha256
│   ├── ulr_phase17_20260519.sql
│   ├── ulr_phase17_20260519.sql.json
│   └── ulr_phase17_20260519.sql.sha256
├── config
│   └── agent_api_keys.yaml
├── deploy
│   ├── .local
│   │   ├── postgres-certs
│   │   │   ├── ca.crt
│   │   │   ├── server.crt
│   │   │   └── server.key
│   │   └── redis-certs
│   │       ├── ca.crt
│   │       ├── redis.crt
│   │       └── redis.key
│   ├── monitoring
│   │   ├── alertmanager
│   │   │   └── alertmanager.yml
│   │   ├── grafana
│   │   │   └── provisioning
│   │   │       ├── dashboards
│   │   │       │   ├── json
│   │   │       │   │   ├── mission-lifecycle.json
│   │   │       │   │   └── thefactory-overview.json
│   │   │       │   └── dashboards.yml
│   │   │       └── datasources
│   │   │           ├── datasources.yml
│   │   │           └── jaeger.yaml
│   │   ├── loki
│   │   │   └── loki-config.yml
│   │   ├── prometheus
│   │   │   ├── rules
│   │   │   │   └── thefactory-alerts.yml
│   │   │   └── prometheus.yml
│   │   └── promtail
│   │       └── promtail-config.yml
│   ├── postgres
│   │   ├── certs
│   │   ├── entrypoint.prod.sh
│   │   ├── entrypoint.sh
│   │   ├── pg_hba.conf
│   │   └── postgresql.conf
│   ├── redis
│   │   ├── certs
│   │   ├── entrypoint.sh
│   │   ├── redis.conf
│   │   └── redis.prod.conf
│   ├── docker-compose.dev.yaml
│   ├── docker-compose.full-dedicated-agents.yaml
│   ├── docker-compose.monitoring.yaml
│   ├── docker-compose.prod.yaml
│   ├── docker-compose.staging.yaml
│   ├── docker-compose.yaml
│   └── promotion-policy.json
├── docs
│   ├── api
│   │   └── README.md
│   ├── archive
│   │   ├── 2026-03-29
│   │   │   ├── historical
│   │   │   │   ├── COMPLETION_TODO_2026-03-02.md
│   │   │   │   ├── COMPLETION_TODO_2026-03-13.md
│   │   │   │   ├── COMPREHENSIVE_APPLICATION_AUDIT_2026-03-02.md
│   │   │   │   ├── DELIVERY_PHASE_LOG_2026-03-02.md
│   │   │   │   ├── GAP_ANALYSIS.md
│   │   │   │   ├── HGR_BACKEND_CHECKLIST_AUDIT_2026-03-02.md
│   │   │   │   ├── LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md
│   │   │   │   ├── MISSION_FLOW_V1_1_CANONICAL_2026-03-07.md
│   │   │   │   ├── MISSION_FLOW_V2_COMPARISON_2026-03-08.md
│   │   │   │   ├── PRODUCTION_PHASE_PLAN.md
│   │   │   │   ├── PRODUCTION_REVIEW_AUDIT.md
│   │   │   │   ├── UI_UX_PHASE_EXECUTION_LOG_2026-03-01.md
│   │   │   │   ├── UI_UX_WIREFRAME_FRONTEND_MASTER_PLAN.md
│   │   │   │   ├── UPDATED_PHASE_PLAN_2026-03-03.md
│   │   │   │   ├── UPDATED_TODO_FROM_WORD_AUDIT_2026-03-03.md
│   │   │   │   ├── UX_USER_STORY_JOURNEY_INTERACTION_REVIEW_2026-03-01.md
│   │   │   │   ├── WORD_DOC_APP_REMAINING_AUDIT_2026-03-08.md
│   │   │   │   ├── WORD_DOC_APP_REMAINING_TODO_2026-03-08.md
│   │   │   │   └── WORD_DOC_AUDIT_2026-03-03.md
│   │   │   ├── legacy-workspace
│   │   │   │   ├── docs-legacy-documentation
│   │   │   │   │   ├── agent_profile_SPECIALIST_AI_001.docx
│   │   │   │   │   ├── agent_profiles_batch5.docx
│   │   │   │   │   ├── agent_profiles_batch6.docx
│   │   │   │   │   ├── agent_profiles_batch7.docx
│   │   │   │   │   └── agent_profiles_batch8_FINAL.docx
│   │   │   │   ├── root-legacy-documentation
│   │   │   │   │   ├── unified-logic-refinery-blueprint-single
│   │   │   │   │   │   └── unified-logic-refinery-starter
│   │   │   │   │   │       ├── deploy
│   │   │   │   │   │       │   └── docker-compose.yaml
│   │   │   │   │   │       ├── examples
│   │   │   │   │   │       │   ├── logicnode.example.json
│   │   │   │   │   │       │   ├── rir.fn.example.json
│   │   │   │   │   │       │   └── rir.module.example.json
│   │   │   │   │   │       ├── ledger
│   │   │   │   │   │       │   └── schema.sql
│   │   │   │   │   │       ├── protocol
│   │   │   │   │   │       │   └── topics.yaml
│   │   │   │   │   │       ├── schemas
│   │   │   │   │   │       │   ├── event.envelope.schema.json
│   │   │   │   │   │       │   ├── logicnode.schema.json
│   │   │   │   │   │       │   ├── rir.fn.schema.json
│   │   │   │   │   │       │   └── rir.module.schema.json
│   │   │   │   │   │       ├── scripts
│   │   │   │   │   │       │   └── validate_schemas.py
│   │   │   │   │   │       ├── services
│   │   │   │   │   │       │   ├── dashboard
│   │   │   │   │   │       │   │   ├── dashboard
│   │   │   │   │   │       │   │   │   ├── __init__.py
│   │   │   │   │   │       │   │   │   └── main.py
│   │   │   │   │   │       │   │   ├── Dockerfile
│   │   │   │   │   │       │   │   └── requirements.txt
│   │   │   │   │   │       │   └── orchestrator
│   │   │   │   │   │       │       ├── orchestrator
│   │   │   │   │   │       │       │   ├── __init__.py
│   │   │   │   │   │       │       │   └── main.py
│   │   │   │   │   │       │       ├── Dockerfile
│   │   │   │   │   │       │       └── requirements.txt
│   │   │   │   │   │       ├── BLUEPRINT.md
│   │   │   │   │   │       ├── BLUEPRINT_SPEC.md
│   │   │   │   │   │       ├── Makefile
│   │   │   │   │   │       └── README.md
│   │   │   │   │   ├── unified-logic-refinery-starter
│   │   │   │   │   │   └── unified-logic-refinery-starter
│   │   │   │   │   │       ├── deploy
│   │   │   │   │   │       │   └── docker-compose.yaml
│   │   │   │   │   │       ├── examples
│   │   │   │   │   │       │   ├── logicnode.example.json
│   │   │   │   │   │       │   ├── rir.fn.example.json
│   │   │   │   │   │       │   └── rir.module.example.json
│   │   │   │   │   │       ├── ledger
│   │   │   │   │   │       │   └── schema.sql
│   │   │   │   │   │       ├── protocol
│   │   │   │   │   │       │   └── topics.yaml
│   │   │   │   │   │       ├── schemas
│   │   │   │   │   │       │   ├── event.envelope.schema.json
│   │   │   │   │   │       │   ├── logicnode.schema.json
│   │   │   │   │   │       │   ├── rir.fn.schema.json
│   │   │   │   │   │       │   └── rir.module.schema.json
│   │   │   │   │   │       ├── scripts
│   │   │   │   │   │       │   └── validate_schemas.py
│   │   │   │   │   │       ├── services
│   │   │   │   │   │       │   ├── dashboard
│   │   │   │   │   │       │   │   ├── dashboard
│   │   │   │   │   │       │   │   │   ├── __init__.py
│   │   │   │   │   │       │   │   │   └── main.py
│   │   │   │   │   │       │   │   ├── Dockerfile
│   │   │   │   │   │       │   │   └── requirements.txt
│   │   │   │   │   │       │   └── orchestrator
│   │   │   │   │   │       │       ├── orchestrator
│   │   │   │   │   │       │       │   ├── __init__.py
│   │   │   │   │   │       │       │   └── main.py
│   │   │   │   │   │       │       ├── Dockerfile
│   │   │   │   │   │       │       └── requirements.txt
│   │   │   │   │   │       ├── BLUEPRINT_SPEC.md
│   │   │   │   │   │       ├── Makefile
│   │   │   │   │   │       └── README.md
│   │   │   │   │   ├── # PART 8 PROFESSIONAL GROUNDING & C.txt
│   │   │   │   │   ├── # Pod D Mathematical Pod - Complete.txt
│   │   │   │   │   ├── 00_Documentation_Index.md
│   │   │   │   │   ├── 00_Documentation_Index.txt
│   │   │   │   │   ├── 00_Documentation_Index.txt.md
│   │   │   │   │   ├── 01_Product_Requirements_Document.md
│   │   │   │   │   ├── 02_Technical_Vision_Document.md
│   │   │   │   │   ├── 03_Market_Competitive_Analysis.md
│   │   │   │   │   ├── 04_Product_Roadmap_Phasing_Strategy.md
│   │   │   │   │   ├── 05_System_Architecture_Document.md
│   │   │   │   │   ├── 06_Agent_Architecture_Specification.md
│   │   │   │   │   ├── 07_Communication_Protocol_Specification.md
│   │   │   │   │   ├── 08_Data_Architecture_Document.md
│   │   │   │   │   ├── 09_Refined_IR_Specification.md
│   │   │   │   │   ├── 10_Pod_A_Dynamic_Languages_Specification.md
│   │   │   │   │   ├── 11_Pod_B_Systems_Specification.md
│   │   │   │   │   ├── 12_Pod_C_Enterprise_Specification.md
│   │   │   │   │   ├── 13_Pod_D_Mathematical_Languages_Specification.md
│   │   │   │   │   ├── 14_Workflow_Orchestration_Design.md
│   │   │   │   │   ├── 15_Mission_Control_UI_Specification.md
│   │   │   │   │   ├── 16_Development_Environment_Setup.md
│   │   │   │   │   ├── 17_Docker_Containerization_Guide.md
│   │   │   │   │   ├── 18_Local_Infrastructure_Configuration_AW1.md
│   │   │   │   │   ├── 19_Agent_Base_Classes_Templates.md
│   │   │   │   │   ├── 20_Semantic_Bus_Implementation_Guide.md
│   │   │   │   │   ├── 21_Database_Setup_and_Schemas.md
│   │   │   │   │   ├── 22_API_Layer_Design_Implementation.md
│   │   │   │   │   ├── 23_Testing_Framework_Quality_Assurance.md
│   │   │   │   │   ├── 24_CICD_Pipeline_Configuration.md
│   │   │   │   │   ├── 25_Monitoring_Observability_Implementation.md
│   │   │   │   │   ├── 26_Security_Implementation_Hardening.md
│   │   │   │   │   ├── 27_Agent_Deployment_Operations_Guide.md
│   │   │   │   │   ├── 28_Development_Workflow_Best_Practices.md
│   │   │   │   │   ├── 29_Knowledge_Lake_Implementation_Guide.md
│   │   │   │   │   ├── 30_LogicNode_Registry_Implementation.md
│   │   │   │   │   ├── 31_Agent_Communication_Patterns.md
│   │   │   │   │   ├── 32_Production_Deployment_Guide.md
│   │   │   │   │   ├── 33_System_Maintenance_Procedures.md
│   │   │   │   │   ├── 34_Backup_Recovery_Operations.md
│   │   │   │   │   ├── 35_Scaling_Performance_Tuning.md
│   │   │   │   │   ├── 36_Incident_Response_Playbook.md
│   │   │   │   │   ├── 37_System_Monitoring_Dashboard_Configuration.md
│   │   │   │   │   ├── 38_Log_Aggregation_Analysis_Setup.md
│   │   │   │   │   ├── 39_Alerting_Notification_System.md
│   │   │   │   │   ├── 40_Disaster_Recovery_Testing_Procedures.md
│   │   │   │   │   ├── 41_Unit_Testing_Standards_Implementation.md
│   │   │   │   │   ├── 42_Integration_Testing_Framework.md
│   │   │   │   │   ├── 43_End_to_End_Testing_Scenarios.md
│   │   │   │   │   ├── 44_Performance_Testing_Benchmarking.md
│   │   │   │   │   ├── 45_Load_Testing_Stress_Testing.md
│   │   │   │   │   ├── 46_Security_Testing_Vulnerability_Assessment.md
│   │   │   │   │   ├── 47_Audit_Agent_Testing_Procedures.md
│   │   │   │   │   ├── 48_Test_Data_Management_Seeding.md
│   │   │   │   │   ├── 49_Regression_Testing_Strategy.md
│   │   │   │   │   ├── 50_Continuous_Testing_Strategy.md
│   │   │   │   │   ├── 51_Developer_Onboarding_Guide.md
│   │   │   │   │   ├── 52_API_Documentation_Reference.md
│   │   │   │   │   ├── 53_Agent_Development_Guide.md
│   │   │   │   │   ├── 54_Protocol_Extension_Guide.md
│   │   │   │   │   ├── 55_Glossary_Terminology_Reference.md
│   │   │   │   │   ├── 56_Architecture_Decision_Records_ADRs.md
│   │   │   │   │   ├── 57_FAQ_Document.md
│   │   │   │   │   ├── 58_Changelog_Release_Notes.md
│   │   │   │   │   ├── 59_User_Guide.md
│   │   │   │   │   ├── 60_System_Administrator_Guide.md
│   │   │   │   │   ├── 61_User_Stories_Use_Cases.md
│   │   │   │   │   ├── 62_User_Interaction_Guide.md
│   │   │   │   │   ├── 63_Graphics_Visual_Design_Style_Guide.md
│   │   │   │   │   ├── 64_User_Facing_IDE_Interface_Specification.md
│   │   │   │   │   ├── 8.txt
│   │   │   │   │   ├── AGENT-C-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-CPP-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-CS-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-GO-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-JAVA-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-PHP-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-RUBY-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-RUST-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-SCALA-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-ZIG-001_Complete_Profile.md
│   │   │   │   │   ├── agent1.txt
│   │   │   │   │   ├── agentsnotes2.txt
│   │   │   │   │   ├── AUDIT-CORRECTNESS-001_Complete_Profile.md
│   │   │   │   │   ├── AUDIT-LEAD-001_Complete_Profile.md
│   │   │   │   │   ├── AUDIT-PERF-001_Complete_Profile.md
│   │   │   │   │   ├── core idea.txt
│   │   │   │   │   ├── holy grail notes 1.txt
│   │   │   │   │   ├── holy grail notes 2.txt
│   │   │   │   │   ├── holy_grail_notes_1.txt
│   │   │   │   │   ├── LANGUAGE_AGENTS_BATCH.md
│   │   │   │   │   ├── MANAGER-POD-B-001_Complete_Profile.md
│   │   │   │   │   ├── MANAGER-POD-C-001_Complete_Profile.md
│   │   │   │   │   ├── MANAGER-POD-D-001_Complete_Profile.md
│   │   │   │   │   ├── master notes.txt
│   │   │   │   │   ├── New chatSearchChatsProjectsArtifact.txt
│   │   │   │   │   ├── notes 2.txt
│   │   │   │   │   ├── notes3.txt
│   │   │   │   │   ├── notes4.txt
│   │   │   │   │   ├── Part_8_Professional_Grounding_Reference.md
│   │   │   │   │   ├── plan.txt
│   │   │   │   │   ├── Pod A Manager.txt
│   │   │   │   │   ├── pod b setup.txt
│   │   │   │   │   ├── pod1.txt
│   │   │   │   │   ├── pod_b_setup.txt
│   │   │   │   │   ├── pod_c_complete.txt
│   │   │   │   │   ├── pod_c_detailed_specification.txt
│   │   │   │   │   ├── pod_d_mathematical_spec.md
│   │   │   │   │   ├── podnotes.txt
│   │   │   │   │   ├── PROFILE_COMPLETION_STATUS.md
│   │   │   │   │   ├── profile_creation_summary.md
│   │   │   │   │   ├── protocol_alpha_directive.md
│   │   │   │   │   ├── protocol_beta_production.md
│   │   │   │   │   ├── protocol_delta_sigma_audit_knowledge.md
│   │   │   │   │   ├── protocol_omega_rho_user_traffic.md
│   │   │   │   │   ├── Security Audit Agent.txt
│   │   │   │   │   ├── SUPPORT-DEVOPS-001_Complete_Profile.md
│   │   │   │   │   ├── Untitled.txt
│   │   │   │   │   ├── Untitled1.txt
│   │   │   │   │   ├── Untitled11.txt
│   │   │   │   │   ├── Untitled13.txt
│   │   │   │   │   ├── Untitled3.txt
│   │   │   │   │   ├── Untitled6.txt
│   │   │   │   │   └── Untitled9.txt
│   │   │   │   └── tmp_docs
│   │   │   │       ├── HGR_Backend_Checklist_v3_Final.docx.md
│   │   │   │       ├── HGR_Mission_Flow_v1_1.txt
│   │   │   │       ├── HGR_Mission_Flow_v2.txt
│   │   │   │       ├── HolyGrail_Development_Standards.docx.md
│   │   │   │       ├── HolyGrail_Frontend_Design_3.docx.md
│   │   │   │       ├── HolyGrail_Production_Review_Checklist.docx.md
│   │   │   │       └── HolyGrail_Style_Guide.docx.md
│   │   │   └── source-docx
│   │   │       ├── HGR_Agent_Model_Register.docx
│   │   │       ├── HGR_Backend_Checklist_v3_Final.docx
│   │   │       ├── HGR_Mission_Flow.docx
│   │   │       ├── HGR_Mission_Flow_v1_1.docx
│   │   │       ├── HGR_Mission_Flow_v2.docx
│   │   │       ├── HolyGrail_Design_Checklist.docx
│   │   │       ├── HolyGrail_Development_Standards.docx
│   │   │       ├── HolyGrail_Frontend_Design_3.docx
│   │   │       ├── HolyGrail_Production_Review_Checklist.docx
│   │   │       └── HolyGrail_Style_Guide.docx
│   │   ├── 2026-05-22
│   │   │   ├── # Local-First Error Handling Standa.txt
│   │   │   ├── # Local-First Security Architecture.txt
│   │   │   ├── Phase_25_completion_summary.md
│   │   │   ├── Phase_26_completion_summary.md
│   │   │   ├── Phase_27_completion_summary.md
│   │   │   ├── README.md
│   │   │   └── UI_UX_wireframe_review_original_2026-05-21.txt
│   │   ├── 2026-06-12
│   │   │   ├── ast-vs-regex-comparison-2026-04-14.md
│   │   │   ├── BLUEPRINT_SPEC.md
│   │   │   ├── codex-baseline-findings-2026-04-14.md
│   │   │   ├── Debugging_Error_Sweep_Plan.md
│   │   │   ├── end-to-end-review-2026-04-15.md
│   │   │   ├── fix_plan_2026-05-22.md
│   │   │   ├── Frontend_Phase_Updates.md
│   │   │   ├── HGR_Gap_Report_1.md
│   │   │   ├── HGR_Phased_Build_Plan.md
│   │   │   ├── HGR_Phased_Build_Plan_1.md
│   │   │   ├── mission-control-ui-ux-update-plan-2026-05-22.md
│   │   │   ├── Phase_01_Fix_Model_Layer.md
│   │   │   ├── Phase_02_CEO_Contract.md
│   │   │   ├── Phase_03_Specialist_Codegen.md
│   │   │   ├── Phase_03_to_07_Intelligence_Layer.md
│   │   │   ├── Phase_04_PM_Cognition.md
│   │   │   ├── Phase_08_to_11_Smelt_Cycle.md
│   │   │   ├── Phase_12_Equivalence_Verification_Harness.md
│   │   │   ├── Phase_12_to_18_Quality_Production.md
│   │   │   ├── Phase_13_Security_Compliance_Agents.md
│   │   │   ├── Phase_14_Dependency_Absorption_Engine.md
│   │   │   ├── Phase_15_Token_Cost_Ledger.md
│   │   │   ├── Phase_16_Knowledge_Lake_Embeddings.md
│   │   │   ├── Phase_17_DR_Release_Hardening.md
│   │   │   ├── Phase_18_Reproducible_Demo_Missions.md
│   │   │   ├── Phase_19_Agent_Prompt_Intelligence.md
│   │   │   ├── Phase_20_CEO_and_Support_Agent_Workflows.md
│   │   │   ├── Phase_21_Pod_Agent_Workflow_Depth.md
│   │   │   ├── Phase_22_Runtime_QC_TESTDATA_RQCA.md
│   │   │   ├── Phase_23_DEPABS_Execution.md
│   │   │   ├── Phase_24_PORT_Cross_Pod.md
│   │   │   ├── Phase_25_Prompt_Versioning_AI_Safety.md
│   │   │   ├── Phase_26_Production_Hardening.md
│   │   │   ├── Phase_27_Mission_Control_Convergence.md
│   │   │   ├── phased-update-plan-validated-2026-04-14.md
│   │   │   ├── production-remediation-plan-2026-04-17.md
│   │   │   ├── production_code_review_2026-05-22.md
│   │   │   ├── QC_Master_Checklist.md
│   │   │   └── review-todo-action-plan-2026-04-15.md
│   │   ├── 2026-06-13
│   │   │   ├── LONG_DURATION_RELIABILITY_QUALIFICATION.md
│   │   │   ├── PHASED_UPDATE_PLAN.md
│   │   │   ├── RELEASE_COMPLETION_PLAN.md
│   │   │   ├── REPOSITORY_BUILD_MAP_2026-03-29.md
│   │   │   ├── ROADMAP.md
│   │   │   ├── SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md
│   │   │   └── SPRINT_BACKLOG.md
│   │   └── README.md
│   ├── codex
│   │   ├── DEFINITION_OF_DONE.md
│   │   └── REVIEW_CHECKLIST.md
│   ├── diagrams
│   │   ├── 01_system_context.mermaid
│   │   ├── 02_container_architecture.mermaid
│   │   ├── 03_component_orchestrator.mermaid
│   │   ├── 04_component_api_gateway.mermaid
│   │   ├── 05_component_protocol_bus.mermaid
│   │   ├── 06_mission_intake_lifecycle_sequence.mermaid
│   │   ├── 07_agent_hierarchy_delegation.mermaid
│   │   ├── 08_data_information_flow.mermaid
│   │   ├── 09_security_trust_boundaries.mermaid
│   │   ├── 10_deployment_infrastructure.mermaid
│   │   ├── ENTERPRISE_ARCHITECTURE_DIAGRAMS.md
│   │   └── README.md
│   ├── enterprise
│   │   ├── API_SPECIFICATION_GUIDE.md
│   │   └── OPERATIONS_DR_PLAYBOOK.md
│   ├── evidence
│   │   ├── canary-runs
│   │   │   ├── dedicated_agent_canary_julia_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_julia_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_julia_20260529T024601Z.json
│   │   │   ├── dedicated_agent_canary_julia_20260529T025335Z.json
│   │   │   ├── dedicated_agent_canary_julia_20260529T025729Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260529T024601Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260529T025335Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260529T025729Z.json
│   │   │   ├── dedicated_agent_canary_python_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_python_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_python_20260529T023049Z.json
│   │   │   ├── dedicated_agent_canary_python_20260529T024601Z.json
│   │   │   ├── dedicated_agent_canary_python_20260529T025335Z.json
│   │   │   ├── dedicated_agent_canary_python_20260529T025729Z.json
│   │   │   ├── dedicated_agent_canary_rust_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_rust_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_rust_20260529T024601Z.json
│   │   │   ├── dedicated_agent_canary_rust_20260529T025335Z.json
│   │   │   └── dedicated_agent_canary_rust_20260529T025729Z.json
│   │   ├── agent_model_inventory_latest.json
│   │   ├── dedicated_agent_canary_full_dedicated_local_2026-04-15.json
│   │   ├── dedicated_agent_canary_full_dedicated_strict_2026-03-09.json
│   │   ├── dedicated_agent_canary_trend_2026-03-08.json
│   │   ├── dedicated_agent_canary_trend_history.jsonl
│   │   ├── dedicated_agent_canary_trend_latest.json
│   │   ├── dr_drill_phase26_20260519_232452.json
│   │   ├── dr_drill_phase26_20260519_234143.json
│   │   ├── dr_drill_phase26_latest.json
│   │   ├── dr_tls_verification_2026-05-22.md
│   │   ├── frontend_style_guide_compliance_2026-03-03.md
│   │   ├── langgraph_postgres_recovery_qualification_latest.json
│   │   ├── langgraph_v2_prototype_matrix_2026-03-08.json
│   │   ├── langgraph_v2_prototype_matrix_history.jsonl
│   │   ├── langgraph_v2_prototype_matrix_latest.json
│   │   ├── live_demo_sprint5_2026-05-25.json
│   │   ├── mission_artifact_qualification_dedicated_2026-03-08.json
│   │   ├── mission_artifact_qualification_full_dedicated_local_2026-04-15.json
│   │   ├── mission_artifact_qualification_full_dedicated_strict_2026-03-09.json
│   │   ├── mission_artifact_qualification_history.jsonl
│   │   ├── mission_artifact_qualification_latest.json
│   │   ├── mission_artifact_qualification_shared_2026-03-08.json
│   │   ├── mission_artifact_qualification_v1_1_latest.json
│   │   ├── model_inventory_latest.json
│   │   ├── operator_route_oidc_matrix_2026-03-08.json
│   │   ├── operator_route_oidc_matrix_history.jsonl
│   │   ├── operator_route_oidc_matrix_latest.json
│   │   ├── phase12_builder_repo_validation_2026-03-03.md
│   │   ├── phase13_script_validation_2026-03-03.md
│   │   ├── phase14_legacy_reconciliation_2026-03-03.md
│   │   ├── phase15_live_integration_validation_2026-03-03.md
│   │   ├── phase16_data_system_activation_validation_2026-03-03.md
│   │   ├── phase17_dr_release_hardening_2026-05-19.json
│   │   ├── phase17_neo4j_feature_flag_validation_2026-03-03.md
│   │   ├── phase18_demo_missions_latest.json
│   │   ├── phase18_object_storage_validation_2026-03-03.md
│   │   ├── phase19_20_prompt_workflow_2026-05-19.json
│   │   ├── phase21_pod_workflow_depth_2026-05-20.json
│   │   ├── phase22_23_runtime_qc_depabs_2026-05-20.json
│   │   ├── phase23_langgraph_baseline_validation_2026-03-03.md
│   │   ├── phase24_langgraph_postgres_checkpointer_validation_2026-03-03.md
│   │   ├── phase25_word_doc_audit_and_langgraph_runtime_visibility_2026-03-03.md
│   │   ├── phase26_langgraph_live_recovery_validation_2026-03-03.md
│   │   ├── phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json
│   │   ├── phase27_final_release_qualification_2026-05-19.md
│   │   ├── phase27_mission_control_live_transport_validation_2026-03-04.md
│   │   ├── phase28_smelt_cycle_runtime_reconciliation_validation_2026-03-04.md
│   │   ├── phase29_topology_and_security_adr_validation_2026-03-04.md
│   │   ├── phase30_auth_mode_and_dedicated_profile_validation_2026-03-04.md
│   │   ├── phase31_dedicated_agent_binding_scheduler_validation_2026-03-04.md
│   │   ├── phase32_optional_data_plane_observability_validation_2026-03-04.md
│   │   ├── phase33_extended_data_plane_live_qualification_validation_2026-03-04.md
│   │   ├── phase34_mission_control_advanced_operator_ux_validation_2026-03-04.md
│   │   ├── phase35_mission_artifact_runtime_integrity_validation_2026-03-08.md
│   │   ├── phase36_frontend_budget_a11y_enforcement_2026-03-08.md
│   │   ├── phase37_strategy_auth_canary_2026-03-08.md
│   │   ├── phase38_qualification_matrix_automation_2026-03-08.md
│   │   ├── phase39_llm_node_wiring_hardening_2026-03-08.md
│   │   ├── phase40_supply_chain_and_secret_hygiene.md
│   │   ├── phase41_build_and_package_artifact_pipeline.md
│   │   ├── phase42_shared_state_and_api_convergence.md
│   │   ├── phase43_ai_safety_prompt_governance_eval_gates.md
│   │   ├── phase44_infrastructure_backup_restore_incident_readiness.md
│   │   ├── phase45_mission_control_convergence_and_final_release_qualification.md
│   │   ├── pod_language_extraction_2026-03-03.md
│   │   ├── qualification_gate_summary_latest.json
│   │   ├── qualification_gate_summary_phase17_2026-05-19.json
│   │   ├── reliability_qualification_baseline_2026-03-03.json
│   │   ├── s502_cost_ledger_live_2026-05-29.json
│   │   ├── s503_gemini_embeddings_live_2026-05-29.json
│   │   ├── s5_handoff_findings_2026-05-28.md
│   │   └── word_doc_extraction_2026-03-08.json
│   ├── openapi
│   │   ├── api-gateway.v1.json
│   │   └── orchestrator.v1.json
│   ├── phases
│   ├── reviews
│   ├── runbooks
│   │   ├── dedicated_agent_canary_runbook.md
│   │   ├── dr_validation_runbook.md
│   │   ├── optional_data_plane_incident_runbook.md
│   │   ├── protocol_bus_incident_runbook.md
│   │   └── qualification_matrix_runbook.md
│   ├── user
│   │   ├── GETTING_STARTED.md
│   │   └── OPERATOR_GUIDE.md
│   ├── 00_PRODUCT_OVERVIEW.md
│   ├── ACCESSIBILITY_STATEMENT.md
│   ├── ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md
│   ├── ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md
│   ├── ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md
│   ├── ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md
│   ├── ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md
│   ├── AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md
│   ├── AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md
│   ├── AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md
│   ├── AGENT_SCALING_AND_HEARTBEAT.md
│   ├── AGENT_SERVICE_KEY_ISOLATION.md
│   ├── API_INTEGRATION_GUIDE.md
│   ├── APPLICATION_INTELLIGENCE_MAP.md
│   ├── ARCHITECTURE.md
│   ├── ARCHITECTURE_DATA_FLOWS.md
│   ├── ARCHITECTURE_DIAGRAMS.md
│   ├── BLUEPRINT_MAP.md
│   ├── COMPLIANCE_EVIDENCE_MAPPING.md
│   ├── COMPOSE_ENVIRONMENT_PROFILES.md
│   ├── CURRENT_TODO.md
│   ├── DATA_CLASSIFICATION_POLICY.md
│   ├── DEMO_MISSION_SETUP.md
│   ├── DEPENDENCY_ABSORPTION_DOCTRINE.md
│   ├── DEPLOYMENT_DR_PLAYBOOK.md
│   ├── DEVELOPER_GUIDE.md
│   ├── DEVELOPER_ONBOARDING_GUIDE.md
│   ├── DIAGRAM_STANDARDS.md
│   ├── DOCUMENTATION_INDEX.md
│   ├── DOCUMENTATION_STANDARDS.md
│   ├── EQUIVALENCE_VERIFIER.md
│   ├── ERROR_CODES.md
│   ├── HANDOFF_CURRENT.md
│   ├── IMPLEMENTATION_STATUS.md
│   ├── IS_AGENT.md
│   ├── KNOWLEDGE_LAKE_AND_EMBEDDINGS.md
│   ├── LEGACY_PROFILE_ID_MAPPING_INDEX.md
│   ├── LICENSE_STRATEGY.md
│   ├── LLM_DELEGATION.md
│   ├── LLM_SAFETY_AND_DOCUMENT_PARSER.md
│   ├── LOCAL_FIRST_COMPLIANCE_PLAN.md
│   ├── LOGICNODE_SCHEMA.md
│   ├── METRICS_SOURCE_MODULES.md
│   ├── MISSION_FLOW_V2.md
│   ├── MODEL_PROMOTION_GOVERNANCE.md
│   ├── MODELS_AND_DOMAIN_SCHEMA.md
│   ├── OBSERVABILITY_STACK.md
│   ├── OPERATIONS_RUNBOOK.md
│   ├── ORCHESTRATOR_MAIN.md
│   ├── PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md
│   ├── PRIVACY_POLICY.md
│   ├── PRODUCTION_STANDARDS_REFERENCES.md
│   ├── PROMPT_REGISTRY_AND_ASSETS.md
│   ├── RELEASE_TRUST_PROMOTION_GATE.md
│   ├── REPOSITORY_BUILD_MAP_2026-06-13.md
│   ├── ROUTES_REFERENCE.md
│   ├── RUNTIME_AND_AGENT_BASE.md
│   ├── RUNTIME_QC_AND_TEST_ENVIRONMENTS.md
│   ├── SCHEMA_REGISTRY_AND_VERSIONING.md
│   ├── SECURITY_COMPLIANCE_MODULE.md
│   ├── SENSITIVE_CODE_HANDLING_POLICY.md
│   ├── SETTINGS_REFERENCE.md
│   ├── STORAGE_LAYER.md
│   ├── SUPPORTING_MODULES.md
│   ├── TERMS_OF_SERVICE.md
│   ├── TESTING_QUALITY_GATES.md
│   ├── TRACING.md
│   └── WHAT_THEFACTORY_IS_AND_IS_NOT.md
├── examples
│   ├── logicnode.example.json
│   ├── rir.fn.example.json
│   └── rir.module.example.json
├── ledger
│   └── schema.sql
├── protocol
│   └── topics.yaml
├── reports
│   └── dr-drill-latest.json
├── schemas
│   ├── event.envelope.schema.json
│   ├── logicnode.schema.json
│   ├── mission_charter.v1.json
│   ├── mission_charter.v1.schema.json
│   ├── rir.fn.schema.json
│   └── rir.module.schema.json
├── scripts
│   ├── backup_postgres.ps1
│   ├── build_refined_ir_catalog.py
│   ├── check_coverage_thresholds.py
│   ├── check_env.py
│   ├── debug_sweep.ps1
│   ├── dedicated_agent_canary_rollout.ps1
│   ├── dedicated_agent_canary_rollout.py
│   ├── dedicated_agent_canary_trend.ps1
│   ├── dedicated_agent_canary_trend.py
│   ├── demo_missions.py
│   ├── dora_metrics_summary.py
│   ├── dr_drill.ps1
│   ├── execute_git_history_scrub.ps1
│   ├── execute_git_history_scrub.py
│   ├── export_agent_model_inventory.py
│   ├── export_openapi.py
│   ├── force_stop.py
│   ├── generate_agent_service_keys.py
│   ├── generate_build_map.py
│   ├── generate_dev_tls_certs.ps1
│   ├── generate_dev_tls_certs.sh
│   ├── generate_postgres_tls_certs.py
│   ├── generate_prompt_manifest.py
│   ├── langgraph_postgres_recovery_qualification.ps1
│   ├── langgraph_postgres_recovery_qualification.py
│   ├── langgraph_v2_prototype_matrix.ps1
│   ├── langgraph_v2_prototype_matrix.py
│   ├── mission_artifact_qualification.ps1
│   ├── mission_artifact_qualification.py
│   ├── normalize_document_headers.py
│   ├── operator_route_auth_matrix_qualification.ps1
│   ├── operator_route_auth_matrix_qualification.py
│   ├── perf_smoke.ps1
│   ├── perf_smoke.py
│   ├── phase17_release_hardening_evidence.py
│   ├── pre_deploy_check.ps1
│   ├── production_review_audit.py
│   ├── promotion_gate.py
│   ├── prune_audit_tables.py
│   ├── qualification_gate_summary.py
│   ├── reliability_qualification.ps1
│   ├── reliability_qualification.py
│   ├── restore_postgres.ps1
│   ├── rotate_secrets.sh
│   ├── run_automated_dr_drill.py
│   ├── run_demo_mission.py
│   ├── smoke_ceo_delegation.py
│   ├── validate_documentation.py
│   ├── validate_schemas.py
│   ├── verify_backup_artifacts.py
│   └── verify_release_evidence.py
├── services
│   ├── agent-runtime
│   │   ├── agent_runtime
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── api-gateway
│   │   ├── api_gateway
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── audit-worker
│   │   ├── audit_worker
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── dashboard
│   │   ├── dashboard
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── orchestrator
│   │   ├── orchestrator
│   │   │   ├── llm_delegation
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agents.py
│   │   │   │   ├── config.py
│   │   │   │   ├── fallbacks.py
│   │   │   │   ├── generators.py
│   │   │   │   ├── generators_artifacts.py
│   │   │   │   ├── health.py
│   │   │   │   ├── metrics.py
│   │   │   │   ├── normalizers.py
│   │   │   │   ├── prompts.py
│   │   │   │   ├── providers.py
│   │   │   │   └── text.py
│   │   │   ├── migrations
│   │   │   │   ├── V001_initial_runtime_schema.sql
│   │   │   │   ├── V002_build_artifact_runtime_schema.sql
│   │   │   │   ├── V003_review_approval_runtime_schema.sql
│   │   │   │   ├── V004_review_approval_expiry_and_hmac.sql
│   │   │   │   ├── V005_project_audit_event_schema.sql
│   │   │   │   ├── V006_runtime_qc_schema.sql
│   │   │   │   ├── V007_llm_usage_ledger_schema.sql
│   │   │   │   ├── V008_audit_table_retention.sql
│   │   │   │   └── V009_immutable_audit.sql
│   │   │   ├── mission_flow_v2
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── lifecycle.py
│   │   │   │   ├── phases_build.py
│   │   │   │   ├── phases_delivery.py
│   │   │   │   ├── phases_intake.py
│   │   │   │   ├── phases_runtime.py
│   │   │   │   └── transitions.py
│   │   │   ├── prompt_assets
│   │   │   │   ├── ceo_delegation.v1.json
│   │   │   │   ├── ceo_mission_contract.v1.json
│   │   │   │   ├── integration_tests.v1.json
│   │   │   │   ├── manifest.json
│   │   │   │   ├── master_logic_stream.v1.json
│   │   │   │   ├── pm_delivery_summary.v1.json
│   │   │   │   ├── pm_feature_contract.v1.json
│   │   │   │   ├── pod_audit_verdict.v1.json
│   │   │   │   ├── pod_group_standard.v1.json
│   │   │   │   ├── security_threat_analysis.v1.json
│   │   │   │   ├── specialist_codegen.v1.json
│   │   │   │   └── vc_commit_strategy.v1.json
│   │   │   ├── routes
│   │   │   │   ├── __init__.py
│   │   │   │   ├── _deps.py
│   │   │   │   ├── internal.py
│   │   │   │   ├── missions.py
│   │   │   │   └── operations.py
│   │   │   ├── __init__.py
│   │   │   ├── agent_base.py
│   │   │   ├── agent_integrations.py
│   │   │   ├── agent_personas.py
│   │   │   ├── agent_registry.py
│   │   │   ├── agent_scaling.py
│   │   │   ├── aim_generator.py
│   │   │   ├── audit_events.py
│   │   │   ├── auth.py
│   │   │   ├── build_artifacts.py
│   │   │   ├── data_plane_metrics.py
│   │   │   ├── dependency_absorption.py
│   │   │   ├── document_parser.py
│   │   │   ├── equivalence_verifier.py
│   │   │   ├── heartbeat_service.py
│   │   │   ├── hw_agent.py
│   │   │   ├── is_agent.py
│   │   │   ├── knowledge_embeddings.py
│   │   │   ├── knowledge_lake.py
│   │   │   ├── langgraph_lifecycle.py
│   │   │   ├── lifecycle_interface.py
│   │   │   ├── lifecycle_recovery.py
│   │   │   ├── llm_cost_ledger.py
│   │   │   ├── llm_safety.py
│   │   │   ├── logicnode_schema.py
│   │   │   ├── main.py
│   │   │   ├── migrations.py
│   │   │   ├── milvus_store.py
│   │   │   ├── mission_flow.py
│   │   │   ├── models.py
│   │   │   ├── neo4j_store.py
│   │   │   ├── object_store.py
│   │   │   ├── orchestrator_metrics.py
│   │   │   ├── port_coordinator.py
│   │   │   ├── project_identity.py
│   │   │   ├── prompt_registry.py
│   │   │   ├── protocol.py
│   │   │   ├── protocol_bus_consumer.py
│   │   │   ├── protocol_bus_producer.py
│   │   │   ├── qdrant_store.py
│   │   │   ├── review_policy.py
│   │   │   ├── rqca_agent.py
│   │   │   ├── runtime.py
│   │   │   ├── security_compliance.py
│   │   │   ├── settings.py
│   │   │   ├── storage.py
│   │   │   ├── storage_agents.py
│   │   │   ├── storage_artifacts.py
│   │   │   ├── storage_core.py
│   │   │   ├── storage_logicnodes.py
│   │   │   ├── storage_missions.py
│   │   │   ├── storage_pods.py
│   │   │   ├── system_maintenance.py
│   │   │   ├── testdata_agent.py
│   │   │   └── tracing.py
│   │   ├── tests
│   │   │   └── test_agent_base_specialists.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── pod-worker
│   │   ├── pod_worker
│   │   │   ├── __init__.py
│   │   │   ├── ast_extractor.py
│   │   │   ├── concept_catalog.py
│   │   │   ├── java_ast_extractor.py
│   │   │   ├── js_ast_extractor.py
│   │   │   ├── language_extractor.py
│   │   │   ├── main.py
│   │   │   ├── refined_ir.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── protocol-bus-mcp
│       ├── protocol_bus
│       │   ├── __init__.py
│       │   ├── mcp_server.py
│       │   └── tracing.py
│       ├── Dockerfile
│       └── requirements.txt
├── shared_runtime
│   ├── __init__.py
│   ├── agent_auth.py
│   ├── agent_keys.py
│   ├── atomic_io.py
│   ├── crypto_keystore.py
│   ├── crypto_signing.py
│   ├── errors.py
│   ├── logging_config.py
│   ├── pii_guard.py
│   ├── prompt_guard.py
│   └── protocol.py
├── test-keys
│   ├── keys.txt
│   ├── list_gemini_models.py
│   ├── probe_gemini.py
│   └── validate_keys.py
├── tests
│   ├── eval
│   │   ├── conftest_eval.py
│   │   ├── golden_delegation_cases.json
│   │   ├── test_llm_delegation_golden.py
│   │   ├── test_pm_contract_evals.py
│   │   ├── test_prompt_registry_evals.py
│   │   └── test_safety_evals.py
│   ├── fixtures
│   │   └── extractors
│   │       ├── java_sample.java
│   │       ├── javascript_sample.js
│   │       ├── python_sample.py
│   │       ├── rust_sample.rs
│   │       └── typescript_sample.ts
│   ├── load
│   │   └── locustfile.py
│   ├── scripts
│   │   ├── test_backup_dr_scripts.py
│   │   ├── test_build_refined_ir_catalog.py
│   │   ├── test_dedicated_agent_canary_rollout.py
│   │   ├── test_dedicated_agent_canary_trend.py
│   │   ├── test_demo_missions.py
│   │   ├── test_dora_metrics_summary.py
│   │   ├── test_export_agent_model_inventory.py
│   │   ├── test_generate_agent_service_keys.py
│   │   ├── test_langgraph_postgres_recovery_qualification.py
│   │   ├── test_langgraph_v2_prototype_matrix.py
│   │   ├── test_mission_artifact_qualification.py
│   │   ├── test_operator_route_auth_matrix_qualification.py
│   │   ├── test_perf_smoke.py
│   │   ├── test_phase17_release_hardening_evidence.py
│   │   ├── test_production_review_audit.py
│   │   ├── test_promotion_gate.py
│   │   ├── test_qualification_gate_summary.py
│   │   ├── test_reliability_qualification.py
│   │   ├── test_verify_backup_artifacts.py
│   │   └── test_verify_release_evidence.py
│   ├── security
│   │   ├── test_pod_assignment_conflict.py
│   │   └── test_state_mutation_auth.py
│   ├── services
│   │   ├── test_agent_base_unit.py
│   │   ├── test_agent_core_unit.py
│   │   ├── test_agent_personas_registry.py
│   │   ├── test_agent_runtime_tracing_unit.py
│   │   ├── test_agent_runtime_unit.py
│   │   ├── test_agent_scaling.py
│   │   ├── test_aim_generator_unit.py
│   │   ├── test_api_gateway_auth_mode_unit.py
│   │   ├── test_api_gateway_helpers_unit.py
│   │   ├── test_api_gateway_live_stream_unit.py
│   │   ├── test_ast_extractor.py
│   │   ├── test_atomic_io_unit.py
│   │   ├── test_audit_worker_unit.py
│   │   ├── test_auth_unit.py
│   │   ├── test_build_artifacts_unit.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_concept_catalog.py
│   │   ├── test_crypto_signing_unit.py
│   │   ├── test_dashboard_snapshot.py
│   │   ├── test_dependency_absorption_unit.py
│   │   ├── test_digital_signatures_integration.py
│   │   ├── test_document_parser_unit.py
│   │   ├── test_envelope_schema_contract.py
│   │   ├── test_equivalence_verifier_unit.py
│   │   ├── test_errors_unit.py
│   │   ├── test_factory_error_handler_unit.py
│   │   ├── test_fusion_rir_verify.py
│   │   ├── test_hardened_api_keys.py
│   │   ├── test_health.py
│   │   ├── test_is_agent_fetch_unit.py
│   │   ├── test_knowledge_embeddings_unit.py
│   │   ├── test_langgraph_lifecycle_unit.py
│   │   ├── test_language_extractor.py
│   │   ├── test_language_extractor_golden.py
│   │   ├── test_lifecycle_interface_unit.py
│   │   ├── test_live_extended_data_plane_integration.py
│   │   ├── test_live_mission_flow_integration.py
│   │   ├── test_llm_cost_ledger_unit.py
│   │   ├── test_llm_delegation_prompt_safety.py
│   │   ├── test_llm_delegation_retry_unit.py
│   │   ├── test_llm_delegation_unit.py
│   │   ├── test_logicnode_schema.py
│   │   ├── test_migrations_unit.py
│   │   ├── test_milvus_store_unit.py
│   │   ├── test_mission_flow_unit.py
│   │   ├── test_mission_flow_v2.py
│   │   ├── test_neo4j_store_unit.py
│   │   ├── test_object_store_unit.py
│   │   ├── test_observability_metrics_unit.py
│   │   ├── test_orchestrator_agent_key_mode.py
│   │   ├── test_orchestrator_endpoints_extra.py
│   │   ├── test_orchestrator_lifecycle_recovery_unit.py
│   │   ├── test_orchestrator_main_helpers_unit.py
│   │   ├── test_pii_guard.py
│   │   ├── test_pod_worker_consumer.py
│   │   ├── test_pod_worker_unit.py
│   │   ├── test_production_foundations.py
│   │   ├── test_prompt_guard.py
│   │   ├── test_prompt_integrity_unit.py
│   │   ├── test_protocol_and_auth.py
│   │   ├── test_protocol_bus_consumer.py
│   │   ├── test_protocol_bus_dedup.py
│   │   ├── test_protocol_bus_mcp.py
│   │   ├── test_qdrant_store_unit.py
│   │   ├── test_refined_ir_unit.py
│   │   ├── test_regression_contracts.py
│   │   ├── test_review_policy_unit.py
│   │   ├── test_runtime_qc_unit.py
│   │   ├── test_runtime_stale_consumer.py
│   │   ├── test_runtime_unit.py
│   │   ├── test_security_compliance_unit.py
│   │   ├── test_storage_missions_unit.py
│   │   ├── test_storage_pool_unit.py
│   │   ├── test_storage_unit.py
│   │   ├── test_tracing_unit.py
│   │   ├── test_tracing_wiring_unit.py
│   │   └── test_type_annotations.py
│   └── shared_runtime
│       └── test_agent_auth.py
├── .coverage
├── .dockerignore
├── .editorconfig
├── .env
├── .env.agent-service-keys.local
├── .env.example
├── .gitignore
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── AGENTS.md
├── CHANGELOG.md
├── CLA.md
├── CODE_OF_CONDUCT.md
├── conftest.py
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── MIGRATION.md
├── pyproject.toml
├── README.md
├── requirements-dev.txt
├── SECURITY.md
├── start_app.bat
└── stop_app.bat
```
