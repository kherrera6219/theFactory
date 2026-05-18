# MISSION CONTROL UI SPECIFICATION

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Interactive Dashboard for Holy Grail Refinery

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase - Complete Specification  
**Document Owner:** Frontend Team Lead

---

## EXECUTIVE SUMMARY

Mission Control is the visual command center for the Holy Grail Refinery. A Next.js/React web application providing real-time visibility into all 35 agents, active missions, LogicNode processing, and system health.

**Key Features:**
- **Real-Time Agent Status** - Live visualization of all 35 agents
- **Mission Timeline** - Track progress from vibe to binary
- **LogicNode Explorer** - Interactive dependency graphs
- **Semantic Bus Monitor** - Live message stream
- **Performance Metrics** - Resource usage and bottlenecks
- **Alert Management** - System health notifications

**Technology Stack:**
- Next.js 14 (React 19)
- Tailwind CSS
- WebSocket (real-time updates)
- D3.js (visualizations)
- Redis Pub/Sub (backend)

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Application Structure

```
mission-control/
├── app/                    # Next.js 14 app directory
│   ├── dashboard/         # Main dashboard page
│   ├── missions/          # Mission detail views
│   ├── agents/            # Agent roster & profiles
│   ├── logicnodes/        # LogicNode explorer
│   └── settings/          # System configuration
├── components/
│   ├── AgentStatusGrid/   # 35-agent live status
│   ├── MissionTimeline/   # Workflow visualization
│   ├── LogicNodeGraph/    # Dependency graph
│   ├── SemanticBusLog/    # Message stream
│   └── MetricsPanel/      # Performance charts
├── lib/
│   ├── websocket.ts       # WebSocket client
│   ├── api-client.ts      # REST API wrapper
│   └── state.ts           # Global state management
└── public/
    └── assets/            # Icons, images
```

---

### 1.2 Data Flow

```
Backend (Python/FastAPI)
    │
    ├─→ REST API (mission data, agent profiles)
    │
    ├─→ WebSocket Server (real-time updates)
    │       │
    │       ├─→ Agent state changes
    │       ├─→ LogicNode events
    │       ├─→ Message bus activity
    │       └─→ System alerts
    │
    └─→ Redis Pub/Sub (Semantic Bus)
            ↓
Frontend (Next.js/React)
    │
    ├─→ WebSocket Client (subscribe to events)
    │
    ├─→ State Management (Zustand/Jotai)
    │
    └─→ UI Components (render live data)
```

---

## 2. MAIN DASHBOARD INTERFACE

### 2.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Holy Grail Refinery - Mission Control                     │
│  Mission: Trading Dashboard | Status: Extraction (65%)     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  System Status  │  │  Active Mission │                 │
│  │                 │  │                 │                 │
│  │  ● 35 Agents    │  │  Phase:         │                 │
│  │    Online       │  │  Pod Extraction │                 │
│  │                 │  │                 │                 │
│  │  ● Phase:       │  │  Progress:      │                 │
│  │    Extraction   │  │  [=========>  ] │                 │
│  │    65%          │  │  65%            │                 │
│  │                 │  │                 │                 │
│  │  ● Est. Time:   │  │  LogicNodes:    │                 │
│  │    8 minutes    │  │  47 extracted   │                 │
│  │                 │  │  12 verified    │                 │
│  └─────────────────┘  └─────────────────┘                 │
│                                                              │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Agent Status Grid (35 Agents)                     │   │
│  │                                                      │   │
│  │  Executive Tier                                     │   │
│  │  [PM: IDLE]  [CEO: MONITORING]                     │   │
│  │                                                      │   │
│  │  Support Ring                                       │   │
│  │  [IS: INDEXING]  [Broker: ACTIVE]  [Acct: IDLE]   │   │
│  │  [Sec: SCANNING] [Dip: IDLE]       [SRE: ACTIVE]  │   │
│  │  [Data: IDLE]    [Comp: IDLE]      [DevOps: ACTIVE]│   │
│  │                                                      │   │
│  │  Pod A (Dynamic)                                    │   │
│  │  [Mgr: CONSOLIDATION]  [Audit: VERIFICATION]       │   │
│  │  [PY: MINING]  [JS: REFINEMENT]  [RUBY: IDLE]      │   │
│  │  [PHP: IDLE]                                        │   │
│  │                                                      │   │
│  │  Pod B (Systems)  Pod C (Enterprise)  Pod D (Math) │   │
│  │  [Similar layout for each pod]                      │   │
│  └────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Semantic Bus Activity (Live Stream)                │   │
│  │                                                      │   │
│  │  12:34:56 [Alpha] CEO → Pod A Mgr: Assignment      │   │
│  │  12:34:57 [Beta]  PY-001 → Audit: LogicNode        │   │
│  │  12:34:58 [Delta] Audit → PY-001: VERIFIED         │   │
│  │  12:34:59 [Sigma] IS → Knowledge: Index Update     │   │
│  │  12:35:00 [Alpha] CEO → Pod B Mgr: Assignment      │   │
│  └────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.2 Agent Status Grid Component

**Visual Design:**
```typescript
// AgentStatusCard.tsx
interface AgentCardProps {
  agent: {
    id: string
    name: string
    role: string
    state: string
    workload: number
    lastActive: Date
  }
}

function AgentStatusCard({ agent }: AgentCardProps) {
  const stateColors = {
    IDLE: 'bg-gray-500',
    ACTIVE: 'bg-green-500',
    MINING: 'bg-blue-500',
    VERIFICATION: 'bg-yellow-500',
    ERROR: 'bg-red-500'
  }
  
  return (
    <div className="p-4 border rounded-lg shadow-sm hover:shadow-md transition">
      <div className="flex items-center gap-2">
        <div className={`w-3 h-3 rounded-full ${stateColors[agent.state]}`} />
        <span className="font-semibold">{agent.name}</span>
      </div>
      <div className="text-sm text-gray-600 mt-1">{agent.state}</div>
      <div className="text-xs text-gray-400 mt-2">
        Workload: {agent.workload}%
      </div>
    </div>
  )
}
```

---

### 2.3 Mission Timeline Component

**Visual Representation:**
```
Vibe → PRD → Decompose → Extract → Verify → Fusion → Optimize → Delivery
  ✓      ✓       ✓          ⟳        ⧖        ○         ○          ○

Timeline Legend:
✓ = Complete
⟳ = In Progress (animated spinner)
⧖ = Queued
○ = Not Started
```

**Implementation:**
```typescript
// MissionTimeline.tsx
const phases = [
  { name: 'Vibe Capture', agent: 'PM', status: 'complete' },
  { name: 'PRD Generation', agent: 'PM', status: 'complete' },
  { name: 'Decomposition', agent: 'CEO', status: 'complete' },
  { name: 'Pod Extraction', agent: 'Pods A-D', status: 'active' },
  { name: 'Audit Verification', agent: 'Audit', status: 'queued' },
  { name: 'Grand Fusion', agent: 'CEO', status: 'pending' },
  { name: 'Optimization', agent: 'Pod B', status: 'pending' },
  { name: 'Delivery', agent: 'PM', status: 'pending' }
]

function MissionTimeline() {
  return (
    <div className="flex items-center gap-4">
      {phases.map((phase, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <PhaseIcon status={phase.status} />
          <div>
            <div className="font-medium">{phase.name}</div>
            <div className="text-sm text-gray-500">{phase.agent}</div>
          </div>
          {idx < phases.length - 1 && <Arrow />}
        </div>
      ))}
    </div>
  )
}
```

---

## 3. LOGICNODE EXPLORER

### 3.1 Interactive Dependency Graph

**D3.js Force-Directed Graph:**
```typescript
// LogicNodeGraph.tsx
import * as d3 from 'd3'

function LogicNodeGraph({ nodes, links }) {
  useEffect(() => {
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
    
    const svg = d3.select('#graph-svg')
    
    // Draw links
    svg.selectAll('.link')
      .data(links)
      .enter()
      .append('line')
      .attr('class', 'link')
      .attr('stroke', '#999')
      .attr('stroke-width', 1)
    
    // Draw nodes
    svg.selectAll('.node')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('class', 'node')
      .attr('r', 8)
      .attr('fill', d => getNodeColor(d.domain))
      .on('click', showNodeDetails)
    
    simulation.on('tick', () => {
      // Update positions
      svg.selectAll('.link')
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      
      svg.selectAll('.node')
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
    })
  }, [nodes, links])
  
  return <svg id="graph-svg" width={800} height={600} />
}
```

---

### 3.2 LogicNode Detail Panel

**Slide-out Panel:**
```typescript
// LogicNodeDetails.tsx
function LogicNodeDetails({ node }) {
  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-lg p-6">
      <h2 className="text-xl font-bold mb-4">{node.concept}</h2>
      
      <div className="mb-4">
        <label className="text-sm text-gray-600">Domain</label>
        <div className="font-medium">{node.domain}</div>
      </div>
      
      <div className="mb-4">
        <label className="text-sm text-gray-600">Intent</label>
        <div className="text-sm">{node.intent}</div>
      </div>
      
      <div className="mb-4">
        <label className="text-sm text-gray-600">Inputs</label>
        <pre className="bg-gray-100 p-2 rounded text-xs">
          {JSON.stringify(node.inputs, null, 2)}
        </pre>
      </div>
      
      <div className="mb-4">
        <label className="text-sm text-gray-600">Audit Status</label>
        <div className={`inline-block px-2 py-1 rounded ${
          node.audit_status === 'verified' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
        }`}>
          {node.audit_status}
        </div>
      </div>
      
      <div className="mb-4">
        <label className="text-sm text-gray-600">Tests Passed</label>
        <div>{node.equivalence_tests_passed} / {node.equivalence_tests_total}</div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
          <div 
            className="bg-green-500 h-2 rounded-full" 
            style={{ width: `${(node.equivalence_tests_passed / node.equivalence_tests_total) * 100}%` }}
          />
        </div>
      </div>
    </div>
  )
}
```

---

## 4. SEMANTIC BUS MONITOR

### 4.1 Live Message Stream

**WebSocket Integration:**
```typescript
// useSemanticBusStream.ts
import { useEffect, useState } from 'react'

export function useSemanticBusStream() {
  const [messages, setMessages] = useState([])
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/semantic-bus')
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      setMessages(prev => [message, ...prev].slice(0, 100)) // Keep last 100
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    return () => ws.close()
  }, [])
  
  return messages
}

// SemanticBusLog.tsx
function SemanticBusLog() {
  const messages = useSemanticBusStream()
  const [filter, setFilter] = useState('all')
  
  const protocols = ['all', 'Alpha', 'Beta', 'Delta', 'Sigma', 'Omega', 'Rho']
  
  const filtered = messages.filter(m => 
    filter === 'all' || m.protocol === filter
  )
  
  return (
    <div className="h-64 overflow-y-auto bg-black text-green-400 p-4 rounded font-mono text-sm">
      <div className="mb-2 flex gap-2">
        {protocols.map(p => (
          <button
            key={p}
            onClick={() => setFilter(p)}
            className={`px-2 py-1 rounded ${filter === p ? 'bg-green-700' : 'bg-gray-700'}`}
          >
            {p}
          </button>
        ))}
      </div>
      
      {filtered.map((msg, idx) => (
        <div key={idx} className="mb-1">
          <span className="text-gray-500">{msg.timestamp}</span>
          <span className="text-blue-400"> [{msg.protocol}]</span>
          <span> {msg.source} → {msg.target}:</span>
          <span className="text-yellow-400"> {msg.type}</span>
        </div>
      ))}
    </div>
  )
}
```

---

### 4.2 Message Filtering & Search

**Advanced Filtering:**
```typescript
// MessageFilters.tsx
function MessageFilters({ onFilterChange }) {
  return (
    <div className="flex gap-4 mb-4">
      <input
        type="text"
        placeholder="Search by agent ID..."
        onChange={(e) => onFilterChange({ agent: e.target.value })}
        className="border rounded px-3 py-2"
      />
      
      <select
        onChange={(e) => onFilterChange({ protocol: e.target.value })}
        className="border rounded px-3 py-2"
      >
        <option value="">All Protocols</option>
        <option value="Alpha">Alpha (Directive)</option>
        <option value="Beta">Beta (Production)</option>
        <option value="Delta">Delta (Audit)</option>
        <option value="Sigma">Sigma (Knowledge)</option>
        <option value="Omega">Omega (User)</option>
        <option value="Rho">Rho (Traffic)</option>
      </select>
      
      <select
        onChange={(e) => onFilterChange({ messageType: e.target.value })}
        className="border rounded px-3 py-2"
      >
        <option value="">All Message Types</option>
        <option value="assignment">Assignment</option>
        <option value="logicnode">LogicNode</option>
        <option value="verification">Verification</option>
        <option value="query">Query</option>
      </select>
    </div>
  )
}
```

---

## 5. PERFORMANCE METRICS PANEL

### 5.1 Real-Time Charts

**Chart.js Integration:**
```typescript
// MetricsChart.tsx
import { Line } from 'react-chartjs-2'

function MetricsChart() {
  const [metrics, setMetrics] = useState({
    labels: [],
    datasets: [
      {
        label: 'LogicNodes/min',
        data: [],
        borderColor: 'rgb(75, 192, 192)',
      },
      {
        label: 'CPU Usage %',
        data: [],
        borderColor: 'rgb(255, 99, 132)',
      }
    ]
  })
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const data = await fetchMetrics()
      setMetrics(prev => ({
        labels: [...prev.labels, new Date().toLocaleTimeString()].slice(-20),
        datasets: prev.datasets.map((ds, idx) => ({
          ...ds,
          data: [...ds.data, data[idx]].slice(-20)
        }))
      }))
    }, 1000)
    
    return () => clearInterval(interval)
  }, [])
  
  return <Line data={metrics} options={{ responsive: true }} />
}
```

---

### 5.2 Resource Usage Gauges

**Agent Workload Visualization:**
```typescript
// AgentWorkloadGauge.tsx
function AgentWorkloadGauge({ agents }) {
  return (
    <div className="grid grid-cols-5 gap-4">
      {agents.map(agent => (
        <div key={agent.id} className="text-center">
          <div className="relative w-24 h-24 mx-auto">
            <svg viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="#e5e7eb"
                strokeWidth="10"
              />
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="10"
                strokeDasharray={`${agent.workload * 2.51} 251`}
                transform="rotate(-90 50 50)"
              />
              <text
                x="50"
                y="55"
                textAnchor="middle"
                fontSize="20"
                fill="#1f2937"
              >
                {agent.workload}%
              </text>
            </svg>
          </div>
          <div className="text-sm mt-2">{agent.name}</div>
        </div>
      ))}
    </div>
  )
}
```

---

## 6. ALERT & NOTIFICATION SYSTEM

### 6.1 Alert Types

**System Alerts:**
```typescript
interface Alert {
  id: string
  type: 'error' | 'warning' | 'info' | 'success'
  title: string
  message: string
  timestamp: Date
  agent_id?: string
  mission_id?: string
  action_required: boolean
}

// Examples:
const alerts: Alert[] = [
  {
    id: '1',
    type: 'error',
    title: 'Audit Failed',
    message: 'Python Specialist LogicNode failed 127/1000 tests',
    timestamp: new Date(),
    agent_id: 'AGENT-PY-001',
    action_required: true
  },
  {
    id: '2',
    type: 'warning',
    title: 'High API Usage',
    message: 'API Broker reports 80% of rate limit consumed',
    timestamp: new Date(),
    agent_id: 'BROKER-001',
    action_required: false
  }
]
```

---

### 6.2 Alert Toast Component

**Toast Notifications:**
```typescript
// AlertToast.tsx
function AlertToast({ alert, onDismiss }) {
  const typeStyles = {
    error: 'bg-red-500',
    warning: 'bg-yellow-500',
    info: 'bg-blue-500',
    success: 'bg-green-500'
  }
  
  return (
    <div className={`${typeStyles[alert.type]} text-white p-4 rounded shadow-lg mb-2`}>
      <div className="flex justify-between items-start">
        <div>
          <div className="font-bold">{alert.title}</div>
          <div className="text-sm">{alert.message}</div>
        </div>
        <button onClick={() => onDismiss(alert.id)} className="text-white">
          ✕
        </button>
      </div>
      {alert.action_required && (
        <button className="mt-2 bg-white text-gray-900 px-3 py-1 rounded text-sm">
          View Details
        </button>
      )}
    </div>
  )
}
```

---

## 7. SETTINGS & CONFIGURATION

### 7.1 System Configuration UI

**Settings Panel:**
```typescript
// SettingsPanel.tsx
function SettingsPanel() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">System Configuration</h2>
      
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-3">API Key Management</h3>
        <table className="w-full">
          <thead>
            <tr className="border-b">
              <th className="text-left p-2">Provider</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Usage</th>
              <th className="text-left p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-2">Anthropic (Claude)</td>
              <td className="p-2">
                <span className="text-green-600">● Active</span>
              </td>
              <td className="p-2">47% of monthly limit</td>
              <td className="p-2">
                <button className="text-blue-600">Rotate Key</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div className="mb-6">
        <h3 className="text-lg font-semibold mb-3">Resource Allocation</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm mb-1">CPU Cores per Agent</label>
            <input type="number" defaultValue={2} className="border rounded px-3 py-2 w-full" />
          </div>
          <div>
            <label className="block text-sm mb-1">Memory Limit (GB)</label>
            <input type="number" defaultValue={4} className="border rounded px-3 py-2 w-full" />
          </div>
        </div>
      </div>
    </div>
  )
}
```

---

## 8. RESPONSIVE DESIGN

### 8.1 Breakpoints

```css
/* Mobile: 320px - 640px */
@media (max-width: 640px) {
  .agent-grid {
    grid-template-columns: 1fr;
  }
}

/* Tablet: 641px - 1024px */
@media (min-width: 641px) and (max-width: 1024px) {
  .agent-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Desktop: 1025px+ */
@media (min-width: 1025px) {
  .agent-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}
```

---

## 9. ACCESSIBILITY

### 9.1 WCAG 2.1 AA Compliance

**Keyboard Navigation:**
```typescript
// Keyboard shortcuts
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'd') {
      e.preventDefault()
      router.push('/dashboard')
    }
    if (e.ctrlKey && e.key === 'm') {
      e.preventDefault()
      router.push('/missions')
    }
    if (e.ctrlKey && e.key === 'a') {
      e.preventDefault()
      router.push('/agents')
    }
  }
  
  window.addEventListener('keydown', handleKeyPress)
  return () => window.removeEventListener('keydown', handleKeyPress)
}, [])
```

**Screen Reader Support:**
```typescript
// ARIA labels
<button
  aria-label="Pause mission execution"
  onClick={pauseMission}
>
  ⏸️
</button>

<div role="alert" aria-live="polite">
  {alert.message}
</div>
```

---

## 10. COMPLETION STATUS

✅ **Main Dashboard** - Real-time agent status grid  
✅ **Mission Timeline** - Visual workflow tracker  
✅ **LogicNode Explorer** - Interactive dependency graph  
✅ **Semantic Bus Monitor** - Live message stream  
✅ **Performance Metrics** - Resource usage charts  
✅ **Alert System** - Toast notifications  
✅ **Settings Panel** - System configuration  
✅ **Responsive Design** - Mobile/tablet/desktop  
✅ **Accessibility** - WCAG 2.1 AA compliant  

**Mission Control UI Specification is 100% complete.**

---

## DOCUMENT METADATA

**Document ID:** 15  
**Version:** 1.0  
**Created:** February 2026  
**Owner:** Frontend Team Lead  
**Related Documents:**
- Document 05: System Architecture
- Document 14: Workflow & Orchestration Design

---

*End of Mission Control UI Specification*
