⚗

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
HOLY GRAIL REFINERY
FRONTEND DESIGN SPECIFICATION
User Stories  ·  Pages  ·  UI/UX Components  ·  Interaction Design  ·  Wireframes
Version 1.0  |  March 2026  |  Local Windows Application — No Login Required
This document defines the complete frontend design for the Holy Grail Refinery running as a local Windows application on localhost:3000. All designs assume local machine execution with no authentication layer, no cloud dependency, and full access to all 35 agents and 5 databases.
1. APPLICATION OVERVIEW
The Holy Grail Refinery Mission Control is a desktop-grade web application served locally at http://localhost:3000 using Next.js 14. Because it runs entirely on the user's Windows machine, there is no login, no session management, and no authentication of any kind. The user opens the app and is immediately inside Mission Control — their personal software engineering firm, running on their hardware.
Property
Value
Application Type
Local web app (Next.js 14, served on localhost:3000)
Operating System
Windows 10/11 (AW1 development machine)
Authentication
NONE — local machine, single user, no login required
Primary Interface
Browser-based Mission Control dashboard
Real-time Updates
WebSocket connection to local Redis Semantic Bus
Theme
Dark mode default (SLATE #0F172A), light mode optional
Breakpoint
Desktop-primary (1440px+), min supported 1024px
Font Stack
Inter (UI) + JetBrains Mono (code/IDs)
Icon Library
Lucide React
Routing
Next.js App Router — 10 primary pages
1.1 The 9 Core Pages at a Glance
Route
Page Name
Primary Purpose
/
Home / Launch Pad
First screen. System health summary + quick launch New Mission
/chat
PM Agent Chat
Conversational interface — user talks to PM Agent via natural language
/missions
Mission Control Center
All missions — active, queued, completed, failed
/missions/[id]
Mission Detail
Live view of one mission: 7-phase timeline, agents, LogicNodes
/agents
Agent Status Grid
Real-time status of all 35 agents organized by tier and pod
/logicnodes
LogicNode Explorer
Browse, search, inspect all extracted LogicNodes
/semantic-bus
Semantic Bus Monitor
Live stream of all 6-protocol messages flowing through Redis
/databases
Database Health
Health and statistics for all 5 shared databases
/repo
GitHub Repository Import
Clone, inspect, and configure a GitHub repo as a mission source or live workspace
/settings
Settings
API key management, system configuration, theme
2. USER PERSONAS
Because HGR runs locally on a single Windows machine, all personas are the same physical user — Kevin, the developer/operator. However, the user occupies different mental modes depending on their goal. These modes drive the page design and information hierarchy.
Persona
Mental Model
Primary Pages
Frequency
🚀 The Mission Launcher
Operator Mode
I have code I want the Refinery to process. I need to describe my intent to the PM Agent, submit a mission, and then monitor it.
Chat, Missions, Mission Detail
Daily — the most common workflow
🔬 The System Inspector
Analysis Mode
I want to see what the agents are doing right now. I need granular real-time data about agent states, LogicNode quality, and bus traffic.
Agents, LogicNode Explorer, Semantic Bus
During active missions
🛠️ The Operator / SRE
DevOps Mode
Something went wrong. An agent is stuck, the bus is backing up, or a database is unhealthy. I need diagnostic data and control.
Database Health, Settings, Semantic Bus
When troubleshooting
📊 The Analyst
Research Mode
The mission is done. I want to understand what was extracted, review the LogicNodes, and verify the quality of the output.
LogicNode Explorer, Mission Detail
After mission completion
3. USER STORIES
Each story is written from the perspective of a user mode (persona). All stories apply to a single local user on Windows. Stories are organized by Epic.
EPIC 1: Mission Launch & Chat
The user communicates with the PM Agent in natural language to describe what they want built or analyzed, then submits and tracks a mission.
US-001  
[Mission Launch]
As a 
developer
, I want to 
open the app and see the system health immediately without any clicks
, so that I know at a glance whether my 35-agent system is healthy before starting work
Acceptance Criteria
Home page shows on http://localhost:3000 with zero setup or login
System health score (0-100) visible within 2 seconds of page load
Count of active, idle, and error agents shown as colored numbers
Any critical alerts shown as red banners at top of page
Quick-launch 'New Mission' button is the most prominent element
Priority: 
Critical   
Effort: 
S
US-002  
[Mission Launch]
As a 
developer
, I want to 
describe what I want in plain English and have the PM Agent understand me
, so that I don't need to learn any special syntax or command language to start a mission
Acceptance Criteria
Chat interface at /chat auto-focuses the message input on load
Typing and pressing Enter (or clicking Send) submits the message
PM Agent responds within 3 seconds with acknowledgment or clarifying question
Agent typing indicator (animated dots) shows while PM Agent is thinking
Conversation history persists for the current session
Priority: 
Critical   
Effort: 
M
US-003  
[Mission Launch]
As a 
developer
, I want to 
upload one or more source code files for the PM Agent to analyze
, so that I can give the system real code, not just text descriptions
Acceptance Criteria
Drag-and-drop zone visible in chat interface
File picker button available as fallback
Accepted formats shown: .py .js .ts .java .c .cpp .rs .go .rb .php .cs .scala .r .m
Uploaded files shown as chips in the chat input area with file name and size
PM Agent acknowledges file receipt and states detected language(s)
Priority: 
High   
Effort: 
M
US-004  
[Mission Launch]
As a 
developer
, I want to 
see the PM Agent convert my description into a structured Feature Contract before the mission begins
, so that I can verify the system understood my intent correctly before investing compute time
Acceptance Criteria
PM Agent displays the Feature Contract as a structured card in the chat
Contract shows: Mission Title, Languages, Scope, Estimated Duration
User can click 'Confirm & Start' or 'Edit' before mission launches
Editing opens an inline form with the contract fields pre-filled
Confirmed contract generates a Mission ID (e.g. mission-a4f7b2) visible in chat
Priority: 
High   
Effort: 
L
US-005  
[Mission Launch]
As a 
developer
, I want to 
submit the mission and be taken to the live Mission Detail view automatically
, so that I can immediately start watching the mission progress without navigating manually
Acceptance Criteria
Clicking 'Confirm & Start' shows a brief 'Launching...' animation (500ms)
User is automatically redirected to /missions/[id] for the new mission
Mission detail shows Phase 1 (INTAKE) as active immediately
Estimated completion time is shown at the top of the mission detail
Browser tab title updates to 'Mission m-4f7b2 — Processing'
Priority: 
Critical   
Effort: 
M
EPIC 2: Mission Monitoring
US-006  
[Mission Monitoring]
As a 
developer
, I want to 
see all 7 phases of the Smelt-Cycle update in real time on the Mission Detail page
, so that I can track exactly where in the pipeline my mission is without refreshing
Acceptance Criteria
All 7 phases shown as a horizontal stepper: INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY
Active phase has animated pulse effect and progress percentage
Completed phases show a green checkmark and elapsed time
Queued phases are shown in gray with no animation
Phase updates via WebSocket — no manual refresh needed
Priority: 
Critical   
Effort: 
L
US-007  
[Mission Monitoring]
As a 
developer
, I want to 
see which specific agents are currently active on my mission
, so that I understand which part of the 35-agent system is doing work right now
Acceptance Criteria
Active agents list shown on the Mission Detail sidebar
Each active agent card shows: Agent ID, current task description, elapsed time
Agents are color-coded by pod (Orange=Pod A, Steel=Pod B, Navy=Pod C, Teal=Pod D)
Clicking an agent card opens a log drawer for that agent
Idle agents are shown in the global Agents page but not in the mission sidebar
Priority: 
High   
Effort: 
M
US-008  
[Mission Monitoring]
As a 
developer
, I want to 
see a live count of LogicNodes being extracted as the mission processes
, so that I can see tangible output accumulating in real time and know the mission is progressing
Acceptance Criteria
LogicNode counter visible in mission header: 'Extracted: 47 LogicNodes'
Counter increments in real time as specialists report new nodes
Clicking the counter navigates to the LogicNode Explorer filtered to this mission
Confidence score average shown alongside count: 'Avg Confidence: 94.2%'
Audit pass rate shown: 'Verified: 43/47 (91.5%)'
Priority: 
High   
Effort: 
M
US-009  
[Mission Monitoring]
As a 
developer
, I want to 
pause or cancel a running mission
, so that I have control over the system and can stop runaway or incorrect missions
Acceptance Criteria
'Pause' and 'Cancel' buttons visible in the Mission Detail header
Clicking 'Pause' shows confirmation dialog: 'Pause mission? Agents will finish current tasks then wait.'
Confirmed pause sets mission status to PAUSED within 10 seconds
Clicking 'Cancel' shows warning dialog with red border: 'Cancel mission? Partial LogicNodes will be discarded.'
Cancelled missions appear in mission list with red CANCELLED badge
Priority: 
High   
Effort: 
M
EPIC 3: Agent Visibility
US-010  
[Agent Visibility]
As a 
developer
, I want to 
see all 35 agents at once, organized by tier and pod, with live status
, so that I have a complete mental model of my system's current state without clicking through multiple pages
Acceptance Criteria
Agents page at /agents shows all 35 agents in a structured grid
Organized visually: Executive Tier (top) → Support Ring → Pod A → Pod B → Pod C → Pod D
Each agent card shows: name, ID, status badge (ACTIVE/IDLE/ERROR/PAUSED), current task
Status updates via WebSocket every 2 seconds
Clicking any agent card opens Agent Detail drawer from the right
Priority: 
Critical   
Effort: 
L
US-011  
[Agent Visibility]
As a 
developer
, I want to 
filter the agent grid to see only agents in a specific pod or status
, so that I can narrow focus when I only care about one part of the system
Acceptance Criteria
Filter bar at top of Agents page with: [All Pods] [Pod A] [Pod B] [Pod C] [Pod D] toggle buttons
Status filter: [All] [Active] [Idle] [Error] [Paused]
Filters combine — e.g. 'Pod A + Error' shows only errored Pod A agents
Filter state preserved in URL: /agents?pod=a&status=error
Agent count shown for current filter: 'Showing 6 of 35 agents'
Priority: 
Medium   
Effort: 
S
US-012  
[Agent Visibility]
As a 
developer
, I want to 
click an agent and see its recent logs in a side drawer without leaving the page
, so that I can diagnose an agent's state quickly without losing my overview of the grid
Acceptance Criteria
Clicking any agent card opens a slide-in drawer from the right (400px wide)
Drawer shows: Agent ID, tier, pod, current status, current mission ID if applicable
Live log stream — new log entries appear at bottom with auto-scroll
Log level filter tabs: [All] [INFO] [WARNING] [ERROR]
Drawer has 'Open Full Logs' link that goes to a dedicated agent log page
Pressing Escape or clicking backdrop closes the drawer
Priority: 
High   
Effort: 
M
EPIC 4: LogicNode Exploration
US-013  
[LogicNode Exploration]
As a 
developer
, I want to 
browse all extracted LogicNodes across all missions in a searchable table
, so that I can understand the full body of extracted logic the system has produced
Acceptance Criteria
LogicNode Explorer at /logicnodes shows all nodes in a paginated table
Columns: Node ID, Concept, Language, Confidence %, Mission ID, Status, Created
Search bar filters by concept name or node ID in real time
Filter by language, pod, confidence range, and verification status
Table is sortable by all columns
Clicking a row opens the LogicNode Detail drawer
Priority: 
High   
Effort: 
M
US-014  
[LogicNode Exploration]
As a 
developer
, I want to 
inspect a single LogicNode's full structure including its Refined-IR JSON
, so that I can verify the quality of extraction and understand exactly what the agent captured
Acceptance Criteria
LogicNode drawer shows: concept, intent, inputs/outputs, pre/postconditions
Full Refined-IR JSON shown in a syntax-highlighted code block
Confidence score shown as a colored progress ring (green ≥ 90%, amber 70-89%, red < 70%)
Audit history shown: test cases run, pass rate, timestamp
Source code snippet shown that generated this node
'Copy JSON' button copies the full Refined-IR to clipboard
Priority: 
Medium   
Effort: 
M
EPIC 5: System Diagnostics
US-015  
[System Diagnostics]
As a 
developer
, I want to 
see the live stream of all messages on the Semantic Bus
, so that I can debug agent communication issues and verify protocols are working correctly
Acceptance Criteria
Semantic Bus Monitor at /semantic-bus shows a live scrolling message log
Each message row shows: timestamp, protocol (Alpha/Beta/Delta/Sigma/Omega/Rho), from-agent, to-agent, message type
Protocol is shown as a color-coded badge matching protocol colors
Message rate shown: 'X messages/second' updating every second
Filter by protocol, agent, or message type
Clicking a message row shows the full JSON payload in an expandable panel
Pause/Resume button to freeze the stream for inspection
Priority: 
High   
Effort: 
L
US-016  
[System Diagnostics]
As a 
developer
, I want to 
see the health status of all 5 databases at a glance
, so that I know immediately if a database is down or degraded before it affects a mission
Acceptance Criteria
Database Health page at /databases shows cards for all 5 databases
Each card shows: database name, status indicator (green/amber/red), connection count, size used, last write time
Clicking a card expands to show top queries, slow query count, and replication lag
Auto-refreshes every 10 seconds
Red card for any database triggers a system-wide alert banner
History chart shows uptime % over last 24 hours
Priority: 
High   
Effort: 
M
US-017  
[System Diagnostics]
As a 
developer
, I want to 
configure my API keys for all LLM providers through the Settings page
, so that I can rotate, add, or update API keys without editing environment files manually
Acceptance Criteria
Settings page at /settings shows a table of all 35 agent API key slots
Each row: Agent ID, Provider (Gemini/Anthropic/OpenAI), key status (Set/Missing/Expired), last rotated date
Clicking 'Edit' on a row opens an inline input to paste a new key (masked)
Saving triggers a validation call to the provider — shows ✅ Valid or ❌ Invalid immediately
Bulk 'Rotate All' button triggers rotation workflow with confirmation dialog
Keys stored in encrypted vault — never shown in plaintext after initial save
Priority: 
Medium   
Effort: 
L
EPIC 6: GitHub Repository Import & Live Editing
The user connects a real GitHub repository — either their own or a public one — clones it into the local Refinery workspace, runs the full Smelt-Cycle on it, and then interacts with the PM Agent to request changes, updates, new features, or refactors that are applied directly to the repo's files and pushed back as commits.
US-018  
[GitHub Import]
As a 
developer
, I want to 
paste a GitHub repo URL and have the Refinery clone it locally without leaving the app
, so that I don't need to manually git clone anything — the system handles ingestion automatically
Acceptance Criteria
Repo Import page at /repo shows a URL input field as the primary element
User pastes any GitHub URL (public or private) — e.g. https://github.com/user/project
Optional: Branch selector dropdown appears after URL validation (defaults to main/master)
Optional: Subdirectory path input to target a specific folder within the repo
Clicking 'Import Repository' triggers a clone to local /workspace/repos/ directory
Progress bar shows clone progress (streaming git output: 'Cloning... 43%')
On completion, repo appears in the workspace file tree panel
Priority: 
Critical   
Effort: 
L
US-019  
[GitHub Import]
As a 
developer
, I want to 
see a file tree of the cloned repo and select which files or folders to include in the mission
, so that I have control over exactly what code the Refinery will process — I don't have to feed it the whole repo
Acceptance Criteria
After clone, a collapsible file tree renders the repo directory structure
All files are unchecked by default — user selects what to include
Checkbox on each file/folder — checking a folder selects all children
Language detection runs automatically — each file shows a language icon badge
File count and estimated LOC (lines of code) updates as selections change
Filter bar: show only [All Files] [Python] [JavaScript] [Rust] etc. based on detected languages
Summary bar at bottom: 'Selected: 23 files · 4,821 lines · Est. mission time: ~12 min'
Priority: 
Critical   
Effort: 
L
US-020  
[GitHub Import]
As a 
developer
, I want to 
choose a mission type for the imported repo — Analyze, Update, Add Feature, or Refactor
, so that I can tell the Refinery exactly what kind of work to do on the code, not just run a generic analysis
Acceptance Criteria
After file selection, a Mission Type panel appears with 4 large icon-cards
' Analyze' — understand the codebase, extract LogicNodes, produce quality report
' Update' — modernize dependencies, fix deprecations, upgrade patterns
'✨ Add Feature' — describe a new feature in natural language, agents implement it
'♻️ Refactor' — improve code quality, performance, or cross-language consistency
Selecting a type opens a context-appropriate description field below
For 'Add Feature' and 'Update': a chat input appears to describe the requested change in plain English
For 'Analyze' and 'Refactor': optional focus areas can be entered (e.g. 'focus on async patterns')
Priority: 
Critical   
Effort: 
M
US-021  
[GitHub Import]
As a 
developer
, I want to 
monitor the agents working on my repo files in real time, seeing which files are being processed
, so that I can follow along as the 35-agent factory works through my actual codebase
Acceptance Criteria
Mission Detail page for a repo mission shows the file tree with live status overlays
Files being actively processed by an agent show an animated orange pulse indicator
Completed files show a green checkmark with extracted LogicNode count
Failed files show a red X with error reason on hover
Agent sidebar shows which specialist is on which file: 'PY-001 → scraper.py (line 142)'
Overall repo progress: 'Processing file 18 of 23 selected'
Estimated remaining time recalculates dynamically based on actual processing rate
Priority: 
High   
Effort: 
M
US-022  
[GitHub Import]
As a 
developer
, I want to 
see a diff of proposed changes before they are written to disk
, so that I can review what the agents want to change and approve or reject specific edits before they touch my files
Acceptance Criteria
After agents complete their work, a 'Review Changes' panel appears in Mission Detail
Changes are shown as a standard unified diff (green = additions, red = removals)
Each changed file is listed with: filename, lines changed, a collapsible diff view
Individual changes can be unchecked to exclude them from the final commit
A summary shows: 'X files changed · Y insertions · Z deletions'
Two action buttons: 'Apply Selected Changes' (primary, violet) and 'Discard All' (ghost, red)
Changes are NOT written to disk until the user explicitly clicks 'Apply Selected Changes'
Priority: 
Critical   
Effort: 
L
US-023  
[GitHub Import]
As a 
developer
, I want to 
have approved changes written back to the repo files and committed to git automatically
, so that The output of the mission is real code changes in my actual repo, not just a report
Acceptance Criteria
After 'Apply Selected Changes', files are written to disk in /workspace/repos/[repo-name]/
A git commit is created automatically with a structured message: 'HGR: [mission type] - [mission title]'
Commit message body includes: mission ID, LogicNodes modified, agent IDs that contributed
User can optionally edit the commit message before the commit is made
Commit appears in a 'Recent Commits' panel with hash, timestamp, and files changed
Option to push to remote: 'Push to origin/main' button (requires GitHub token in Settings)
If push is not configured, instructions shown: 'Run: git push from /workspace/repos/[repo]'
Priority: 
Critical   
Effort: 
L
US-024  
[GitHub Import]
As a 
developer
, I want to 
have a conversation with the PM Agent to request follow-up changes to the same repo without re-importing
, so that I can iterate on my codebase through natural language — like pairing with a team of engineers
Acceptance Criteria
After a repo mission completes, the chat interface persists with full repo context loaded
User can type follow-up requests: 'Now add unit tests for the scraper functions you just refactored'
PM Agent references the existing LogicNodes from the previous mission — no re-extraction needed
New mission launches with: same repo files, same context, incremental changes only
Chat shows a 'Repo Context' banner: '📁 my-project @ main (last updated 3 minutes ago)'
Each conversation turn can spawn a new focused sub-mission targeting specific files
Full conversation history with all repo missions is accessible in the Mission list with a 📁 icon
Priority: 
High   
Effort: 
L
US-025  
[GitHub Import]
As a 
developer
, I want to 
connect a private GitHub repository using a Personal Access Token stored securely in Settings
, so that I can use the Refinery on my private work repos, not just public ones
Acceptance Criteria
Settings > API Keys tab has a 'GitHub Tokens' section separate from LLM keys
User pastes a GitHub PAT (Personal Access Token) with repo scope
Token is validated immediately: green ✅ if clone access confirmed, red ❌ if not
Token is stored in the encrypted vault — never shown in plaintext after initial save
Private repos can then be entered in the /repo URL field just like public repos
Token is scoped — only used for git operations, never sent to LLM providers
Token expiry date shown in Settings if detectable from GitHub API response
Priority: 
High   
Effort: 
M
4. PAGE WIREFRAMES & LAYOUT SPECS
The following section documents every page's layout, zones, and component inventory. All pages share the same global chrome (topbar + sidebar). Wireframes use ASCII art at 1440px desktop width.
4.0 Global Application Shell
╔═══════════════════════════════════════════════════════════════════════════╗
║  TOPBAR  [h:64px, sticky, bg:#1E293B, border-bottom: 1px #334155]        ║
║  ⚗ Holy Grail Refinery     [Divider]  [●] System: 100%  [●] 35 Agents   ║
║                                        [Amber ●] if degraded             ║
╠═══════════╦═══════════════════════════════════════════════════════════════╣
║ SIDEBAR   ║  MAIN CONTENT AREA (flex-1, overflow-y auto)                 ║
║ [w:240px] ║                                                               ║
║ sticky    ║  PAGE HEADER [h:72px, bg:#0F172A]                             ║
║ bg:#1E293B║  Page Title                    [Action Buttons]              ║
║           ║  Breadcrumb or subtitle                                       ║
║ ▣  Home   ║ ─────────────────────────────────────────────────────────── ║
║ ◉  Chat   ║                                                               ║
║ ◎  Missions║  PRIMARY PAGE CONTENT                                       ║
║ ◎  Agents ║  (scrollable, padding: 24px)                                 ║
║ ◎  Nodes  ║                                                               ║
║ ◎  Bus    ║                                                               ║
║ ◎  DBs    ║                                                               ║
║ ◎  Repo   ║                                                               ║
║ ─────     ║                                                               ║
║ ◎  Settings║                                                              ║
║           ║                                                               ║
╠═══════════╩═══════════════════════════════════════════════════════════════╣
║  STATUS BAR [h:32px, bg:#0F172A, border-top: 1px #334155]                ║
║  ● Redis Connected  |  ● DB Healthy  |  WS: Connected  |  v1.0.0         ║
╚═══════════════════════════════════════════════════════════════════════════╝
Zone
Height/Width
Background
Content
Topbar
64px, 100% width
#1E293B
Logo left. System health indicators right. Always visible.
Sidebar
240px, full height
#1E293B
Nav items with icons. Active item has violet left border + violet text.
Page Header
72px, content width
#0F172A
Page title (H1). Breadcrumb subtitle. Primary actions right-aligned.
Content
flex-1, scrollable
#0F172A
24px padding on all sides. Max-width 1600px, centered.
Status Bar
32px, 100% width
#0F172A
System connection status. WS state. App version. Never hidden.
4.1 Home / Launch Pad  [ / ]
The first page the user sees. No clicks required. Designed to answer: 'Is my system healthy?' and 'What should I work on next?' in under 3 seconds.
╔══════════════════════════════════════════════════════════════════════════╗
║  HOME — LAUNCH PAD                                                       ║
╠══════════════════╦═══════════════════════════════════════════════════════╣
║  SYSTEM HEALTH   ║  QUICK LAUNCH                                         ║
║  ┌────────────┐  ║  ┌────────────────────────────────────────────────┐  ║
║  │ SYSTEM: 98%│  ║  │  + NEW MISSION  [large violet CTA button]      │  ║
║  │ ● ● ● ● ●  │  ║  │    Describe your goal to the PM Agent →        │  ║
║  │ 33 Healthy │  ║  └────────────────────────────────────────────────┘  ║
║  │  2 Idle    │  ║                                                        ║
║  │  0 Error   │  ║  RECENT MISSIONS                                      ║
║  └────────────┘  ║  ┌────────────────────────────────────────────────┐  ║
║                  ║  │ m-4f7b2  Analyze scraper.py    COMPLETE  8m ago│  ║
║  DB HEALTH       ║  │ m-9a3c1  Build REST API        RUNNING   now   │  ║
║  ┌────────────┐  ║  │ m-2e8d4  Cross-lang compare    QUEUED    —     │  ║
║  │ Knowledge  ●  ║  └────────────────────────────────────────────────┘  ║
║  │ State Graph●  ║                                                        ║
║  │ LogicNodes ●  ║  SYSTEM ACTIVITY                                      ║
║  │ Traceability● ║  ┌────────────────────────────────────────────────┐  ║
║  │ Model Store ● ║  │  Missions Today: 7  |  LogicNodes: 312  |       │  ║
║  └────────────┘  ║  │  Avg Completion: 6.2min | Success Rate: 97%    │  ║
╚══════════════════╩══╧════════════════════════════════════════════════════╝
Home Page — Component Inventory
Component
Location
Data Source
Update Frequency
System Health Ring
Left panel, top
WebSocket: /ws/system-health
Every 5s
Agent Status Counters
Left panel, middle
WebSocket: /ws/agents
Every 2s
Database Health List
Left panel, bottom
REST: GET /api/databases/health
Every 10s
New Mission CTA Button
Right panel, top
Navigate to /chat
Static
Recent Missions List
Right panel, middle
REST: GET /api/missions?limit=5
Every 30s
System Activity Stats
Right panel, bottom
REST: GET /api/stats/today
Every 60s
4.2 PM Agent Chat  [ /chat ]
The primary mission entry point. A conversational interface that feels like a smart chat app, not a command line. The PM Agent lives here.
╔═══════════════════════════════════════════════════════════════════════╗
║  CHAT — PM AGENT                              [New Chat] [History ▼] ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  ┌─── CHAT HISTORY PANEL (flex-1, overflow-y: auto) ───────────────┐  ║
║  │                                                                   │  ║
║  │  [Welcome card on empty state]                                    │  ║
║  │  ┌──────────────────────────────────────────────────────────┐    │  ║
║  │  │ ⚗ PM Agent · Just now                                    │    │  ║
║  │  │ Hello! I'm your PM Agent. Tell me what you want to build │    │  ║
║  │  │ or analyze. You can also drag and drop code files here.  │    │  ║
║  │  └──────────────────────────────────────────────────────────┘    │  ║
║  │                                                                   │  ║
║  │                    ┌───────────────────────────────────────┐     │  ║
║  │  [User] 2:34pm     │ Analyze my Python web scraper for     │     │  ║
║  │                    │ performance issues   [scraper.py × 1] │     │  ║
║  │                    └───────────────────────────────────────┘     │  ║
║  │                                                                   │  ║
║  │  ⚗ PM Agent · 2:34pm                                             │  ║
║  │  ┌── FEATURE CONTRACT CARD ──────────────────────────────────┐   │  ║
║  │  │  Mission: Python Web Scraper Performance Analysis          │   │  ║
║  │  │  Language: Python (detected)                               │   │  ║
║  │  │  Scope: Performance audit, optimization recommendations     │   │  ║
║  │  │  Files: scraper.py (500 lines)                             │   │  ║
║  │  │  Est. Time: ~8 minutes                                     │   │  ║
║  │  │  ─────────────────────────────────────────────────────     │   │  ║
║  │  │  [✓ Confirm & Launch Mission]   [✎ Edit Contract]         │   │  ║
║  │  └───────────────────────────────────────────────────────────┘   │  ║
║  │                                                                   │  ║
║  │  ⚗ PM Agent · 2:35pm    [● ● ●] (typing indicator)             │  ║
║  │                                                                   │  ║
║  └───────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  ┌── DRAG & DROP ZONE (active when files dragged) ─────────────────┐  ║
║  │  Drop code files here to attach                                  │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
║  ┌── MESSAGE INPUT ─────────────────────────────────────────────────┐  ║
║  │  [📎] Describe what you want...                    [Send ↵]     │  ║
║  └──────────────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════════╝
Chat Page — Interaction Specs
Interaction
Trigger
Behavior
Send message
Enter key or Send button
POST to /api/chat, optimistic UI update, WS listener for PM response
Attach file
📎 button or drag & drop
File picker or drop zone. File shown as chip. Uploaded to /api/files/upload
Confirm mission
'Confirm & Launch Mission' button
POST /api/missions/create, redirect to /missions/[id] with 500ms transition
Edit contract
'Edit Contract' button
Contract card switches to editable form mode inline
New chat session
'New Chat' button
Clears history in UI, starts fresh session — previous sessions accessible via History
Typing indicator
PM Agent responds
Three pulsing dots animation for 1-30 seconds while PM Agent generates response
Mission launched toast
After confirmation
Green toast notification: '✅ Mission m-4f7b2 launched — viewing live' with link
4.3 Mission Control Center  [ /missions ]
The command center for all missions. The user can see everything running, queued, completed, or failed, and filter/search across all missions.
╔════════════════════════════════════════════════════════════════════════╗
║  MISSIONS   [All] [Running 2] [Queued 1] [Complete 12] [Failed 0]     ║
║                                    [🔍 Search missions...] [+ New]    ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                         ║
║  RUNNING ──────────────────────────────────────────────────────────    ║
║  ┌────────────────────────────────────────────────────────────────┐   ║
║  │ m-9a3c1  Build REST API   [████████░░░] 78%   Phase: SMELT     │   ║
║  │ Started: 5m ago | Agents: 8 active | LogicNodes: 31            │   ║
║  │ [View Live] [Pause] [Cancel]                                    │   ║
║  ├────────────────────────────────────────────────────────────────┤   ║
║  │ m-1d5e9  Cross-lang compare  [████░░░░░░] 43%   Phase: SMELT   │   ║
║  │ Started: 2m ago | Agents: 12 active | LogicNodes: 18           │   ║
║  │ [View Live] [Pause] [Cancel]                                    │   ║
║  └────────────────────────────────────────────────────────────────┘   ║
║                                                                         ║
║  QUEUED ────────────────────────────────────────────────────────────   ║
║  ┌────────────────────────────────────────────────────────────────┐   ║
║  │ m-2e8d4  Optimize COBOL legacy   [QUEUED]   Est. start: 3min   │   ║
║  │ [View] [Cancel]                                                 │   ║
║  └────────────────────────────────────────────────────────────────┘   ║
║                                                                         ║
║  COMPLETED (last 24h) ──────────────────────────────────────────────   ║
║  m-4f7b2   Analyze scraper.py        ✅ SUCCESS  8m    47 nodes    ▶  ║
║  m-0b3a7   Build FastAPI todo app    ✅ SUCCESS  12m   89 nodes    ▶  ║
║  m-7c2f1   Java→Rust comparison      ✅ SUCCESS  15m   134 nodes   ▶  ║
╚════════════════════════════════════════════════════════════════════════╝
4.4 Mission Detail  [ /missions/[id] ]
The live view of a single mission. This is where the user spends the most time during active missions — it's the cockpit for a running Smelt-Cycle.
╔═══════════════════════════════════════════════════════════════════════════╗
║  ← Missions  /  m-9a3c1 — Build REST API                [Pause] [Cancel]║
║  Status: RUNNING  |  Phase: SMELT  |  Started: 5m ago  |  Est: 7m left   ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  SMELT-CYCLE PHASE STEPPER                                                ║
║  [✓INTAKE]──[✓FETCH]──[●SMELT 78%]──[○GATING]──[○FUSION]──[○SQUEEZE]──[○DELIVERY]║
╠══════════════════════════════════════╦════════════════════════════════════╣
║  MAIN AREA (flex-1)                  ║  SIDEBAR (w:320px)                ║
║                                       ║                                   ║
║  LOGICNODE EXTRACTION PROGRESS        ║  ACTIVE AGENTS                    ║
║  ┌──────────────────────────────┐    ║  ┌────────────────────────────┐  ║
║  │ Extracted:  31 LogicNodes    │    ║  │ PY-001 [Pod A ●] Mining... │  ║
║  │ Verified:   28 (90.3%)       │    ║  │   scraper.py:142-197   4s  │  ║
║  │ Avg Conf.:  93.7%            │    ║  ├────────────────────────────┤  ║
║  │ ████████████████████░░░      │    ║  │ JS-001 [Pod A ●] Mining... │  ║
║  └──────────────────────────────┘    ║  │   api.js:89-204        8s  │  ║
║                                       ║  ├────────────────────────────┤  ║
║  RECENT LOGICNODES                    ║  │ CEO [Exec ●] Monitoring    │  ║
║  ┌──────────────────────────────┐    ║  │   Fusion queue: 28 nodes   │  ║
║  │ #LN-031 filter_collection ✅ │    ║  ├────────────────────────────┤  ║
║  │ #LN-030 async_http_fetch  ✅ │    ║  │ AUDIT-A [●] Verifying...   │  ║
║  │ #LN-029 parse_json_stream ⏳ │    ║  │   LN-029: test 847/1000    │  ║
║  │ #LN-028 retry_with_backoff✅ │    ║  └────────────────────────────┘  ║
║  │ [View All in Explorer →]      │    ║                                   ║
║  └──────────────────────────────┘    ║  MISSION LOG (live scroll)         ║
║                                       ║  ┌────────────────────────────┐  ║
║  SEMANTIC BUS ACTIVITY (this mission) ║  │ 14:35:01 CEO→PodA: assign  │  ║
║  ┌──────────────────────────────┐    ║  │ 14:35:02 PY→Audit: LN-031  │  ║
║  │ [Alpha] CEO→PodA: assign    ⏱│    ║  │ 14:35:03 Audit→PY: PASS    │  ║
║  │ [Beta]  PY→Audit: LN-031   ⏱│    ║  │ 14:35:04 IS→PY: docs chunk  │  ║
║  │ [Delta] Audit→PY: VERIFIED ⏱│    ║  └────────────────────────────┘  ║
║  └──────────────────────────────┘    ║                                   ║
╚══════════════════════════════════════╩═══════════════════════════════════╝
4.5 Agent Status Grid  [ /agents ]
A real-time surveillance panel for all 35 agents. The user can see at a glance what the entire system is doing.
╔═══════════════════════════════════════════════════════════════════════════╗
║  AGENTS (35 total)  [All Pods▼] [All Status▼]   [🔍 Search agent...]    ║
║  ● 8 Active  ● 27 Idle  ● 0 Error                                        ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  EXECUTIVE TIER ──────────────────────────────────────────────────────   ║
║  ┌──────────────────────┐  ┌──────────────────────────────┐             ║
║  │ ⚗ PM-001             │  │ 👑 CEO-001                   │             ║
║  │ Program Manager      │  │ Grand Manager                │             ║
║  │ [● IDLE]             │  │ [● MONITORING]               │             ║
║  │ Awaiting user input  │  │ Mission m-9a3c1 active       │             ║
║  └──────────────────────┘  └──────────────────────────────┘             ║
║                                                                           ║
║  SUPPORT RING ─────────────────────────────────────────────────────────  ║
║  [IS:INDEXING] [Broker:ACTIVE] [Acct:IDLE] [Security:SCAN] [Comp:IDLE]  ║
║  [Diplomat:IDLE] [SRE:ACTIVE] [Data:IDLE] [DevOps:IDLE]                  ║
║                                                                           ║
║  POD A — DYNAMIC ─ [Orange]────────────────────────────────────────────  ║
║  [Mgr-A:CONSOLIDATING] [Audit-A:VERIFYING] [PY:MINING] [JS:IDLE]        ║
║  [TS:MINING] [RUBY:IDLE] [PHP:IDLE] [GO:IDLE]                            ║
║                                                                           ║
║  POD B — SYSTEMS ─ [Steel]──────────────────────────────────────────────  ║
║  [Mgr-B:IDLE] [Audit-B:IDLE] [C:IDLE] [CPP:IDLE] [RUST:IDLE] [ZIG:IDLE]║
║                                                                           ║
║  POD C — ENTERPRISE ─ [Navy]────────────────────────────────────────────  ║
║  [Mgr-C:IDLE] [Audit-C:IDLE] [JAVA:IDLE] [CS:IDLE] [SCALA:IDLE]         ║
║                                                                           ║
║  POD D — MATHEMATICAL ─ [Teal]─────────────────────────────────────────  ║
║  [Mgr-D:IDLE] [Audit-D:IDLE] [R:IDLE] [MATLAB:IDLE] [JULIA:IDLE]        ║
╚═══════════════════════════════════════════════════════════════════════════╝
4.6 LogicNode Explorer  [ /logicnodes ]
╔════════════════════════════════════════════════════════════════════════╗
║  LOGICNODE EXPLORER   Total: 1,247 nodes  [🔍 Search concept/ID...]  ║
║  [All Languages▼] [All Pods▼] [All Status▼] [Confidence: ≥90%]       ║
╠════════════════════════════════════════════════════════════════════════╣
║  Node ID      │ Concept             │ Lang  │ Conf │ Mission  │ Status ║
║ ──────────────┼─────────────────────┼───────┼──────┼──────────┼──────  ║
║  LN-001031   │ filter_collection    │ 🐍 PY │ 97%  │ m-4f7b2  │ ✅     ║
║  LN-001030   │ async_http_fetch     │ 🐍 PY │ 94%  │ m-4f7b2  │ ✅     ║
║  LN-001029   │ parse_json_stream    │ 🐍 PY │ 88%  │ m-4f7b2  │ ⏳     ║
║  LN-001028   │ retry_with_backoff   │ 🐍 PY │ 96%  │ m-4f7b2  │ ✅     ║
║  LN-001027   │ connection_pool      │ 🦀 RS │ 92%  │ m-7c2f1  │ ✅     ║
║  LN-001026   │ atomic_counter       │ 🦀 RS │ 99%  │ m-7c2f1  │ ✅     ║
║  ...                                                                    ║
║  [← Prev]   Page 1 of 25   [Next →]          Showing 50 per page       ║
╠════════════════════════════════════════════════════════════════════════╣
║  LOGICNODE DETAIL DRAWER (slides in from right, 480px)                 ║
║  ┌──────────────────────────────────────────────────────────────┐     ║
║  │ LN-001031  filter_collection                       [×]       │     ║
║  │ Language: Python  |  Mission: m-4f7b2  |  Confidence: ◉ 97% │     ║
║  │ ─────────────────────────────────────────────────────────    │     ║
║  │ REFINED-IR JSON:                                              │     ║
║  │ { 'concept': 'filter_collection', 'intent': '...',            │     ║
║  │   'inputs': [...], 'outputs': [...],                          │     ║
║  │   'postconditions': [...] }                                   │     ║
║  │ ─────────────────────────────────────────────────────────    │     ║
║  │ AUDIT:  1000/1000 tests passed  |  Duration: 2.3s            │     ║
║  │ SOURCE: scraper.py lines 142-197                              │     ║
║  │ [Copy JSON]  [View Source]  [View Mission]                    │     ║
║  └──────────────────────────────────────────────────────────────┘     ║
╚════════════════════════════════════════════════════════════════════════╝
4.7 Semantic Bus Monitor  [ /semantic-bus ]
╔═══════════════════════════════════════════════════════════════════════╗
║  SEMANTIC BUS MONITOR     Rate: 47 msg/s  [●LIVE]  [⏸ Pause] [Clear]║
║  [All Protocols▼] [All Agents▼] [All Types▼]                         ║
╠═══════════════════════════════════════════════════════════════════════╣
║  PROTOCOL THROUGHPUT (last 60s)                                        ║
║  Alpha [Directive] ████████████████░░  23 msg/s                        ║
║  Beta  [Production]████████░░░░░░░░░░  11 msg/s                        ║
║  Delta [Audit]     █████░░░░░░░░░░░░░   7 msg/s                        ║
║  Sigma [Knowledge] ███░░░░░░░░░░░░░░░   4 msg/s                        ║
║  Omega [User]      █░░░░░░░░░░░░░░░░░   1 msg/s                        ║
║  Rho   [Traffic]   █░░░░░░░░░░░░░░░░░   1 msg/s                        ║
╠═══════════════════════════════════════════════════════════════════════╣
║  LIVE MESSAGE STREAM                                                   ║
║  Time       │ Protocol    │ From         │ To           │ Type          ║
║ ────────────┼─────────────┼──────────────┼──────────────┼────────────  ║
║  14:35:04   │ [Sigma]     │ IS-001       │ PY-001       │ docs_chunk    ║
║  14:35:03   │ [Delta]     │ AUDIT-A      │ PY-001       │ VERIFIED      ║
║  14:35:02   │ [Beta]      │ PY-001       │ AUDIT-A      │ logicnode     ║
║  14:35:01   │ [Alpha]     │ CEO-001      │ MGR-A        │ task_assign   ║
║  14:35:00   │ [Alpha]     │ CEO-001      │ MGR-B        │ task_assign   ║
║  14:34:59   │ [Rho]       │ BROKER       │ PY-001       │ api_key       ║
║  ▼ (new messages appear here when live)                                ║
║                                                                         ║
║  ┌── EXPANDED MESSAGE PAYLOAD (on row click) ───────────────────────┐ ║
║  │  { 'protocol': 'beta', 'from': 'PY-001', 'to': 'AUDIT-A',       │ ║
║  │    'type': 'logicnode', 'payload': { 'node_id': 'LN-031', ... } }│ ║
║  └──────────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════════╝
4.8 Database Health  [ /databases ]
╔═══════════════════════════════════════════════════════════════════════╗
║  DATABASE HEALTH                                  Auto-refresh: 10s   ║
╠═══════════════════════════════════════════════════════════════════════╣
║  ┌─────────────────────┐  ┌─────────────────────┐                    ║
║  │ 🧠 Knowledge Lake   │  │ 🗃️  State Graph      │                    ║
║  │ Milvus + LlamaIndex │  │ PostgreSQL           │                    ║
║  │ ● HEALTHY           │  │ ● HEALTHY            │                    ║
║  │ Size: 423GB / 1TB   │  │ Size: 12.3GB / 50GB  │                    ║
║  │ Connections: 8/50   │  │ Connections: 24/100  │                    ║
║  │ Last write: 0.3s ago│  │ Last write: 0.1s ago │                    ║
║  │ [▶ Expand Details]  │  │ [▶ Expand Details]   │                    ║
║  └─────────────────────┘  └─────────────────────┘                    ║
║                                                                         ║
║  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────┐ ║
║  │ 🔗 LogicNode Reg.   │  │ 📋 Traceability     │  │ 🤖 Model Store│ ║
║  │ Redis + Git         │  │ SQLite              │  │ MLflow        │ ║
║  │ ● HEALTHY           │  │ ● HEALTHY            │  │ ● HEALTHY     │ ║
║  │ Nodes: 1,247        │  │ Records: 48,392      │  │ Models: 12    │ ║
║  │ Git commits: 312    │  │ Size: 1.8GB / 20GB  │  │ Runs: 847     │ ║
║  │ [▶ Expand]          │  │ [▶ Expand]           │  │ [▶ Expand]    │ ║
║  └─────────────────────┘  └─────────────────────┘  └───────────────┘ ║
╚═══════════════════════════════════════════════════════════════════════╝
4.9 Settings  [ /settings ]
╔══════════════════════════════════════════════════════════════════════╗
║  SETTINGS                                                             ║
╠══════════════════════════════════════════════════════════════════════╣
║  [API Keys] [System Config] [Theme] [Diagnostics]  ← Tab navigation  ║
╠══════════════════════════════════════════════════════════════════════╣
║  TAB: API KEYS                                                         ║
║                                                                         ║
║  Agent ID     │ Provider   │ Status      │ Last Rotated │ Actions      ║
║  ─────────────┼────────────┼─────────────┼──────────────┼─────────     ║
║  PM-001       │ Gemini Pro │ ✅ Valid    │ 3 days ago   │ [Edit] [Test]║
║  CEO-001      │ Gemini Pro │ ✅ Valid    │ 3 days ago   │ [Edit] [Test]║
║  PY-001       │ Gemini Fla.│ ✅ Valid    │ 3 days ago   │ [Edit] [Test]║
║  JS-001       │ Gemini Fla.│ ⚠️ Expiring │ 87 days ago  │ [Edit] [Test]║
║  ...          │ ...        │ ...         │ ...          │ ...          ║
║                                                                         ║
║  [Rotate All Keys]  [Export Vault Backup]                              ║
╠══════════════════════════════════════════════════════════════════════╣
║  TAB: SYSTEM CONFIG                                                    ║
║                                                                         ║
║  Redis URL:          redis://localhost:6379       [Edit]              ║
║  PostgreSQL URL:     postgresql://localhost:5432  [Edit]              ║
║  Max Concurrent Missions:  3                      [Edit]              ║
║  LogicNode Confidence Threshold:  70%             [Edit]              ║
║  Audit Test Count per Node:  1000                 [Edit]              ║
║  Mission Timeout (minutes):  60                   [Edit]              ║
╚══════════════════════════════════════════════════════════════════════╝
4.10 GitHub Repository Import  [ /repo ]
The repo import hub — the user's gateway to loading an existing codebase into the Refinery. Divided into three sequential steps: (1) Import, (2) Select, (3) Configure Mission. Each step unlocks after the previous one completes.
╔═══════════════════════════════════════════════════════════════════════════╗
║  GITHUB REPOSITORY IMPORT                        [Recent Repos ▼]        ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  STEP 1: IMPORT REPOSITORY  ●────────────────────────────────────         ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │  GitHub Repository URL                                           │    ║
║  │  [ https://github.com/user/project                          ]   │    ║
║  │                                                                  │    ║
║  │  Branch:  [ main ▼ ]    Subdirectory:  [ / (root) ]             │    ║
║  │                                                                  │    ║
║  │  🔒 Private repo? → Token detected in Settings ✅               │    ║
║  │                                                                  │    ║
║  │  [📂 Import Repository]                                         │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
║                                                                            ║
║  ── Cloning progress (visible after Import clicked) ───────────────────   ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │  🔄 Cloning my-project from github.com...                        │    ║
║  │  [████████████████████████░░░░░░] 78%                            │    ║
║  │  remote: Counting objects: 847, done.                            │    ║
║  │  Receiving objects: 78% (660/847)                                │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
║                                                                            ║
║  STEP 2: SELECT FILES  ○─────────────────────────────────────────────     ║
║  ┌──────────────────┬───────────────────────────────────────────────┐    ║
║  │  FILE TREE       │  SELECTION SUMMARY                            │    ║
║  │                  │                                               │    ║
║  │  ☑ 📁 src/       │  Languages detected:                          │    ║
║  │  ├ ☑ 🐍 scraper. │  🐍 Python:  12 files  (3,847 lines)         │    ║
║  │  ├ ☑ 🐍 parser.py│  📜 JS/TS:    5 files  (1,204 lines)         │    ║
║  │  ├ ☐ 📄 README.md│  📝 Config:   4 files  (ignore?)             │    ║
║  │  ☑ 📁 api/       │                                               │    ║
║  │  ├ ☑ 🌐 routes.js│  Selected: 17 files · 5,051 lines            │    ║
║  │  ☐ 📁 tests/     │  Est. mission time: ~14 minutes              │    ║
║  │  ☐ 📄 .env.examp │                                               │    ║
║  │                  │  [🔍 Filter: All ▼]  [☑ Select All Python]   │    ║
║  └──────────────────┴───────────────────────────────────────────────┘    ║
║                                                                            ║
║  STEP 3: CONFIGURE MISSION  ○────────────────────────────────────────     ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │  What do you want the Refinery to do?                            │    ║
║  │                                                                  │    ║
║  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │    ║
║  │  │ 🔬 Analyze   │ │ 🔄 Update    │ │ ✨ Add Feature│ │♻️ Refac│ │    ║
║  │  │ Understand & │ │ Modernize    │ │ Describe new │ │ Improve│ │    ║
║  │  │ extract all  │ │ deps, fix    │ │ feature in   │ │quality │ │    ║
║  │  │ LogicNodes   │ │ deprecations │ │ plain English│ │& perf  │ │    ║
║  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────┘ │    ║
║  │  [Selected: ✨ Add Feature]                                      │    ║
║  │                                                                  │    ║
║  │  Describe the feature or changes you want:                       │    ║
║  │  ┌────────────────────────────────────────────────────────────┐ │    ║
║  │  │ Add rate limiting to the scraper — max 10 req/sec with     │ │    ║
║  │  │ exponential backoff on 429 errors                          │ │    ║
║  │  └────────────────────────────────────────────────────────────┘ │    ║
║  │                                                                  │    ║
║  │  Git commit: [Auto-generate from mission ✓]  [Edit message]     │    ║
║  │                                                                  │    ║
║  │  [🚀 Launch Mission]                                            │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════════╝
Repo Import Page — Step States
Step
State
Visual Indicator
Unlocks When
Step 1: Import
Active on page load
Filled violet circle ●, full color panel
Always available
Step 2: Select Files
Locked until clone done
Hollow gray circle ○, panel grayed out
Clone completes successfully (exit code 0)
Step 3: Configure Mission
Locked until selection
Hollow gray circle ○, panel grayed out
At least 1 file is checked in the file tree
Launch Mission
Locked until Step 3
Disabled button, tooltip: 'Complete step 3'
Mission type selected + description entered (if required)
Repo Mission Detail — Diff Review Panel
After agents finish processing, the Mission Detail page shows an additional panel below the Smelt-Cycle stepper — the Change Review panel. This only appears on repo-type missions.
╔════════════════════════════════════════════════════════════════════════╗
║  REVIEW CHANGES  ← appears after DELIVERY phase completes             ║
║  ✨ Add Feature: Rate Limiting    [3 files changed · 47+ · 12-]       ║
╠════════════════════════════════════════════════════════════════════════╣
║  ☑ scraper.py                                    +32 lines  -4 lines  ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │    def fetch_url(url):                                         │  ║
║  │ -      response = requests.get(url)                            │  ║
║  │ +      response = requests.get(url, timeout=30)                │  ║
║  │ +      if response.status_code == 429:                         │  ║
║  │ +          time.sleep(exponential_backoff(retry_count))        │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║                                                                         ║
║  ☑ rate_limiter.py  (NEW FILE)                           +78 lines    ║
║  ☑ config.py                                             +2 lines     ║
║                                                                         ║
║  Commit message:  [HGR: Add Feature - Rate Limiting · m-9a3c1]        ║
║                                                                         ║
║  [✅ Apply Selected Changes]          [🗑️ Discard All Changes]         ║
║                                                                         ║
║  After apply:                                                           ║
║  [⬆️ Push to origin/main]  or  'Run: git push from /workspace/repos'   ║
╚════════════════════════════════════════════════════════════════════════╝
5. UI/UX COMPONENT LIBRARY
All reusable components for the HGR frontend. Every component must be built in React/TypeScript with Tailwind CSS. Dark mode is the default — all components must render correctly on #0F172A backgrounds.
5.1 Agent Status Card
Used on the Agents page and Mission Detail sidebar. Each card represents one agent and shows live status.
State
Border Left
Status Badge
Icon Animation
Background
ACTIVE
4px solid #10B981 (Green)
Green pill: ● ACTIVE
None
#1E293B
IDLE
4px solid #6B7280 (Gray)
Gray pill: ○ IDLE
None
#1E293B
ERROR
4px solid #EF4444 (Red)
Red pill: ✕ ERROR
Pulse ring (red)
#2D1B1B
PAUSED
4px solid #8B5CF6 (Violet)
Violet pill: ⏸ PAUSED
None
#1E293B
PROCESSING
4px solid #3B82F6 (Blue)
Blue pill: ⟳ PROCESSING
Spinner (continuous)
#1A2030
// AgentCard.tsx
interface AgentCardProps {
  agent: { id: string; name: string; role: string; pod: string;
           state: 'ACTIVE'|'IDLE'|'ERROR'|'PAUSED'|'PROCESSING';
           currentTask?: string; elapsedMs?: number; }
  onClick: () => void;
}
 
// Pod color mapping:
// Pod A → border-orange-500  | Pod B → border-zinc-500
// Pod C → border-blue-800    | Pod D → border-teal-600
// Executive → border-violet-500  | Support → border-gray-500
5.2 Mission Card (List Item)
Element
Spec
Container
White border 1px #334155, border-radius 8px, padding 16px, bg #1E293B
Mission ID
Monospace font, 12px, muted gray #94A3B8
Mission Title
Inter 600, 16px, white #F1F5F9
Status Badge
Pill badge — see status badge spec in Section 5.4
Progress Bar
Full-width, height 6px, border-radius 3px — shows only for RUNNING state
Phase Label
Small text, 12px, gray, right-aligned: 'Phase: SMELT'
Agent Count
Small text: '8 active agents' in muted gray
LogicNode Count
Small text: '31 LogicNodes' in muted gray
CTA Buttons
'View Live', 'Pause', 'Cancel' — text buttons, compact
Hover state
Background lightens to #263349, translateY(-1px)
5.3 Smelt-Cycle Phase Stepper
The 7-phase progress indicator used on Mission Detail and in mission cards. This is the signature component of the HGR interface.
  [✓ INTAKE]───[✓ FETCH]───[● SMELT 78%]───[○ GATING]───[○ FUSION]───[○ SQUEEZE]───[○ DELIVERY]
     2.1s          4.3s        ████████░░         —           —            —              —
 
  Legend:
  ✓ = Complete (Green filled circle, green connector line, elapsed time shown below)
  ● = Active  (Blue filled circle + pulse animation, progress bar below, % shown)
  ○ = Pending (Gray outline circle, gray connector line, no label)
Phase
# Agents Typical
Duration Typical
Phase Color
1. INTAKE
2 (PM + CEO)
2-10s
Violet (Executive)
2. FETCH
2 (IS + Broker)
5-30s
Blue (Support)
3. SMELT
4-24 (Specialists)
2-10min
Orange (Active processing)
4. GATING
4 (Audit Agents)
30s-5min
Amber (Verification)
5. FUSION
1 (CEO)
10-60s
Blue (Executive)
6. SQUEEZE
Up to 4 (Pod B Systems)
30s-3min
Steel (Systems)
7. DELIVERY
2 (SRE + PM)
5-30s
Green (Complete)
5.4 Status Badge Pills
Status
Label
Icon
Background
Text Color
Active
● ACTIVE
CheckCircle
#D1FAE5
#065F46
Idle
○ IDLE
Clock
#F3F4F6
#374151
Processing
⟳ PROCESSING
Loader2 (spin)
#DBEAFE
#1E40AF
Mining
⛏ MINING
Code2
#FEF3C7
#92400E
Verifying
✦ VERIFYING
ShieldCheck
#E0E7FF
#3730A3
Error
✕ ERROR
XCircle
#FEE2E2
#991B1B
Paused
⏸ PAUSED
PauseCircle
#EDE9FE
#5B21B6
Complete
✅ COMPLETE
CheckCircle2
#D1FAE5
#065F46
Cancelled
✗ CANCELLED
XOctagon
#F9FAFB
#6B7280
Queued
◷ QUEUED
Clock4
#F3F4F6
#4B5563
Running
▶ RUNNING
Play
#DBEAFE
#1D4ED8
Failed
✕ FAILED
XCircle
#FEE2E2
#B91C1C
5.5 Protocol Message Badge
Used in the Semantic Bus monitor and mission log. Each of the 6 protocols has a distinct color identity to allow instant visual parsing.
Protocol
Full Name
Color
Hex
Who Uses It
Alpha
Directive Protocol
Violet
#8B5CF6
CEO → Pods, CEO → Managers (task assignment)
Beta
Production Protocol
Blue
#3B82F6
Specialists → Managers → Audit (output delivery)
Delta
Audit Protocol
Amber
#F59E0B
Audit Agents → Specialists (verification results)
Sigma
Knowledge Protocol
Teal
#0D9488
IS Agent ↔ All (knowledge distribution)
Omega
User Protocol
Green
#10B981
PM Agent ↔ Human (user-facing comms)
Rho
Traffic Protocol
Orange
#F97316
API Broker → All (resource allocation)
5.6 Chat Message Bubbles
Type
Alignment
Background
Text
Shape
User message
Right
#8B5CF6 (Violet)
White #FFFFFF
rounded-2xl rounded-tr-sm
PM Agent message
Left
#1E293B (Slate)
Light #F1F5F9
rounded-2xl rounded-tl-sm
Feature Contract card
Left
#0F172A (Dark)
Light #F1F5F9
rounded-lg, full-width border #334155
System notification
Center
#1A2030 (Dark Blue)
Muted #94A3B8
rounded-full, small pill style
Error message
Left
#2D1B1B (Dark Red)
Red #FCA5A5
rounded-2xl rounded-tl-sm, red left border
Agent typing dots
Left
#1E293B (Slate)
— (animated)
rounded-full, 3 dots pulse animation
5.7 LogicNode Confidence Ring
A circular progress indicator showing confidence score (0-100%). Used in the LogicNode Explorer drawer and Mission Detail's LogicNode list.
Confidence Range
Ring Color
Inner Text Color
Interpretation
90-100%
#10B981 Green
#065F46
High confidence — extraction strongly verified
70-89%
#F59E0B Amber
#92400E
Medium confidence — manual review recommended
50-69%
#F97316 Orange
#9A3412
Low confidence — extraction uncertain, flag for review
< 50%
#EF4444 Red
#991B1B
Failed confidence — extraction rejected, retry
5.8 Toast Notification System
Toast notifications appear in the top-right corner. They stack vertically. Max 3 visible at once. They auto-dismiss after 5 seconds (errors after 10 seconds).
Type
Icon
Background
Duration
Example
Success
CheckCircle
#D1FAE5 / #065F46 text
5s auto-dismiss
✅ Mission m-9a3c1 launched successfully
Error
XCircle
#FEE2E2 / #991B1B text
10s, manual close
❌ Agent PY-001 failed: LLM timeout after 30s
Warning
AlertTriangle
#FEF3C7 / #92400E text
7s auto-dismiss
⚠️ API key for JS-001 expiring in 7 days
Info
Info
#DBEAFE / #1E40AF text
5s auto-dismiss
ℹ️ Mission m-4f7b2 entered GATING phase
5.9 Agent Detail Drawer
A slide-in panel from the right (400px wide) triggered by clicking any agent card. Used on both the Agents page and Mission Detail sidebar.
Section
Content
Update Frequency
Header
Agent ID, Name, Role, Pod badge, Status badge with live status
Every 2s via WS
Current Task
If ACTIVE: task description, mission ID link, elapsed time, progress %
Every 2s via WS
Performance
Average task duration, tasks completed today, error rate %
Every 30s REST
Log Stream
Live scrolling log with level filter tabs [ALL/INFO/WARN/ERROR]
Real-time WS stream
Action Buttons
'Open Full Logs' link | 'Restart Agent' button (with confirmation) | 'View on Agents Page'
Static
Close Controls
× button top-right | Escape key | Click backdrop (outside drawer)
User triggered
5.10 Keyboard Shortcuts
Because this is a local power-user application, keyboard shortcuts are first-class. They display as a sheet with Ctrl+? (Windows).
Shortcut
Action
Ctrl + N
New Mission — open /chat
Ctrl + D
Navigate to Dashboard / Home
Ctrl + M
Navigate to Missions
Ctrl + A
Navigate to Agents
Ctrl + L
Navigate to LogicNode Explorer
Ctrl + B
Navigate to Semantic Bus Monitor
Ctrl + ,
Navigate to Settings
Ctrl + ?
Show keyboard shortcuts reference sheet
Escape
Close any open drawer, modal, or dropdown
Ctrl + F
Focus search bar on current page
Ctrl + R
Force refresh data (re-fetch all APIs)
Space
Pause/Resume Semantic Bus monitor stream
5.11 Repository File Tree
The interactive file selector on the /repo page. Mirrors a VS Code-style tree with checkbox overlays for mission scoping.
Element
Behavior / Spec
Tree node — folder
Chevron ▶/▼ to expand/collapse. Checkbox selects all children recursively.
Tree node — file
Language icon badge (🐍 .py · 🌐 .js · ☕ .java etc.) · filename · line count on hover.
Checkbox state
3 states: ☑ checked · ☐ unchecked · ⊟ indeterminate (partial child selection).
Filtered view
Language filter dropdown hides non-matching extensions; tree structure preserved.
Excluded patterns
.env, node_modules/, __pycache__/, *.lock auto-excluded with grey strikethrough.
Selection summary
Sticky bar at tree bottom: 'N files · N lines' — updates on every checkbox change.
Max selection
Warn toast if >500 files selected: 'Large selection — mission may take 60+ min'.
5.12 Diff Viewer Panel
Unified diff display that renders agent-generated code changes for user review before they are written to disk. Appears in Mission Detail for all repo-type missions after the DELIVERY phase.
Element
Spec
Added lines
Background: #14532D (dark green) · text: #86EFAC · prefix: '+'
Removed lines
Background: #7F1D1D (dark red) · text: #FCA5A5 · prefix: '-'
Context lines
Background: #1E293B (slate-800) · text: #94A3B8 · no prefix
File header
Filename bold + language icon + '+N / -N lines' count. Collapsible.
New file badge
Green pill 'NEW FILE' beside filename for agent-created files.
Deleted file badge
Red pill 'DELETED' beside filename for agent-removed files.
Line numbers
Shown in gutter: old line / new line, gray, right-aligned.
Checkbox column
Each file has a checkbox to include/exclude from the commit — unchecking collapses diff.
Font
JetBrains Mono 13px — consistent with all log viewers in the app.
Max height
Each file diff scrollable at max-height: 400px before internal scroll activates.
5.13 Repo Context Banner
A persistent banner shown at the top of the Chat page when a GitHub repository is loaded as the active context. Signals to the user that the PM Agent is repo-aware.
Element
Spec
Background
#1E293B (slate-800) · left border 4px solid #1A56DB (blue-700)
Icon + name
📁 folder emoji + repo name in Inter SemiBold 14px
Branch pill
Gray pill showing current branch name (e.g. 'main')
Status
Last synced timestamp: 'Synced 3 min ago' in slate-400
File count
Subtle annotation: '17 files in context' in slate-500
Clear button
Ghost button '✕ Clear Repo' — confirmation dialog before unloading context
Position
Sticky below topbar, above the chat message list. Does not scroll.
6. INTERACTION PATTERNS & UX DECISIONS
6.1 No Login — Zero Friction Entry
Since this runs locally on Windows, there is no authentication, no session token, no login page. The user opens http://localhost:3000 in their browser and is immediately in Mission Control. This is a deliberate design decision.
✅  DO
Land directly on the Home / Launch Pad page with the system health visible within 2 seconds. Make the New Mission CTA the most visually dominant element.
❌  DON'T
Show any login form, account creation flow, email verification, or user profile page. These are not needed and add friction to a local app.
6.2 Dark Mode First
The HGR UI defaults to dark mode (#0F172A backgrounds). This is appropriate for a developer tool running on a dev machine — dark mode reduces eye strain during long sessions and looks more professional with technical content.
✅  DO
Default to dark mode on first launch. Store theme preference in localStorage. Allow toggle in Settings > Theme.
❌  DON'T
Force light mode as default. Never use pure #000000 black — always use the rich Slate palette (#0F172A, #1E293B, #334155).
6.3 Real-Time First, Polling Never
Every piece of data that changes during a mission (agent status, LogicNode count, bus messages, phase progress) must update via WebSocket. HTTP polling is not acceptable for live data — it creates jarring updates and unnecessary server load on the local machine.
Data Type
Update Mechanism
Fallback if WS Drops
Agent status
WebSocket /ws/agents
HTTP poll every 5s
Mission phase
WebSocket /ws/missions/[id]
HTTP poll every 3s
Semantic Bus stream
WebSocket /ws/bus
Pause stream, show warning banner
LogicNode count
WebSocket /ws/missions/[id]
HTTP poll every 5s
System health
WebSocket /ws/system
HTTP poll every 10s
Database health
HTTP REST poll
Every 10s (not WS — acceptable frequency)
Chat responses
WebSocket /ws/chat
HTTP long-poll fallback
6.4 Optimistic UI for Mission Launch
When the user clicks 'Confirm & Launch Mission', the UI should not wait for the server to create the mission before responding. It should immediately navigate to a pre-rendered mission detail page and populate it as data arrives.
User clicks 'Confirm & Launch Mission' in chat
UI immediately shows a 'Launching…' brief overlay (300ms)
POST /api/missions/create is sent to the backend
UI navigates to /missions/temp-id with a loading skeleton
Server responds with real mission ID — URL updates to /missions/m-9a3c1
WebSocket connection opens for this mission — real data begins flowing in
Loading skeletons replaced by real data as it arrives
6.5 Empty States
Every list or data table must have a thoughtful empty state — not just a blank space. Empty states tell the user what they can do next.
Page / Component
Empty State Message
CTA
Mission List
⚗ No missions yet. Start one to see it here.
'+ New Mission' button
Active Agents
○ All agents are idle. Ready for your next mission.
None — just informational
LogicNode Explorer
🔬 No LogicNodes extracted yet. Run a mission to populate this.
'+ New Mission' button
Semantic Bus
📡 No messages on the bus. Launch a mission to see activity.
None
Chat (new session)
⚗ I'm your PM Agent. Tell me what you'd like to build or analyze.
Suggested prompts (3 chips)
Search results
🔍 No results for '[query]'. Try a different search term.
Clear search X button
6.6 Error Handling & Recovery
Error Scenario
UI Response
Recovery Action
WebSocket disconnects
Yellow warning banner at top: 'Live updates paused — reconnecting…'
Auto-reconnect every 5s. Banner disappears when reconnected.
Agent ERROR state
Agent card turns red. Toast notification. Mission detail shows error phase.
'Restart Agent' button in drawer. 'View Logs' link.
Mission FAILED
Mission card turns red with ✕ FAILED badge. Toast notification.
'View Error Report' button shows what failed and why.
API call fails (HTTP)
Inline error state in the component (e.g. 'Failed to load agents — retry')
'Retry' button triggers re-fetch.
Invalid API key
Settings page shows red ❌ Invalid next to the key. Toast warning.
'Edit' button to paste new key.
Database connection lost
Database Health page shows red card. System-wide alert banner.
Manual restart instructions shown. 'Open Docker Logs' link.
6.7 GitHub Repo Import — Progressive Disclosure Flow
The /repo page uses a locked-step progressive disclosure pattern to prevent user error. Each of the 3 steps is visually locked until its predecessor completes. This eliminates the risk of launching a mission with no files selected or no URL entered.
✅  DO
Lock Step 2 and Step 3 until Step 1 (clone) succeeds. Use a clear visual step indicator with filled/hollow circles to communicate progress. Show real git output during cloning so the user knows it's working.
❌  DON'T
Show all three panels open at once. Use a spinner-only progress indicator with no feedback. Let the user click 'Launch Mission' before selecting any files — this leads to confusing empty missions.
The Diff Review panel in Mission Detail follows the same principle: changes are NEVER applied to disk automatically. The user must explicitly click 'Apply Selected Changes'. The CTA uses a confirmation pattern: first click shows a summary modal ('You are about to overwrite 3 files. Continue?'), second click executes.
Repo missions are visually distinguished everywhere in the app with a 📁 icon prefix — in the Mission list, in the chat history, in the sidebar Recent Missions widget, and in the Page Header breadcrumb.
7. IMPLEMENTATION TECH STACK
Layer
Technology
Version
Purpose
Framework
Next.js
14.x
App Router, SSR/CSR hybrid, file-based routing
Language
TypeScript
5.x
Strict mode, full type safety, no 'any'
Styling
Tailwind CSS
3.x
Utility-first, dark mode support, custom HGR tokens
UI Library
shadcn/ui
Latest
Accessible headless components: Dialog, Sheet, Toast, etc.
Icons
Lucide React
0.263+
All UI icons — consistent stroke style
State
Zustand
4.x
Global app state (agent states, mission states, WebSocket data)
Server State
@tanstack/react-query
5.x
HTTP data fetching, caching, background updates
Real-time
WebSocket (native)
—
Browser WebSocket API — connects to Redis via local WS server
Charts
Recharts
2.x
Line charts, bar charts, progress indicators
Fonts
Inter + JetBrains Mono
—
Loaded from Google Fonts CDN or bundled locally
Code Highlight
Prism.js
1.x
JSON syntax highlighting for LogicNode Refined-IR viewer
HTTP Client
Axios
1.x
REST API calls to local backend (FastAPI on port 8000)
Date/Time
date-fns
3.x
Timestamp formatting throughout the app
7.1 Directory Structure
mission-control/              ← Next.js 14 App
  app/
    layout.tsx                ← Root layout (topbar + sidebar shell)
    page.tsx                  ← Home / Launch Pad
    chat/page.tsx             ← PM Agent Chat
    
missions/
      page.tsx                ← Mission list
      [id]/page.tsx           ← Mission detail (dynamic route)
    agents/page.tsx           ← Agent grid
    logicnodes/page.tsx       ← LogicNode explorer
    semantic-bus/page.tsx     ← Bus monitor
    databases/page.tsx        ← DB health
    settings/page.tsx         ← Settings
  
components/
    layout/
      Topbar.tsx  Sidebar.tsx  StatusBar.tsx
    agents/
      AgentCard.tsx  AgentGrid.tsx  AgentDrawer.tsx
    missions/
      MissionCard.tsx  MissionDetail.tsx  SmeltCycleStepper.tsx
    chat/
      ChatInterface.tsx  MessageBubble.tsx  FeatureContractCard.tsx  ChatInput.tsx
    logicnodes/
      LogicNodeTable.tsx  LogicNodeDrawer.tsx  ConfidenceRing.tsx
    bus/
      BusMonitor.tsx  ProtocolBadge.tsx  MessageRow.tsx
    shared/
      StatusBadge.tsx  Toast.tsx  EmptyState.tsx  SearchBar.tsx
      ProgressBar.tsx  LoadingSkeleton.tsx  ConfirmDialog.tsx
  hooks/
    useWebSocket.ts  useMission.ts  useAgents.ts  useBus.ts
  store/
    agentStore.ts  missionStore.ts  notificationStore.ts
  
types/
    agent.ts  mission.ts  logicnode.ts  protocol.ts
  lib/
    api.ts  ws.ts  constants.ts  utils.ts
8. ACCEPTANCE CRITERIA SUMMARY
The frontend implementation is complete when all of the following criteria are met. These criteria are derived from the user stories in Section 3 and are the definition of done for the frontend team.
#
Criterion
Story Ref
AC-01
App opens at http://localhost:3000 with no login, no redirect
US-001
AC-02
Home page shows system health score within 2 seconds
US-001
AC-03
PM Agent Chat accepts natural language input and responds within 3 seconds
US-002
AC-04
Files can be attached to chat via drag & drop or file picker
US-003
AC-05
Feature Contract card is displayed before mission launch with Edit/Confirm options
US-004
AC-06
Confirming launch redirects to Mission Detail (/missions/[id]) automatically
US-005
AC-07
All 7 Smelt-Cycle phases update in real-time via WebSocket (no polling)
US-006
AC-08
Active agents list on Mission Detail shows live agent cards
US-007
AC-09
LogicNode counter increments in real-time during SMELT phase
US-008
AC-10
Pause and Cancel buttons work with confirmation dialogs
US-009
AC-11
Agents page shows all 35 agents organized by tier and pod
US-010
AC-12
Agent grid filters by pod and status work correctly
US-011
AC-13
Clicking any agent opens a slide-in drawer with live logs
US-012
AC-14
LogicNode Explorer table is searchable, filterable, and sortable
US-013
AC-15
LogicNode drawer shows full Refined-IR JSON with copy button
US-014
AC-16
Semantic Bus Monitor shows live stream with protocol color coding
US-015
AC-17
Database Health page shows live status for all 5 databases
US-016
AC-18
Settings API Key table allows edit, test, and shows valid/invalid status
US-017
AC-19
All keyboard shortcuts in Section 5.10 work as specified
US-010+
AC-20
All empty states show appropriate messaging and CTAs
UX-6.5
AC-21
WebSocket disconnect shows warning banner and auto-reconnects
UX-6.6
AC-22
Dark mode is default; theme preference stored in localStorage
UX-6.2
AC-23
App renders correctly at 1440px and 1024px widths
Style Guide
AC-24
All components use Inter font and JetBrains Mono for code/IDs
Style Guide
AC-25
Status badges use exact colors from Section 5.4 specification
Style Guide
AC-26
/repo page shows 3 locked steps — Step 2 disabled until clone succeeds, Step 3 disabled until ≥1 file checked
US-018, US-019
AC-27
File tree renders with correct language icons, 3-state checkboxes, and auto-excludes .env / node_modules
US-019
AC-28
Mission type selector shows all 4 types (Analyze, Update, Add Feature, Refactor) — description field only required for Add Feature/Update
US-020
AC-29
Repo missions show 📁 icon in Mission list, Mission Detail header, and Chat history
US-021, US-024
AC-30
Mission Detail for repo missions shows per-file processing status (active pulse · complete ✓ · failed ✗) in file tree overlay
US-021
AC-31
Diff Review panel appears after DELIVERY phase on repo missions; changes NOT written to disk until 'Apply' clicked
US-022
AC-32
Diff viewer renders added lines green (#14532D bg) and removed lines red (#7F1D1D bg) in JetBrains Mono 13px
US-022
AC-33
After 'Apply', a git commit is created with structured message; 'Push to remote' button appears if GitHub token is configured
US-023
AC-34
Chat page shows Repo Context Banner when repo is loaded; banner persists across chat turns and shows sync timestamp
US-024
AC-35
Settings page GitHub Tokens section validates PAT on entry and stores it encrypted; never displays token in plaintext after save
US-025
9. ACCESSIBILITY SPECIFICATION (WCAG 2.2)
All HGR frontend components must conform to WCAG 2.2 Level AA. This section defines the concrete accessibility requirements identified in the gap analysis (gaps GAP-A01 through GAP-A08) and mandates specific implementations.
9.1 ARIA Roles Reference (Resolves GAP-A01)
Every interactive component must declare explicit ARIA roles. The following table is the complete mandatory mapping:
Component
ARIA Role
Required Labels / Properties
AgentCard
article
aria-label="{AgentName} — {status}"
AgentDrawer
dialog
aria-modal="true", focus trap required (GAP-A04), aria-labelledby pointing to drawer title
MissionCard
article
aria-label="Mission {id}: {status}"
SmeltCycleStepper
list
aria-label="Smelt Cycle phases", each step is listitem with aria-current="step" when active
BusMonitor
log
aria-label="Semantic Bus live message stream", aria-live="polite" on new-message announcer
ChatInterface
main
aria-label="PM Agent Chat", message list uses role="log" with aria-live="polite"
ConfirmDialog
alertdialog
aria-modal="true", focus trap mandatory, aria-describedby for destructive action warnings
SearchBar
search
aria-label="Search {context}", results count announced via aria-live region
Toast
status
aria-live="polite" (info/success), aria-live="assertive" (error), role="alert" for errors
Sidebar
nav
aria-label="Main navigation", active link uses aria-current="page"
LogicNodeDrawer
dialog
aria-modal="true", focus trap required, JSON code block uses role="region" aria-label="Refined-IR JSON"
StatusBadge
status
Never rely on color alone — always include text label alongside color indicator
9.2 Color Contrast Compliance (Resolves GAP-A02)
All text must meet WCAG 2.2 AA contrast requirements (4.5:1 for normal text, 3:1 for large text/UI components). The following correction is mandatory: muted gray #94A3B8 used on background #0F172A yields only 5.1:1 contrast ratio, which is marginal and fails for small text. The corrected value is #CBD5E1 which yields 8.2:1 — well above the AA threshold. All instances of #94A3B8 for body text must be replaced with #CBD5E1.
9.3 Focus Management (Resolves GAP-A03, A04, A08)
Focus Ring Specification: All interactive elements must display a visible focus ring on keyboard navigation. Implementation: outline: 2px solid #8B5CF6; outline-offset: 2px. The :focus-visible pseudo-class must be used (not :focus) so the ring only appears for keyboard users. Mouse users must not see the ring. Focus Trap: Any component with role="dialog" or role="alertdialog" must implement a focus trap. When a drawer or dialog opens, focus moves to the first focusable element inside. Tab and Shift+Tab must cycle only within the dialog. Escape key closes the dialog and returns focus to the trigger element. Focus Order: The Tab key order for complex layouts must follow logical reading order (top-to-bottom, left-to-right). The Mission Detail page specifically must tab through the Smelt Cycle phases, then the active agent list, then the LogicNode counter, in that order.
9.4 Skip Navigation and Reduced Motion (Resolves GAP-A05, A06)
Skip Navigation: A "Skip to main content" link must be the first focusable element on every page. It is visually hidden by default (via CSS clip, not display:none) and appears on keyboard focus. It links to id="main-content" on the page’s primary content region. Reduced Motion: All animations and transitions must respect the user’s prefers-reduced-motion media query. When this preference is set, disable: spinner animations, slide-in transitions for drawers, progress bar animations, pulsing status indicators, and chart transitions. Essential state transitions (e.g., loading skeleton to content) may use a simple opacity fade (200ms max) as a respectful fallback.
9.5 Semantic HTML Map (Resolves GAP-A07)
Every page must use semantic HTML5 landmark elements: <header> for the Topbar, <nav> for the Sidebar, <main id="main-content"> for page content, <aside> for drawers and side panels, <footer> for the StatusBar, <section> with aria-labelledby for major content groupings, <article> for repeating card components, and <h1> through <h3> in strict descending order with no skipped levels. Div and span elements must only be used for styling hooks — never as structural elements replacing semantic ones.
10. PERFORMANCE BUDGET
Because HGR runs entirely on local hardware, performance budgets must be maintained to ensure the application remains responsive even when all 35 agents are active and the Semantic Bus is processing up to 47 messages per second. This section resolves gaps GAP-P01 through GAP-P05.
10.1 Core Web Vitals Targets (Resolves GAP-P01)
Metric
Target
Notes
LCP (Largest Contentful Paint)
≤1.5s
Localhost advantage; skeleton screens show immediately
INP (Interaction to Next Paint)
≤100ms
Critical during active missions; no heavy work on UI thread
CLS (Cumulative Layout Shift)
≤0.05
Reserve space for agent cards; never inject content above viewport
JS Bundle (gzipped)
≤500KB
Heavy libs (Recharts, Prism.js, DiffViewer) must be lazy loaded
TTI (Time to Interactive)
≤2s
Measured at cold start; CI pipeline fails if exceeded
10.2 Lazy Loading Strategy (Resolves GAP-P02)
The following components must be loaded on demand using Next.js dynamic() with loading fallback skeletons: Recharts (loaded only on /databases and Mission Detail charts), Prism.js syntax highlighter (loaded only when a code block is rendered in chat or LogicNode drawer), DiffViewer (loaded only on Diff Review panel after DELIVERY phase), FileTree (loaded only on /repo and Mission Detail for repo missions), and DiagramChart (loaded only on /agents when the topology view is active). All page components outside the critical path (Home, Chat) must also use dynamic() import. This reduces initial bundle size by an estimated 60–70KB gzipped.
10.3 Virtualization for High-Frequency Streams (Resolves GAP-P03)
The BusMonitor component processes up to 47 messages per second. Rendering every message as a DOM node will freeze the browser within seconds. The BusMonitor must use react-virtual (or @tanstack/virtual) to render only the visible rows in the viewport, typically 50–100 items. The virtualized list must: maintain a fixed row height of 40px, keep a maximum buffer of 1000 messages in memory (rolling), support keyboard navigation through the virtual list, and maintain scroll position correctly when new messages arrive (auto-scroll to bottom unless the user has manually scrolled up). The same virtualization requirement applies to the AgentLogViewer inside AgentDrawer when displaying live agent logs.
11. SECURITY IMPLEMENTATION
Although HGR runs locally, security is critical because the application stores and uses LLM API keys for all 35 agents. A single XSS vulnerability could expose all API keys simultaneously. This section resolves gaps GAP-S01 through GAP-S05 and defines mandatory security controls.
11.1 Content Security Policy (Resolves GAP-S01)
The Next.js application must set the following HTTP response headers via next.config.js headers() configuration. Content-Security-Policy must be: default-src ‘self’; script-src ‘self’ ‘unsafe-eval’; style-src ‘self’ ‘unsafe-inline’; connect-src ‘self’ ws://localhost:*; img-src ‘self’ data:; object-src ‘none’; frame-ancestors ‘none’. The unsafe-eval allowance is required for Next.js development mode and must be removed in production builds. Additional mandatory headers: X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy: no-referrer, Permissions-Policy: camera=(), microphone=(), geolocation=().
11.2 XSS Prevention for Chat Rendering (Resolves GAP-S02)
PM Agent responses rendered in the ChatInterface may contain markdown with code blocks and potentially HTML. Raw dangerouslySetInnerHTML is forbidden. All agent-generated content must be sanitized using DOMPurify before rendering. The sanitization config must allow: basic markdown-rendered HTML tags (p, strong, em, code, pre, ul, ol, li, blockquote, h1-h6), but must strip: script, iframe, object, embed, form, input, style, link, base, and all event handler attributes (onclick, onload, etc.). The same DOMPurify sanitization must be applied to the DiffViewer component (Resolves GAP-S05) which renders AI-generated code diffs.
11.3 API Key Vault Encryption (Resolves GAP-S03)
API keys for all 35 agents must never be stored in plaintext in localStorage, sessionStorage, or any browser-accessible storage. The vault implementation must use node-keytar v7+ to store secrets in the Windows Credential Manager (DPAPI-encrypted). The Next.js API route /api/vault handles all vault operations server-side — the frontend never accesses keytar directly. The Settings page displays only masked previews of stored keys (first 4 characters + asterisks). After a key is saved, the full key is never returned to the frontend. The “Test” button triggers /api/vault/test which validates the key server-side and returns only a boolean result. GitHub Personal Access Tokens (from AC-35) must follow the same vault storage pattern (Resolves GAP-S04 for URL inputs: all repo URLs provided on /repo must be validated against a safe URL allowlist before processing).
12. TESTING STRATEGY
The testing strategy resolves gaps GAP-DX01 (no testing strategy) and GAP-O01 (no React Error Boundaries). All 35 Acceptance Criteria defined in Section 8 must have automated test coverage before the frontend is considered production-ready.
12.1 Unit and Component Testing
Framework: Vitest + React Testing Library. Coverage threshold: 80% for statements, branches, functions, and lines. All 13 reusable components from Section 7 must have dedicated test files. Test files live adjacent to components at ComponentName.test.tsx. Each component test must cover: default render state, all prop variants (especially status and phase enums), user interaction events (click, keyboard), and error/empty states. The StatusBadge component, due to its use across all pages, requires 100% branch coverage — every status value must be tested.
12.2 Accessibility Testing (jest-axe)
Every component test file must include an axe accessibility scan using jest-axe. The pattern is: render the component, run await axe(container), assert expect(results).toHaveNoViolations(). This catches WCAG violations automatically on every test run and CI build. No component may ship with outstanding jest-axe violations. The only exceptions allowed are “best-practice” level violations (not “minor”, “moderate”, “serious”, or “critical”).
12.3 Integration Testing (MSW)
API integration tests use Mock Service Worker (MSW) to intercept fetch and WebSocket calls. Every API route defined in Section 7 (lib/api.ts) must have a corresponding MSW handler. Integration tests must cover: successful responses with realistic fixture data, 404 and 500 error responses, WebSocket connection establishment and message handling, WebSocket disconnect and reconnect behavior, and React Query cache invalidation scenarios. The MSW server setup lives at src/__mocks__/server.ts and is initialized in vitest.setup.ts.
12.4 End-to-End Testing (Playwright)
End-to-end tests use Playwright against a locally running Next.js dev server. There must be one E2E test per Acceptance Criterion (AC-01 through AC-35). Tests live at e2e/ac-{number}.spec.ts. Critical E2E scenarios that must pass before every release: (1) full mission lifecycle from /chat through to Diff Review on /missions/[id], (2) all 35 agents visible and filterable on /agents, (3) API key save and mask cycle on /settings, (4) /repo clone flow through file selection to mission launch, and (5) WebSocket disconnect banner appears within 3 seconds of simulated disconnect. Playwright must be configured to run against Chromium only (since HGR targets Windows with Chrome/Edge).
12.5 React Error Boundaries (Resolves GAP-O01)
React Error Boundaries are mandatory at the following levels in the component tree to prevent a single crashing agent card or malfunctioning chart from taking down the entire Mission Control interface. Required boundary placement: one global boundary wrapping the entire application (in layout.tsx) which renders a full-page error screen with a “Reload Application” button; one boundary around each AgentCard to isolate individual agent failures from the AgentGrid; one boundary around each MissionCard; one boundary around the BusMonitor virtualized list; and one boundary around each chart/visualization component (Recharts, DiffViewer). Each boundary must log the error to the structured frontend logging system (see Section 12.6) before rendering its fallback UI. The fallback UI must display the error type, a safe message, and a retry action where appropriate.
12.6 Performance Testing (Lighthouse CI)
Lighthouse CI must be integrated into the development workflow to enforce the performance budget defined in Section 10.1. The Lighthouse CI configuration must set budgets for: performance score ≥90, accessibility score ≥95 (driven by WCAG compliance from Section 9), LCP ≤1500ms, INP ≤100ms, CLS ≤0.05, and total JS size ≤500KB. A build that fails these thresholds must not be deployed. Lighthouse CI runs against the production build (next build && next start) to capture accurate metrics. The Home page (/) and Mission Detail (/missions/test-id) are the two primary measurement pages since they represent the highest complexity renders in the application.
⚗
This frontend spec is the contract between design and engineering. Any deviation requires a documented design decision.
Holy Grail Refinery — Frontend Design Specification v1.1  ·  March 2026  ·  Local Windows Application — Updated with Accessibility, Performance, Security & Testing Specifications
