# USER-FACING IDE INTERFACE SPECIFICATION
## Holy Grail Refinery: The Builder's Experience

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase - New Document  
**Document Owner:** Product & Frontend Team  
**Related Documents:** Doc 15 (Mission Control), Doc 01 (PRD), Doc 06 (Agent Architecture)

---

## EXECUTIVE SUMMARY

This document specifies the **user-facing IDE interface** - the actual product that users interact with when building applications with the Holy Grail Refinery. While Mission Control (Document 15) monitors internal agent operations, **this interface is the product** - a natural language-driven coding environment where users describe what they want to build and watch it materialize in real-time.

**Target Experience:** Bolt.new/Replit/Lovable style interface  
**Core Innovation:** Conversational AI-powered development with live preview  
**Key Differentiator:** True multi-language understanding (14 languages), not just template generation

---

## 1. PRODUCT VISION & USER EXPERIENCE

### 1.1 The Builder's Journey

**Initial State:** User opens the Refinery interface and sees:
```
┌─────────────────────────────────────────────────────┐
│  🏗️  Holy Grail Refinery                            │
│                                                      │
│  What would you like to build today?                │
│                                                      │
│  [Type your idea or describe your project...]       │
│                                                      │
│  💡 Examples:                                        │
│  • "Build me a real-time stock trading dashboard"   │
│  • "Create an e-commerce site with payment"         │
│  • "I need a REST API for user management"          │
└─────────────────────────────────────────────────────┘
```

**User Types:** "Build me a task management app with React frontend and Python backend"

**System Responds:** PM Agent engages in conversational requirements gathering:
```
PM Agent: Great! Let me understand what you need:

✓ Frontend: React with TypeScript
✓ Backend: Python (FastAPI or Django?)
✓ Features: Task CRUD, user authentication, real-time updates?
✓ Database: PostgreSQL or MongoDB?
✓ Deployment: Docker containers?

Would you like:
[ ] Drag & drop task reordering
[ ] Team collaboration features  
[ ] Mobile responsive design
[ ] Dark mode

[Continue] [Start Over] [Show Me Examples]
```

---

### 1.2 The "Vibe Capture" Experience

**Philosophy:** Users shouldn't need to know technical implementation details. The PM Agent translates "vibes" into specifications.

**Example Interaction:**

User: "I want something clean and modern, like Notion's interface"

PM Agent: 
```
🎨 Design Vision Captured:
• Minimalist aesthetic
• Generous whitespace
• Soft shadows and rounded corners
• Sidebar navigation
• Keyboard shortcuts

Generating visual mockup...
```

**Live Wireframe Generation:**
The interface shows a real-time generated wireframe/mockup of the UI being described.

---

## 2. INTERFACE ARCHITECTURE

### 2.1 Main Application Layout

```
┌──────────────────────────────────────────────────────────────┐
│ [🏗️ Refinery]  [Projects ▼]  [Templates]  [@username ▼]    │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────┐  ┌────────────────────────────────┐│
│  │                     │  │                                 ││
│  │   CHAT PANEL       │  │      LIVE PREVIEW              ││
│  │   (Left 40%)       │  │      (Right 60%)               ││
│  │                     │  │                                 ││
│  │ User: Build me a... │  │  [Rendered Output]             ││
│  │                     │  │                                 ││
│  │ PM Agent: I'll help│  │  [Interactive Preview]         ││
│  │ you with that...    │  │                                 ││
│  │                     │  │  [Auto-refreshes]              ││
│  │ [Input box here]   │  │                                 ││
│  │                     │  │  [Full Screen] [Mobile View]   ││
│  └─────────────────────┘  └────────────────────────────────┘│
│                                                               │
├──────────────────────────────────────────────────────────────┤
│  [CODE VIEW]  [TERMINAL]  [DEPENDENCIES]  [LOGS]  [AGENTS] │
└──────────────────────────────────────────────────────────────┘
```

---

### 2.2 Panel Breakdown

#### **LEFT PANEL: Conversational Chat Interface**
- **Purpose:** Primary interaction point with PM Agent
- **Features:**
  - Natural language input
  - Rich message rendering (markdown, code blocks, images)
  - Inline clarification questions from PM Agent
  - Visual mockup thumbnails
  - "Refine" and "Regenerate" buttons on each response
  - Chat history persistence
  
**Chat Message Components:**
```typescript
interface ChatMessage {
  id: string
  role: 'user' | 'pm_agent' | 'system'
  content: string
  timestamp: Date
  attachments?: {
    type: 'mockup' | 'code_snippet' | 'file'
    data: any
  }[]
  actions?: {
    label: string
    action: () => void
  }[]
}
```

#### **RIGHT PANEL: Live Preview**
- **Purpose:** Real-time rendering of the application being built
- **Features:**
  - Automatic refresh on code changes
  - Device preview modes (desktop, tablet, mobile)
  - Interactive - users can click around and test
  - Console output for debugging
  - Network request monitoring
  - Performance metrics overlay

**Preview Modes:**
```typescript
enum PreviewMode {
  DESKTOP = 'desktop',
  TABLET = 'tablet',
  MOBILE = 'mobile',
  CUSTOM = 'custom'
}

interface PreviewConfig {
  mode: PreviewMode
  width?: number
  height?: number
  orientation?: 'portrait' | 'landscape'
  refreshInterval?: number
}
```

#### **BOTTOM PANEL: Technical Details (Collapsible)**

**Tabs:**

1. **CODE VIEW Tab**
   - File tree on left
   - Code editor on right
   - Syntax highlighting
   - Read-only by default (can enable editing)
   - Real-time updates as agents modify code
   
2. **TERMINAL Tab**
   - Standard terminal output
   - Container logs
   - Build/compile output
   - Error messages with stack traces
   
3. **DEPENDENCIES Tab**
   - Visual dependency graph
   - Package versions
   - Update notifications
   - Security vulnerability warnings
   
4. **LOGS Tab**
   - Agent activity log
   - Semantic Bus message stream (filtered)
   - Mission timeline
   - Performance metrics
   
5. **AGENTS Tab**
   - Simplified agent status view
   - Active agents highlighted
   - Current task for each agent
   - Links to full Mission Control dashboard

---

## 3. KEY USER FLOWS

### 3.1 New Project Creation Flow

```
1. User clicks "New Project"
   ↓
2. System presents template gallery:
   - Web App (React, Vue, Svelte)
   - API Backend (Python, Node, Go)
   - Full Stack (various combos)
   - Desktop App (Electron, Tauri)
   - Mobile App (React Native)
   - Data Science (Python, R, Julia)
   - Blank Canvas
   ↓
3. User selects template OR describes from scratch
   ↓
4. PM Agent conducts intake interview:
   - What features do you need?
   - What's your target audience?
   - Any design preferences?
   - Performance requirements?
   - Deployment preferences?
   ↓
5. PM Agent generates Feature Contract with:
   - Visual mockups
   - Tech stack recommendation
   - Project structure preview
   ↓
6. User reviews and approves/modifies
   ↓
7. System creates project workspace
   ↓
8. CEO Agent initiates Smelt-Cycle
   ↓
9. User sees real-time progress:
   - Agents activating
   - Files being created
   - Dependencies installing
   - First preview appearing
   ↓
10. User can start iterating immediately
```

---

### 3.2 Iterative Development Flow

**User makes a request:** "Add user authentication with Google OAuth"

**System response sequence:**

```
[PM Agent responds in chat]
PM Agent: I'll add Google OAuth authentication. This will include:
✓ Login/logout buttons
✓ Session management  
✓ Protected routes
✓ User profile display

Estimated time: 2-3 minutes

[Start] [Customize] [Cancel]

───────────────────────────────────────

[User clicks Start]

[Visual progress indicator appears]

🔄 AGENT ACTIVITY:
✓ CEO Agent: Decomposing feature request...
⏳ JavaScript Specialist: Adding OAuth client library...
⏳ Python Specialist: Implementing backend auth...
⏳ Security Specialist: Reviewing implementation...

───────────────────────────────────────

[Code files update in real-time in Code View]
[Live preview shows login button appearing]
[User can test OAuth flow immediately]

───────────────────────────────────────

PM Agent: ✓ Authentication added! 
You can now test the login flow in the preview.

I've also added:
• Session persistence
• Token refresh logic
• Logout functionality

Would you like to customize the login UI?
```

---

### 3.3 Debugging & Refinement Flow

**User encounters an issue:** "The login button isn't working on mobile"

**System debugging sequence:**

```
PM Agent: Let me investigate the mobile login issue.

[Switches preview to mobile view automatically]

🔍 DIAGNOSIS:
✓ Bug Tracker Agent: Analyzing issue...
⏳ Running mobile tests...
⏳ Checking responsive CSS...

───────────────────────────────────────

PM Agent: Found the issue:

Problem: Button z-index conflict with mobile nav overlay
Fix: Adjusted CSS stacking context

[Live preview updates with fix]

Please test again. The button should now be clickable.

[Test on Mobile] [Test on Tablet] [Looks Good]
```

---

## 4. CONVERSATIONAL INTERFACE PATTERNS

### 4.1 PM Agent Personality & Tone

**Guidelines:**
- Professional but friendly
- Proactive in asking clarifying questions
- Uses emojis sparingly (✓, ⏳, 🔍, ⚠️)
- Explains technical decisions in simple terms
- Celebrates progress ("Great! That's working now")
- Honest about limitations ("This might take a bit longer...")

**Example Responses:**

❌ **Bad:** "I have initiated the OAuth integration subroutine via Protocol Alpha to the JavaScript Specialist Agent."

✅ **Good:** "I'm adding Google login now. Should be ready in about 2 minutes."

---

❌ **Bad:** "ERROR: Specification ambiguity detected. Please provide additional parameters."

✅ **Good:** "Quick question: Should users be able to sign up with just Google, or do you also want email/password signup?"

---

### 4.2 Clarification Patterns

When PM Agent needs more information, it should:

1. **Present options visually:**
```
Which database would you prefer?

[PostgreSQL]  [MongoDB]  [MySQL]  [Not Sure]
    SQL          NoSQL      SQL      Help me choose
```

2. **Provide context for decisions:**
```
For real-time features, I recommend WebSockets.

Pros:
• True real-time updates
• Lower latency
• Better for live data

Cons:
• More complex setup
• Higher server load

Alternative: Long polling (simpler but slower)

[Use WebSockets] [Use Long Polling] [Explain More]
```

3. **Show examples when helpful:**
```
What kind of charts do you need?

[📊 Bar Charts]  [📈 Line Graphs]  [🥧 Pie Charts]  
[Example]        [Example]          [Example]

[Show me all options]
```

---

### 4.3 Error Communication

When things go wrong:

```
⚠️ Something went wrong

The Python backend isn't starting. 

Common causes:
• Port 8000 already in use
• Missing environment variable
• Package installation failed

I'm working on it...

[View Logs] [Restart Containers] [Get Help]

───────────────────────────────────────

[Auto-diagnosis happening]

PM Agent: Found it! The .env file was missing the 
DATABASE_URL variable. I've added it.

[Restart Now] [Review Changes]
```

---

## 5. VISUAL DESIGN SYSTEM

### 5.1 Color Palette

```css
/* Primary Brand Colors */
--refinery-primary: #2563eb;      /* Trust blue */
--refinery-secondary: #7c3aed;    /* Innovation purple */
--refinery-accent: #f59e0b;       /* Energy amber */

/* Semantic Colors */
--success: #10b981;               /* Green */
--warning: #f59e0b;               /* Amber */
--error: #ef4444;                 /* Red */
--info: #3b82f6;                  /* Blue */

/* UI Colors */
--bg-primary: #ffffff;
--bg-secondary: #f9fafb;
--bg-tertiary: #f3f4f6;
--text-primary: #111827;
--text-secondary: #6b7280;
--border: #e5e7eb;

/* Dark Mode */
--dark-bg-primary: #0f172a;
--dark-bg-secondary: #1e293b;
--dark-bg-tertiary: #334155;
--dark-text-primary: #f1f5f9;
--dark-text-secondary: #94a3b8;
--dark-border: #334155;
```

---

### 5.2 Typography

```css
/* Font Stack */
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* Type Scale */
--text-xs: 0.75rem;      /* 12px */
--text-sm: 0.875rem;     /* 14px */
--text-base: 1rem;       /* 16px */
--text-lg: 1.125rem;     /* 18px */
--text-xl: 1.25rem;      /* 20px */
--text-2xl: 1.5rem;      /* 24px */
--text-3xl: 1.875rem;    /* 30px */
--text-4xl: 2.25rem;     /* 36px */

/* Font Weights */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

---

### 5.3 Component Design Patterns

#### **Chat Message Bubble**
```typescript
// User message: Right-aligned, primary color
<div className="ml-auto max-w-[80%] bg-refinery-primary text-white rounded-2xl rounded-tr-sm px-4 py-3">
  <p>Build me a dashboard</p>
  <span className="text-xs opacity-70">2:34 PM</span>
</div>

// PM Agent message: Left-aligned, secondary background
<div className="mr-auto max-w-[80%] bg-gray-100 text-gray-900 rounded-2xl rounded-tl-sm px-4 py-3">
  <p>I'll help you build that dashboard...</p>
  <span className="text-xs opacity-70">2:34 PM</span>
</div>
```

#### **Progress Indicator**
```typescript
<div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded">
  <div className="flex items-center mb-2">
    <Spinner className="mr-2" />
    <span className="font-medium">Building your application...</span>
  </div>
  
  <div className="space-y-2">
    <div className="flex items-center">
      <CheckCircle className="text-green-500 mr-2" />
      <span className="text-sm">Project structure created</span>
    </div>
    <div className="flex items-center">
      <Loader className="animate-spin text-blue-500 mr-2" />
      <span className="text-sm">Installing dependencies...</span>
    </div>
    <div className="flex items-center text-gray-400">
      <Circle className="mr-2" />
      <span className="text-sm">Starting dev server</span>
    </div>
  </div>
</div>
```

#### **Action Button Group**
```typescript
<div className="flex gap-2 mt-4">
  <button className="px-4 py-2 bg-refinery-primary text-white rounded-lg hover:bg-blue-600 transition">
    Start Building
  </button>
  <button className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition">
    Customize
  </button>
  <button className="px-4 py-2 text-gray-600 hover:text-gray-900 transition">
    Cancel
  </button>
</div>
```

---

## 6. TECHNICAL IMPLEMENTATION

### 6.1 Frontend Stack

```json
{
  "framework": "Next.js 14",
  "ui_library": "React 19",
  "styling": "Tailwind CSS",
  "state_management": "Zustand",
  "websocket": "Socket.io-client",
  "code_editor": "Monaco Editor (VS Code engine)",
  "charts": "Recharts / D3.js",
  "animations": "Framer Motion",
  "icons": "Lucide React",
  "markdown": "react-markdown",
  "syntax_highlighting": "Prism.js"
}
```

---

### 6.2 Application Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Next.js Frontend                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Chat Panel   │  │ Live Preview │  │ Code View │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└────────────┬────────────────────────────────────────┘
             │
             │ WebSocket + REST API
             │
┌────────────▼────────────────────────────────────────┐
│              API Gateway (FastAPI)                   │
│  ┌─────────────────────────────────────────────┐   │
│  │    PM Agent Interface Layer                 │   │
│  │  - Message handling                         │   │
│  │  - Session management                       │   │
│  │  - Real-time event streaming                │   │
│  └─────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────┘
             │
             │ Protocol Omega
             │
┌────────────▼────────────────────────────────────────┐
│          PM Agent (EXEC-001)                         │
│  - Vibe capture                                     │
│  - Requirements translation                          │
│  - Feature contract generation                       │
└────────────┬────────────────────────────────────────┘
             │
             │ Protocol Alpha
             │
┌────────────▼────────────────────────────────────────┐
│          CEO Agent (EXEC-002)                        │
│  - Mission orchestration                             │
│  - Agent coordination                                │
│  - Quality oversight                                 │
└────────────┬────────────────────────────────────────┘
             │
             │ Protocols Beta/Delta/Sigma
             │
┌────────────▼────────────────────────────────────────┐
│    35-Agent Refinery Ecosystem                       │
│  (Support Ring + 4 Pods)                            │
└──────────────────────────────────────────────────────┘
```

---

### 6.3 WebSocket Event Schema

**Client → Server Events:**
```typescript
// User sends a message
{
  type: 'user_message',
  content: string,
  sessionId: string,
  timestamp: Date
}

// User requests code view
{
  type: 'request_code',
  files?: string[],
  sessionId: string
}

// User action in preview
{
  type: 'preview_interaction',
  action: 'click' | 'input' | 'navigate',
  target: string,
  sessionId: string
}
```

**Server → Client Events:**
```typescript
// PM Agent response
{
  type: 'pm_response',
  content: string,
  attachments?: Array<{
    type: 'mockup' | 'code' | 'file',
    data: any
  }>,
  actions?: Array<{
    label: string,
    actionId: string
  }>,
  timestamp: Date
}

// Agent activity update
{
  type: 'agent_activity',
  agentId: string,
  agentName: string,
  status: 'active' | 'idle' | 'error',
  currentTask: string,
  progress: number
}

// Code file update
{
  type: 'file_update',
  path: string,
  content: string,
  action: 'create' | 'update' | 'delete'
}

// Preview refresh
{
  type: 'preview_refresh',
  url: string,
  reason: string
}

// System notification
{
  type: 'notification',
  level: 'info' | 'success' | 'warning' | 'error',
  title: string,
  message: string,
  dismissible: boolean
}
```

---

### 6.4 API Endpoints

```typescript
// REST API
GET    /api/projects                    // List user's projects
GET    /api/projects/:id                // Get project details
POST   /api/projects                    // Create new project
PATCH  /api/projects/:id                // Update project
DELETE /api/projects/:id                // Delete project

GET    /api/projects/:id/files          // Get project file tree
GET    /api/projects/:id/files/:path    // Get file content
POST   /api/projects/:id/files          // Create new file
PATCH  /api/projects/:id/files/:path    // Update file
DELETE /api/projects/:id/files/:path    // Delete file

GET    /api/projects/:id/preview        // Get preview URL
GET    /api/projects/:id/logs           // Get project logs
GET    /api/projects/:id/agents         // Get active agents

POST   /api/chat/message                // Send message to PM Agent
GET    /api/chat/history/:sessionId     // Get chat history

GET    /api/templates                   // Get project templates
GET    /api/templates/:id               // Get template details

GET    /api/user/profile                // Get user profile
PATCH  /api/user/profile                // Update profile
GET    /api/user/usage                  // Get usage statistics
```

---

### 6.5 Live Preview Implementation

**Preview Container Architecture:**

```typescript
// Frontend Preview Component
function LivePreview({ projectId }: { projectId: string }) {
  const [previewUrl, setPreviewUrl] = useState('')
  const iframeRef = useRef<HTMLIFrameElement>(null)
  
  useEffect(() => {
    // Get unique preview URL for this project
    fetch(`/api/projects/${projectId}/preview`)
      .then(res => res.json())
      .then(data => setPreviewUrl(data.url))
      
    // Listen for refresh events
    socket.on('preview_refresh', ({ url, reason }) => {
      if (iframeRef.current) {
        iframeRef.current.src = url
      }
      toast.info(`Preview updated: ${reason}`)
    })
  }, [projectId])
  
  return (
    <div className="relative w-full h-full">
      <iframe
        ref={iframeRef}
        src={previewUrl}
        className="w-full h-full border-0"
        sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
      />
      
      {/* Preview Controls Overlay */}
      <div className="absolute top-4 right-4 flex gap-2">
        <button onClick={() => window.open(previewUrl, '_blank')}>
          🔗 Open in New Tab
        </button>
        <select onChange={(e) => setDeviceMode(e.target.value)}>
          <option value="desktop">Desktop</option>
          <option value="tablet">Tablet</option>
          <option value="mobile">Mobile</option>
        </select>
      </div>
    </div>
  )
}
```

**Backend Preview Server:**
```python
# Each project gets isolated preview server
async def create_preview_server(project_id: str):
    """Create isolated preview environment for project"""
    
    # Allocate port
    port = allocate_port(project_id)
    
    # Start container with hot-reload
    await docker_client.run(
        image="node:20-alpine",
        command=f"npm run dev -- --port {port}",
        volumes={
            f"./projects/{project_id}": "/app"
        },
        environment={
            "NODE_ENV": "development",
            "VITE_HMR_ENABLE": "true"
        },
        ports={f"{port}": port},
        name=f"preview-{project_id}"
    )
    
    # Generate secure preview URL
    preview_url = f"https://{project_id}.preview.refinery.dev"
    
    # Setup reverse proxy
    await nginx.add_proxy(
        domain=preview_url,
        target=f"http://localhost:{port}"
    )
    
    return preview_url
```

---

## 7. ADVANCED FEATURES

### 7.1 Multi-Language Code Switching

**Feature:** Users can view the same logic implemented in different languages

```
User: "Show me this authentication logic in both Python and Node.js"

[Split view appears]

┌──────────────────────┬──────────────────────┐
│   Python (FastAPI)   │   Node.js (Express)  │
├──────────────────────┼──────────────────────┤
│ @app.post("/login")  │ app.post('/login',   │
│ async def login(     │   async (req, res) =>│
│   credentials: Login │   {                  │
│ ):                   │   const { username,  │
│   user = await       │     password } = req │
│     authenticate(    │     .body            │
│     credentials.user │   const user = await │
│     credentials.pass │     authenticate(    │
│   )                  │     username,        │
│   return create_token│     password)        │
│     (user)           │   res.json(          │
│                      │     createToken(user)│
│                      │   )                  │
└──────────────────────┴──────────────────────┘

PM Agent: Both implementations use the same LogicNode 
structure. Would you like to see C# or Go versions too?
```

---

### 7.2 Visual Logic Flow

**Feature:** Interactive visualization of application logic

```typescript
// User clicks "Show Logic Flow" button

<div className="logic-flow-viewer">
  {/* D3.js powered logic graph */}
  <LogicGraph>
    <Node id="user_input" type="entry">
      User Login Form
    </Node>
    ↓
    <Node id="validation" type="process">
      Validate Credentials
    </Node>
    ↓
    <Branch>
      <Path condition="valid">
        <Node id="auth" type="process">
          Authenticate User
        </Node>
        ↓
        <Node id="token" type="process">
          Generate JWT
        </Node>
        ↓
        <Node id="success" type="exit">
          Return 200 + Token
        </Node>
      </Path>
      
      <Path condition="invalid">
        <Node id="error" type="exit">
          Return 401 Error
        </Node>
      </Path>
    </Branch>
  </LogicGraph>
</div>
```

Clicking any node shows:
- Source code for that logic
- Which agents implemented it
- Test coverage
- Performance metrics

---

### 7.3 Template Marketplace

**Feature:** Community-contributed project templates

```
[Template Gallery View]

┌─────────────────────────────────────────────────┐
│  🔥 Featured Templates                          │
├─────────────────────────────────────────────────┤
│                                                  │
│  [🛍️ E-Commerce]  [📊 Analytics]  [🎮 Game]   │
│   Full Stack      Dashboard        Phaser.js    │
│   ⭐ 4.8          ⭐ 4.6           ⭐ 4.9       │
│   2.3k uses       1.8k uses        956 uses     │
│                                                  │
│  [🔐 Auth System] [📱 Mobile App] [🤖 ML API]  │
│   JWT + OAuth     React Native    FastAPI       │
│   ⭐ 4.9          ⭐ 4.5           ⭐ 4.7       │
│   3.1k uses       1.2k uses        734 uses     │
│                                                  │
├─────────────────────────────────────────────────┤
│  🔍 Search templates...                         │
│  [Filter: All Languages ▼] [Sort: Popular ▼]   │
└─────────────────────────────────────────────────┘
```

Clicking a template shows:
- Preview/screenshot
- Tech stack details
- Included features
- Customization options
- User reviews

---

### 7.4 AI-Powered Code Explanation

**Feature:** Users can ask questions about any part of the generated code

```
[User right-clicks on code block in Code View]

┌─────────────────────────────────┐
│ ✨ Ask about this code          │
│ 📝 Add comment                  │
│ 🔀 Show alternatives            │
│ 🧪 Generate tests               │
│ 📊 Show performance             │
└─────────────────────────────────┘

[User selects "Ask about this code"]

PM Agent: This code handles user authentication using JWT. 
Here's what's happening:

1️⃣ Takes username/password from request
2️⃣ Looks up user in database
3️⃣ Verifies password hash
4️⃣ Creates a JWT token with user info
5️⃣ Returns token to client

The token expires in 24 hours and includes the user's 
ID and permissions.

Would you like me to:
[ ] Add refresh token support
[ ] Implement 2FA
[ ] Add rate limiting
```

---

### 7.5 Collaborative Features (Future)

**Feature:** Multiple users working on same project

```
[Top bar shows collaborators]

👤 You  👤 Sarah  👤 Mike (viewing)

[Live cursors in code editor]
[Real-time file tree updates]
[Shared chat with PM Agent]

PM Agent: Sarah just added the payment integration. 
Mike is currently reviewing the checkout flow.

Would you like me to update you on their changes?
```

---

## 8. MOBILE EXPERIENCE

### 8.1 Mobile-First Chat Interface

On mobile devices (< 768px), the interface switches to a single-panel view:

```
┌─────────────────────────────┐
│ [☰]  Refinery  [⋮]         │ ← Header
├─────────────────────────────┤
│                             │
│  [Chat Messages]            │ ← Full height
│                             │
│  PM Agent: Building...      │
│                             │
│  [Input box]                │
│  [📎] [🎤] [Send]           │
│                             │
├─────────────────────────────┤
│ [Code] [Preview] [Agents]   │ ← Bottom tabs
└─────────────────────────────┘
```

**Swipe gestures:**
- Swipe left: View code
- Swipe right: View preview
- Pull down: Refresh
- Long press message: Additional actions

---

### 8.2 Mobile Code Editing

Uses mobile-optimized Monaco editor:
- Syntax highlighting (limited)
- Autocomplete suggestions
- Touch-friendly scrolling
- Keyboard shortcuts toolbar
- Read-only by default (can enable editing)

---

## 9. ACCESSIBILITY

### 9.1 WCAG 2.1 AA Compliance

**Keyboard Navigation:**
```typescript
// Global keyboard shortcuts
{
  'Cmd/Ctrl + K': 'Open command palette',
  'Cmd/Ctrl + /': 'Toggle sidebar',
  'Cmd/Ctrl + Enter': 'Send message',
  'Cmd/Ctrl + B': 'Toggle code view',
  'Cmd/Ctrl + P': 'Toggle preview',
  'Esc': 'Close modals',
  'Tab': 'Navigate between elements',
  'Shift + Tab': 'Navigate backwards'
}
```

**Screen Reader Support:**
```typescript
// ARIA labels throughout
<button 
  aria-label="Send message to PM Agent"
  onClick={sendMessage}
>
  Send
</button>

<div 
  role="log" 
  aria-live="polite" 
  aria-atomic="false"
>
  {chatMessages.map(msg => (
    <div key={msg.id} aria-label={`Message from ${msg.role}`}>
      {msg.content}
    </div>
  ))}
</div>

// Announce agent activity
<div role="status" aria-live="polite">
  {activeAgent && `${activeAgent.name} is now ${activeAgent.task}`}
</div>
```

**High Contrast Mode:**
```css
@media (prefers-contrast: high) {
  :root {
    --bg-primary: #000000;
    --text-primary: #ffffff;
    --border: #ffffff;
  }
}
```

---

### 9.2 Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 10. PERFORMANCE OPTIMIZATION

### 10.1 Frontend Performance

**Code Splitting:**
```typescript
// Lazy load heavy components
const CodeEditor = lazy(() => import('./components/CodeEditor'))
const LogicGraph = lazy(() => import('./components/LogicGraph'))
const TemplateGallery = lazy(() => import('./components/TemplateGallery'))

// Route-based splitting
const routes = [
  { path: '/dashboard', component: lazy(() => import('./pages/Dashboard')) },
  { path: '/project/:id', component: lazy(() => import('./pages/Project')) },
]
```

**Virtual Scrolling:**
```typescript
// For long chat histories and file trees
import { FixedSizeList } from 'react-window'

<FixedSizeList
  height={600}
  itemCount={chatMessages.length}
  itemSize={80}
  width="100%"
>
  {({ index, style }) => (
    <ChatMessage 
      message={chatMessages[index]} 
      style={style}
    />
  )}
</FixedSizeList>
```

**Image Optimization:**
```typescript
// Next.js Image component for mockups and templates
import Image from 'next/image'

<Image
  src={mockupUrl}
  alt="UI mockup"
  width={800}
  height={600}
  placeholder="blur"
  loading="lazy"
/>
```

---

### 10.2 WebSocket Optimization

**Message Batching:**
```typescript
// Batch multiple agent updates into single message
const messageBatcher = new MessageBatcher({
  maxBatchSize: 10,
  maxWaitTime: 100, // ms
  
  onBatch: (messages) => {
    socket.emit('batch_update', messages)
  }
})

// Usage
messageBatcher.add({
  type: 'agent_activity',
  data: agentStatus
})
```

**Connection Resilience:**
```typescript
// Auto-reconnect with exponential backoff
const socket = io({
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: Infinity,
  
  transports: ['websocket', 'polling'] // Fallback
})

socket.on('disconnect', (reason) => {
  if (reason === 'io server disconnect') {
    // Server forced disconnect, manual reconnect
    socket.connect()
  }
  // Otherwise auto-reconnect
})
```

---

### 10.3 Caching Strategy

```typescript
// React Query for API data
const { data: project } = useQuery({
  queryKey: ['project', projectId],
  queryFn: () => fetchProject(projectId),
  staleTime: 5 * 60 * 1000, // 5 minutes
  cacheTime: 10 * 60 * 1000 // 10 minutes
})

// Service Worker for offline support
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
}
```

---

## 11. SECURITY

### 11.1 Authentication & Authorization

```typescript
// JWT-based auth
interface AuthToken {
  userId: string
  email: string
  permissions: string[]
  exp: number
}

// Protected API routes
app.use('/api/projects', authenticateJWT, projectRoutes)
app.use('/api/admin', authenticateJWT, requireAdmin, adminRoutes)

// WebSocket authentication
socket.on('connection', async (socket) => {
  const token = socket.handshake.auth.token
  
  try {
    const user = await verifyToken(token)
    socket.userId = user.id
    
    // Join user's private room
    socket.join(`user:${user.id}`)
    
  } catch (error) {
    socket.disconnect()
  }
})
```

---

### 11.2 Content Security Policy

```typescript
// Next.js security headers
module.exports = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'", // For Monaco Editor
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https:",
              "font-src 'self' data:",
              "connect-src 'self' wss: https:",
              "frame-src 'self' https://*.preview.refinery.dev"
            ].join('; ')
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin'
          }
        ]
      }
    ]
  }
}
```

---

### 11.3 Sandbox Isolation

```typescript
// Preview iframe sandbox
<iframe
  src={previewUrl}
  sandbox="
    allow-scripts 
    allow-same-origin 
    allow-forms 
    allow-modals
    allow-popups
  "
  // Prevent access to parent window
  referrerPolicy="no-referrer"
/>
```

---

## 12. ANALYTICS & MONITORING

### 12.1 User Activity Tracking

```typescript
// Track key user actions
const analytics = {
  trackEvent: (event: string, properties: object) => {
    // Send to analytics service
    posthog.capture(event, properties)
  }
}

// Usage
analytics.trackEvent('project_created', {
  template: 'react-typescript',
  language: 'javascript'
})

analytics.trackEvent('pm_agent_interaction', {
  type: 'feature_request',
  complexity: 'medium'
})

analytics.trackEvent('code_generated', {
  linesOfCode: 234,
  filesCreated: 5,
  duration: 45000 // ms
})
```

---

### 12.2 Error Tracking

```typescript
// Sentry integration
import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  
  // Performance monitoring
  tracesSampleRate: 0.1,
  
  // Error filtering
  beforeSend(event, hint) {
    // Don't send user cancellations as errors
    if (event.exception?.values?.[0]?.type === 'UserCancellation') {
      return null
    }
    return event
  }
})

// Usage in components
try {
  await buildProject(projectId)
} catch (error) {
  Sentry.captureException(error, {
    tags: { projectId },
    context: { user: currentUser }
  })
  
  toast.error('Build failed. Our team has been notified.')
}
```

---

### 12.3 Performance Monitoring

```typescript
// Web Vitals tracking
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'

function sendToAnalytics({ name, delta, value, id }) {
  analytics.trackEvent('web_vitals', {
    metric: name,
    value: Math.round(value),
    delta: Math.round(delta),
    id
  })
}

getCLS(sendToAnalytics)
getFID(sendToAnalytics)
getFCP(sendToAnalytics)
getLCP(sendToAnalytics)
getTTFB(sendToAnalytics)
```

---

## 13. DEPLOYMENT

### 13.1 Production Architecture

```
┌─────────────────────────────────────────────────┐
│              CDN (CloudFlare)                    │
│  - Static assets                                 │
│  - Edge caching                                  │
│  - DDoS protection                               │
└────────────┬────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────┐
│         Load Balancer (AWS ALB)                  │
│  - SSL termination                               │
│  - Health checks                                 │
│  - Auto-scaling triggers                         │
└────────────┬────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────┐
│      Next.js Frontend (Vercel/AWS)               │
│  - Server-side rendering                         │
│  - API routes                                    │
│  - WebSocket proxy                               │
└────────────┬────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────┐
│       FastAPI Backend (AWS ECS)                  │
│  - PM Agent gateway                              │
│  - Project management                            │
│  - Preview orchestration                         │
└────────────┬────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────┐
│    Holy Grail Refinery (On-Prem/AWS)            │
│  - 35 Docker containers                          │
│  - Redis Semantic Bus                            │
│  - PostgreSQL databases                          │
└──────────────────────────────────────────────────┘
```

---

### 13.2 Scaling Strategy

**Horizontal Scaling:**
- Frontend: Auto-scale Next.js instances based on traffic
- Backend: Scale FastAPI workers based on CPU/memory
- Preview Servers: Spin up/down containers per project

**Vertical Scaling:**
- Agent containers: Allocate more resources during peak
- Database: Read replicas for query performance

**Cost Optimization:**
- Idle preview containers shut down after 30 minutes
- Aggressive caching for static assets
- Lazy-load heavy components

---

## 14. FUTURE ENHANCEMENTS

### 14.1 AI Pair Programming

```
User: "I want to add a feature but I'm not sure how"

PM Agent: Let's work on it together! What would you 
like to add?

User: "Users should be able to export their data"

PM Agent: Great! I see a few options:

1. CSV export (simple, works everywhere)
2. JSON export (for developers)
3. PDF report (professional looking)

Which sounds best? Or all three?

[User selects CSV]

PM Agent: Perfect. I'll add a CSV export button. 
Where should it go?

[Shows mockup with 3 placement options]

User: "Option 2 looks good"

PM Agent: Done! The button is now in your dashboard.
Try clicking it in the preview.

[User tests, it works]

PM Agent: Awesome! Should we add a date range filter 
so users can export just recent data?
```

---

### 14.2 Voice Input

```typescript
// Voice-to-text integration
const { transcript, isListening } = useVoiceRecognition()

<button
  onClick={toggleVoiceInput}
  className={isListening ? 'recording' : ''}
>
  {isListening ? '🎤 Listening...' : '🎤 Voice Input'}
</button>

// User speaks: "Add a login page with email and password"
// Transcript appears in chat input
// User reviews and sends
```

---

### 14.3 GitHub Integration

```
PM Agent: I've completed your project! Would you like to:

[ ] Download as ZIP
[ ] Push to GitHub repo
[ ] Deploy to Vercel

[User selects GitHub]

PM Agent: I'll need access to your GitHub account.

[Authenticate with GitHub]

PM Agent: Great! Where should I push this?

[Create new repo] [Use existing repo]

[User creates new repo: "my-awesome-app"]

PM Agent: Pushing to github.com/username/my-awesome-app...

✓ Repository created
✓ Code pushed  
✓ README.md added
✓ .gitignore configured

[View on GitHub]
```

---

### 14.4 VS Code Extension

```
// Holy Grail Refinery extension for VS Code
// Brings PM Agent directly into the editor

[VS Code Side Panel]

┌─────────────────────────────┐
│  🏗️  Refinery Chat          │
├─────────────────────────────┤
│                             │
│  PM Agent: Hi! I can help   │
│  you with your code.        │
│                             │
│  [Highlight code and ask]   │
│                             │
└─────────────────────────────┘

// User highlights a function
// Right-click → "Ask Refinery"

PM Agent: This function calculates the total price.
Would you like me to:
- Add tax calculation
- Support discount codes
- Add error handling
```

---

## 15. IMPLEMENTATION ROADMAP

### Phase 1: MVP (Weeks 1-4)
- ✅ Basic chat interface with PM Agent
- ✅ Simple project creation flow
- ✅ Live preview for web projects
- ✅ Code view (read-only)
- ✅ Basic file management
- ✅ WebSocket real-time updates

### Phase 2: Core Features (Weeks 5-8)
- ✅ Template gallery
- ✅ Multi-language support
- ✅ Agent activity monitoring
- ✅ Error handling and debugging
- ✅ Mobile responsive design
- ✅ User authentication

### Phase 3: Advanced Features (Weeks 9-12)
- ✅ Code editing capabilities
- ✅ Logic flow visualization
- ✅ AI code explanations
- ✅ Performance metrics
- ✅ Template marketplace
- ✅ Collaboration features

### Phase 4: Polish & Scale (Weeks 13-16)
- ✅ Voice input
- ✅ GitHub integration
- ✅ VS Code extension
- ✅ Advanced analytics
- ✅ Performance optimization
- ✅ Production deployment

---

## 16. SUCCESS METRICS

### 16.1 User Engagement
- Time to first working preview: < 2 minutes
- Messages per session: 15-30 (conversational flow)
- Project completion rate: > 70%
- User retention (7-day): > 40%
- User retention (30-day): > 25%

### 16.2 Technical Performance
- Initial load time: < 3 seconds
- WebSocket latency: < 100ms
- Preview refresh time: < 2 seconds
- Code generation time: < 30 seconds
- Uptime: > 99.9%

### 16.3 Quality Metrics
- Generated code pass rate: > 95%
- User satisfaction (CSAT): > 4.5/5
- Bug reports per 1000 projects: < 10
- Support ticket rate: < 5%

---

## 17. COMPETITIVE DIFFERENTIATION

### vs Bolt.new
**Bolt.new:** Template-based, primarily web/React focus  
**Refinery:** True multi-language understanding (14 langs), unified LogicNodes

### vs Replit
**Replit:** Full IDE with coding required  
**Refinery:** Natural language-first, AI does the coding

### vs Lovable (GPT Engineer)
**Lovable:** Single-language focused  
**Refinery:** Cross-language semantic understanding, agent specialization

### vs Cursor/GitHub Copilot
**Cursor/Copilot:** Code completion and suggestions  
**Refinery:** Full application generation from vibe capture

---

## 18. CONCLUSION

The Holy Grail Refinery user-facing interface transforms software development from a technical skill to a conversational collaboration. By combining natural language understanding, real-time feedback, and true multi-language comprehension, we create an experience where **anyone can build anything**.

**Key Innovation:** The PM Agent acts as a highly skilled product manager and translator, capturing the user's intent (the "vibe") and orchestrating a team of 35 specialized AI agents to manifest that vision across any technology stack.

**User Promise:**
- Describe what you want in plain English
- Watch it being built in real-time
- Iterate and refine through conversation
- Get production-ready code across 14 languages

This is not another code generation tool - it's a complete software engineering organization at your fingertips.

---

## DOCUMENT METADATA

**Document ID:** 37  
**Version:** 1.0  
**Created:** February 2026  
**Owner:** Product & Frontend Team Lead  
**Dependencies:**
- Document 15: Mission Control UI (Internal Dashboard)
- Document 06: Agent Architecture
- Document 01: Product Requirements Document
- Document 07: Communication Protocols

**Status:** ✅ Complete Specification - Ready for Implementation

---

*End of User-Facing IDE Interface Specification*
