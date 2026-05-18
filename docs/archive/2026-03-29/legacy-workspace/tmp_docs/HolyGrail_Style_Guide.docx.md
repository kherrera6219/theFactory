⚗

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
HOLY GRAIL REFINERY
STYLE GUIDE & GRAPHICS DESIGN STANDARDS
Brand 
Identity  ·
  Color 
System  ·
  
Typography  ·
  
Iconography  ·
  UI 
Components  ·
  
Motion  ·
  Marketing
Version 
1.0  |
  February 
2026  |
  Confidential
The Design Vision
The Holy Grail Refinery visual identity is built on a single powerful metaphor: the ancient alchemical refinery, reimagined as a precision industrial machine. Raw ore (messy, multi-language code) enters. Pure refined gold (universal computational intent) emerges. Every visual decision reinforces this transformation narrative — from 
the color
 choices to 
the motion
 design to 
the typography
.
⚗
Refinement
Industrial precision, transformation of raw material into pure form.
⚙️
Precision
Technical exactness. Every pixel 
deliberate
. No decoration without purpose.
🔬
Clarity
Complex systems made comprehensible. Data visualization over abstraction.
⚡
Power
Performance focus. Speed communicated visually. The system is fast.
🛡️
Trust
Enterprise-grade. Calm, stable palette. 
Nothing garish or playful.
🌊
Depth
Layered dark backgrounds evoke the deep technical stack beneath the surface.
1. BRAND IDENTITY
1.1 Logo
The Holy Grail Refinery logo is the ⚗ alchemical retort symbol — universally understood as transformation and refinement. It pairs with the wordmark in two configurations.
Configuration
Usage
Minimum Size
Clear Space
Primary (Icon + Wordmark)
Default for all applications — documentation, UI headers, marketing
120px wide / 1.5in print
Equal to icon height on all sides
Icon Only
Favicon, app icon, small UI contexts, social avatars
32px / 0.4in print
Equal to icon height on all sides
Horizontal (Icon + Wordmark inline)
Header bars, page headers, email headers
200px wide / 2.5in print
Half icon height on all sides
Wordmark Only
Text contexts where icon renders poorly (e.g. plain text email)
N/A — no minimum
None required
Logo Do's and Don'ts
✅  DO
Use the logo on white, light 
gray (#
F9FAFB), or the dark Slate 
background (#
0F172A). These are the only approved backgrounds.
❌  DON'T
Place the logo on busy photography, gradients, or backgrounds with poor contrast. Never use a colored background that isn't in the approved palette.
✅  DO
Maintain the exact proportions of the original asset files. Scale uniformly.
❌  DON'T
Stretch, skew, rotate, recolor, add drop shadows, apply outlines, or modify the logo in any way. Use approved files only.
✅  DO
Use the monochrome version on colored backgrounds or in single-color print contexts.
❌  DON'T
Use the color logo on a dark background that creates insufficient contrast. Switch to the reversed (white) version instead.
1.2 Brand Voice & Personality
The HGR brand has a distinct voice. This personality must be consistent across UI copy, documentation, error messages, marketing, and agent interactions.
Trait
What It Means
Voice Example
Precise
Specific over vague. Numbers, names, and concrete outcomes — never marketing fluff.
"Extracted 47 
LogicNodes
 from 3 Python files in 8.3 seconds."  Not: "Processing complete."
Confident
Never hedges unnecessarily. The system knows what it's doing.
"Analysis complete. 3 issues found, 2 can be 
auto-resolved
."  Not: "We think we may have found some potential issues."
Human
Technical power communicated in plain language. No jargon to users.
"I'm analyzing your code now — this usually takes about 2 minutes."  Not: "Initiating Smelt-Cycle Phase 3 extraction subroutine."
Transparent
Shows its work. 
Explains
 what's happening and why.
"Flagging this for manual review — the intent is ambiguous between two patterns."  Not: Just silently failing.
Respectful
Treats the user as an expert. Never condescending, never over-explains.
"Which optimization target matters most: runtime, memory, or bundle size?"  Not: "Code optimization means making code faster or smaller!"
2. COLOR SYSTEM
2.1 Primary Brand Colors
The HGR palette is built on three primary brand colors representing the three phases of the refinery process: raw input, active transformation, and refined output.
 
 
 
 
Refinery Violet
Transform Blue
Output Teal
Energy Amber
#8B5CF6
#3B82F6
#0D9488
#F59E0B
Brand identity, primary CTAs
Interactive elements, links
Success states, completed
Warnings, in-progress
2.2 Pod Color System
Each of the four language pods has a dedicated color identity. These colors are used consistently throughout the UI, agent visualizations, charts, and all pod-specific contexts. They are not interchangeable.
 
 
 
 
Pod A — Dynamic
Pod B — Systems
Pod C — Enterprise
Pod D — Mathematical
#F97316
#71717A
#1E40AF
#0D9488
Python, JS, TypeScript, Ruby, PHP, Go
C, C++, Rust, Zig
Java, C#, Scala
R, MATLAB, Julia
⚠️ Pod colors are semantic identifiers, not decorative choices. Pod A's orange must always mean 'dynamic languages'. Never repurpose a pod color for non-pod UI elements. This consistency is how users instantly orient in the interface.
2.3 Semantic Colors
These colors carry universal meaning across all HGR interfaces. They communicate system state and cannot be used for decorative purposes.
 
 
 
 
Success Green
Warning Amber
Error Red
Info Blue
#10B981
#F59E0B
#EF4444
#3B82F6
Completed, passed, healthy
In progress, caution, near limit
Failed, error, critical alert
Informational, neutral status
2.4 UI Background & Surface Colors
HGR ships with both a light mode and a dark mode. Both modes use the same semantic structure — only the fill values change. All components must support both.
Token Name
Light Mode Value
Dark Mode Value
Usage
--
bg
-primary
#FFFFFF
#0F172A
Main app background
--
bg
-secondary
#F9FAFB
#1E293B
Cards, panels, sidebars
--
bg
-tertiary
#F3F4F6
#334155
Hover states, nested surfaces
--text-primary
#111827
#F1F5F9
Primary readable text
--text-secondary
#6B7280
#94A3B8
Captions, secondary labels
--border
#E5E7EB
#334155
Dividers, card borders
2.5 Color Usage Rules
✅  DO
Use 
violet (#
8B5CF6) for primary CTAs, key brand moments, and the most important interactive element on any given screen.
❌  DON'T
Use violet as a generic highlight or background fill. It's a power color — used sparingly so it retains its visual weight.
✅  DO
Maintain WCAG AA contrast ratios: 4.5:1 for body text, 3:1 for large text and UI elements. Test every new color combination.
❌  DON'T
Assume a color combination will be readable. Always verify contrast using a tool. Low-contrast combinations are accessibility violations.
✅  DO
Use the pod color system consistently — Pod A orange always means dynamic languages, in every context, without exception.
❌  DON'T
Repurpose pod colors for non-pod purposes. If you need orange for a different reason, find another color from the palette.
3. TYPOGRAPHY
3.1 Font Stack
HGR uses two typefaces exclusively. Inter for all UI and written content. JetBrains Mono for all code, 
LogicNode
 IDs, protocol identifiers, and technical string values.
Inter
Sans-Serif Display & UI
For: All headings, body text, UI labels, buttons, navigation, marketing copy, documentation prose.
Weights Used: 400 (
Regular)  500
 (
Medium)  600
 (
Semibold)  700
 (Bold)
CDN: fonts.googleapis.com/css2?family=
Inter:wght
@400;500;600;700
JetBrains Mono
Monospace Technical
For: All code blocks, 
LogicNode
 IDs, trace IDs, protocol names, terminal output, config values, hex colors.
Weights Used: 400 (
Regular)  600
 (Semibold) only
CDN: fonts.googleapis.com/css2?family=JetBrains+
Mono:wght
@400;600
3.2 Type Scale
All 
type
 sizes are defined as design tokens. Do not use arbitrary pixel values. Reference these tokens in code and design files.
Token
Size (rem)
Size (
px
)
Weight
Usage
--text-display-1
3.75rem
60px
700 Bold
Marketing hero headlines
--text-display-2
3rem
48px
700 Bold
Marketing section headlines
--text-h1
2.25rem
36px
700 Bold
Page titles, doc section headers
--text-h2
1.875rem
30px
600 Semibold
Section headers
--text-h3
1.5rem
24px
600 Semibold
Subsection headers, card titles
--text-h4
1.25rem
20px
600 Semibold
Small headers, table headers
--text-body-lg
1.125rem
18px
400 Regular
Lead paragraphs, intro text
--text-body
1rem
16px
400 Regular
Default body text
--text-
sm
0.875rem
14px
400 Regular
Captions, metadata, labels
--text-
xs
0.75rem
12px
400 Regular
Fine print, timestamps, badges
--text-code
0.875rem
14px
400 Mono
Inline code, IDs, protocol names
3.3 Line Height & Letter Spacing
Context
Line Height
Letter Spacing
Rationale
Display Headlines
1.1
-0.02em (tight)
Creates visual impact and tight grouping for large text
Body Headings (H1–H3)
1.2
-0.01em
Readable without appearing loose
Body Text
1.6
0 (normal)
Comfortable reading rhythm for paragraphs
Captions & Labels
1.4
0.01em (slightly open)
Distinguishes secondary text visually
Code (Mono)
1.7
0 (normal)
Extra line height aids code readability
Button Text
1.0
0.01em
Compact for UI affordance
3.4 Typography Do's and Don'ts
✅  DO
Use Inter for all UI text and prose. Use JetBrains Mono exclusively for code, IDs, hex values, protocol names, and technical tokens.
❌  DON'T
Use more than two typefaces in any single context. Never use system fonts like Arial or Helvetica as substitutes — always load Inter from CDN.
✅  DO
Respect the 
type
 scale tokens. Use --text-h2 for section headers, --text-body for paragraphs. Consistency builds visual rhythm.
❌  DON'T
Use arbitrary font sizes like 13px, 17px, or 22px that fall outside the defined scale. This breaks the visual hierarchy.
✅  DO
Use font-weight: 600 for UI element labels and 700 for headings. Semibold for emphasis within body text.
❌  DON'T
Use font-weight: 800, 900, or Black weights — they are not part of the approved type system and feel too heavy.
4. ICONOGRAPHY
4.1 Icon Library Standard
HGR uses 
Lucide
 Icons as the primary icon library — a clean, consistent open-source set with 1000+ icons in a single unified style. All icons must come from 
Lucide
 unless there is no suitable option, in which case custom icons must be created following the 
Lucide
 visual language.
Attribute
Standard
Rationale
Library
Lucide
 React (lucide-react@0.263.1+)
Consistent stroke style, tree-
shakeable
, TypeScript native
Stroke Width
1.5px default, 2px for emphasis contexts
Matches Inter font weight at body sizes
Size — Small
16px (--icon-
sm
)
Inline
 with body text, badges, dense UI
Size — Default
20px (--icon-md)
Most UI contexts: buttons, nav, labels
Size — Large
24px (--icon-lg)
Section headers, empty states, feature callouts
Size — Display
48px+ (--icon-xl)
Hero illustrations, onboarding, marketing
Color
currentColor
 — inherits from parent text color
Ensures icons always match surrounding text
Aria
aria-hidden='true' on decorative icons
Accessibility: screen readers skip decoration
4.2 System Status Icons
These icons represent HGR system states and must be used consistently. Using a different icon for these states creates ambiguity.
State
Icon (
Lucide
)
Color
Usage Context
🟢
Active / Healthy
CheckCircle
#10B981 Green
Agent running, mission in progress, system healthy
⭕
Idle / Waiting
Clock
#6B7280 Gray
Agent available, queue empty, awaiting input
🔄
Processing
Loader2
#3B82F6 Blue
Active computation, extracting, analyzing
⚠️
Warning / Caution
AlertTriangle
#F59E0B Amber
Rate limit approaching, retry in progress, degraded
❌
Error / Failed
XCircle
#EF4444 Red
Agent down, mission failed, critical alert
⏸️
Paused
PauseCircle
#8B5CF6 Violet
Mission paused, agent suspended by operator
🔒
Locked / Secured
Lock
#1E40AF Navy
Vault locked, credentials secured, read-only mode
📦
Complete
Package
#0D9488 Teal
LogicNode
 packaged, mission delivered, output ready
4.3 Agent Identity Icons
Each agent tier has a visual identity expressed through an icon and pod color. These appear in 
the Mission
 Control UI's agent status grid and all agent-related contexts.
Tier / Agent
Icon (
Lucide
)
Color
Visual Treatment
PM Agent (ARCH-001)
MessageSquare
Violet #7C3AED
Violet badge on dark background — entry point, user-facing
CEO / Grand Manager
Crown
Blue #2563EB
Blue badge — orchestration authority, mission control center
Pod A Sub-Manager
Zap
Orange #F97316
Orange badge — dynamic languages, high-energy processing
Pod B Sub-Manager
Cpu
Steel #71717A
Steel badge — systems languages, low-level power
Pod C Sub-Manager
Building2
Navy #1E40AF
Navy badge — enterprise languages, structured, formal
Pod D Sub-Manager
Calculator
Teal #0D9488
Teal badge — mathematical languages, analytical
Language Specialists
Code2
Inherited from pod
Smaller version of pod manager badge, slightly muted
Audit Agents
ShieldCheck
Green #10B981
Green shield — quality gate, verification authority
IS Agent
Database
Blue #2563EB
Blue database icon — knowledge and indexing
API Broker
Network
Amber #F59E0B
Amber network icon — traffic control, rate management
SRE / DevOps
Activity
Green #10B981
Green pulse — system health monitoring
Security Agent
Shield
Red #EF4444
Red shield — security posture, threat monitoring
5. SPACING SYSTEM
5.1 Spacing Scale
HGR uses an 8px base grid. All spacing values are multiples of 4px (half-base) with the most common units being multiples of 8px. Never use arbitrary pixel values. Reference only these tokens.
Token
Value (rem)
Value (
px
)
Primary Use
--space-0.5
0.125rem
2px
Hairline gaps, tight icon pairs
--space-1
0.25rem
4px
Inline gaps, icon-to-text separation
--space-2
0.5rem
8px
Internal card padding (compact), badge padding
--space-3
0.75rem
12px
Input padding, compact list items
--space-4
1rem
16px
Standard internal padding, list spacing
--space-6
1.5rem
24px
Card padding, section spacing, form groups
--space-8
2rem
32px
Between sections within a card
--space-12
3rem
48px
Between major page sections
--space-16
4rem
64px
Page top padding, hero spacing
--space-24
6rem
96px
Marketing section vertical rhythm
5.2 Border Radius Scale
Token
Value
Use
--radius-
sm
4px
Small chips, tight UI elements, checkboxes
--radius-md
8px
Buttons, input fields, small cards
--radius-lg
12px
Cards, panels, dropdowns
--radius-xl
16px
Large modals, drawer panels
--radius-2xl
24px
Feature cards, hero elements
--radius-full
9999px
Pills, badges, avatar circles, toggle switches
6. UI COMPONENT STANDARDS
6.1 Buttons
HGR uses four button variants. Each variant has a clear purpose. Mixing them arbitrarily undermines the visual hierarchy.
Variant
Appearance
Use Case
When to Use
When NOT to Use
Primary
bg
: #
8B5CF6 text: white border: none 
hover: #
7C3AED
Start Mission, Submit, Confirm
One per screen max. The single most important action.
Secondary or tertiary actions
Secondary
bg
: transparent 
text: #
8B5CF6 
border: #
8B5CF6 1px hover 
bg
: #
EDE9FE
Cancel, Back, Edit, View Details
Actions that matter but aren't primary
Never as the only button on a screen
Ghost
bg
: transparent 
text: #
6B7280 border: 
none
 hover 
bg
: #
F3F4F6
Tertiary actions, icon buttons, nav items
Low-emphasis actions in crowded UIs
For actions the user frequently needs
Danger
bg
: #
EF4444 text: white border: none 
hover: #
DC2626
Delete, Remove, Force Stop
Destructive or irreversible actions only
Regular workflow actions — danger implies irreversibility
Standard Button Sizing: Height 36px (compact), 40px (default), 48px (large). Horizontal padding: 16px (compact), 20px (default), 24px (large). Font-size always --text-
sm
 (14px) for compact/default, --text-body (16px) for large.
6.2 Cards
Cards are the primary container for dashboard content. All cards follow the same structural rules regardless of content.
Property
Light Mode
Dark Mode
Notes
Background
#FFFFFF
#1E293B
One level above the page background
Border
1px #E5E7EB
1px #334155
Subtle separation from background
Border Radius
--radius-lg (12px)
--radius-lg (12px)
Consistent across all card types
Shadow
--shadow-md
--shadow-xl
Slightly heavier shadow in dark mode for depth
Padding
--space-6 (24px)
--space-6 (24px)
Internal padding on all sides
Header padding
--space-4 (16px) bottom border
Same
Separates card header from body
Title font
--text-h4, font-weight: 600
Same
Consistent card title style
Hover state
translateY
(-2px), shadow-lg
Same
Subtle lift on interactive cards only
6.3 Status Badges
Badges communicate state inline. They use semantic colors and must always be accompanied by an icon for accessibility — never color alone.
Badge
Icon
Colors
Code Pattern
Active
CheckCircle
bg
 #D1FAE5, text #065F46
className
="badge badge-success"
Idle
Clock
bg
 #F3F4F6, text #374151
className
="badge badge-neutral"
Processing
Loader2 spin
bg
 #
DBEAFE, text #1E40AF
className
="badge badge-info"
Warning
AlertTriangle
bg
 #FEF3C7, text #92400E
className
="badge badge-warning"
Error
XCircle
bg
 #FEE2E2, text #991B1B
className
="badge badge-error"
Paused
PauseCircle
bg
 #EDE9FE, text #5B21B6
className
="badge badge-violet"
6.4 Progress Indicators
HGR has three types of progress indicators for different contexts. They are not interchangeable.
Type
When to Use
Visual Spec
Animation
Linear Progress Bar
Mission completion (0–100% known). 
LogicNode
 extraction progress.
Height 8px, border-radius 4px (pill). Background #E5E7EB. Fill: pod color or brand violet.
Linear easing, smooth fill. Duration matches real-time progress.
Circular Spinner
Indeterminate wait. Agent thinking. LLM call in progress.
24px diameter, 2px stroke, 
currentColor
. Use 
Lucide
 Loader2.
Continuous spin 1s linear infinite.
Step Indicator
Mission timeline (7 Smelt-Cycle phases). Onboarding flow.
Circles connected by lines. Complete=filled, Active=pulsing, Pending=outline.
Active step has pulse animation: scale 1→1.05, opacity 1→0.8, 1.5s ease-in-out infinite.
7. DATA VISUALIZATION
7.1 Chart Color Assignment
All charts and graphs in HGR follow strict color assignment rules. Colors carry meaning — they are not picked for aesthetics. The pod color system extends directly into data visualization.
Chart Color Priority Order: 1. If data represents a specific pod — use that pod's color. Always. 2. If data represents system health states — use the semantic color (green=healthy, red=error, etc.). 3. If data is a neutral metric (e.g. CPU usage, message 
count) —
 use the brand gradient: Violet → Blue → Teal. 4. If comparing multiple neutral series — use the ordered 
palette: #8B5CF6, #3B82F6, #0D9488, #F59E0B, #
EF4444. 5. Never use colors not in the HGR palette in a chart.
7.2 Chart Type Guidelines
Chart Type
Use For
Do Not Use For
Line Chart
Time-series data: message latency over time, agent CPU usage trends, 
LogicNode
 extraction rate per hour
Comparisons between discrete categories
Bar Chart
Comparing discrete items: 
LogicNodes
 per language, missions by status, DLQ depth per protocol
Time-series with dense data points
Stacked Bar
Part-to-whole over categories: protocol message breakdown per pod
More than 5 data series — becomes unreadable
Donut Chart
Simple part-to-whole: mission status breakdown, protocol usage share. Max 5 segments.
More than 6 segments; trend data; precise comparisons
Scatter Plot
Correlation: extraction time vs file size, audit pass rate vs complexity score
Single-variable distributions
Heatmap
Agent activity over time: rows=agents, columns=hours. Uses teal gradient intensity.
Non-grid data structures
Progress Ring
Single metric vs target: overall system health score, test pass rate (0–100%)
Multi-variable comparisons
7.3 Chart Anatomy Standards
Every chart in HGR must follow these anatomical rules regardless of chart type or library used (Recharts is the primary library).
Title: --text-h4, font-weight 600, top-left aligned — describes what is being shown
Subtitle / Timeframe: --text-
sm
, gray #6B7280, below title — context for the data
Axes: --text-
xs
, gray #6B7280, no bold — axis labels never compete with data
Gridlines: 1px solid #E5E7EB (light) or #334155 (dark), horizontal only — vertical gridlines add visual noise
Legends: placed below chart, --text-
sm
 — never float over data
Tooltips: dark background #1E293B, white text, 4px border-radius, show value + label + timestamp
Empty state: Illustrated empty state with explanation — never a blank chart frame
8. MOTION & ANIMATION
8.1 Motion Principles
Motion in HGR communicates system state and guides attention. It is purposeful, not decorative. All animations must have functional justification.
Principle
What It Means
Example
Purposeful
Every animation communicates something: state change, direction of flow, processing activity. Motion without meaning is deleted.
Loader spinner = 'the system is working'. Fade in = 'this content has appeared'.
Subtle
Animations should support the interface, not steal focus. The user's attention belongs 
on
 their task, not 
on
 the UI.
Cards lift 2px on hover — noticeable but not distracting.
Fast
Functional UI animations are short. Users don't wait for animations.
Transitions: 150ms–300ms. Load states may be longer.
Consistent
Same action = same animation everywhere in the app. Build a motion vocabulary.
All modal opens use the same scale + fade. All slide-ins come from the same direction.
Respectful
Always honor prefers-reduced-motion. Remove or minimize animations when the user has requested it.
@media (prefers-reduced-motion) reduces all transitions to instant.
8.2 Animation Tokens
Token
Duration
Easing
Use For
--
anim
-instant
0ms
—
prefers-reduced-motion fallback
--
anim
-fast
150ms
ease-out
Hover effects, toggle switches, button press
--
anim
-normal
250ms
ease-in-out
Dropdown opens, tooltip appears, badge state change
--
anim
-slow
350ms
cubic-
bezier
(
0.4,0,0.2,1)
Modal opens, panel slides, page transitions
--
anim
-loading
1000ms
linear, infinite
Spinner rotation
--
anim
-pulse
1500ms
ease-in-out, infinite
Active agent pulse, live indicator
--
anim
-flow
2000ms
ease-in-out, infinite
Semantic Bus message flow visualization, background data streams
8.3 Key Animation Patterns
The Smelt-Cycle Flow Animation
The mission timeline progress animation is the signature motion of HGR. It must always feel industrial and precise.
/* Smelt-Cycle Phase Transition */
.phase
-complete {
  animation: 
phaseComplete
 300ms ease-out 
forwards;
}
@keyframes 
phaseComplete
 {
  0%
   {
 background: 
var(
--color-info); transform: 
scale(
1.05)
; }
  100% 
{ background
: 
var(
--color-success); transform: 
scale(
1)
; }
}
/* Data Flow Line (Semantic Bus visualization) */
.message
-particle {
  animation: 
flowRight
 2000ms ease-in-out 
infinite;
}
@keyframes 
flowRight
 {
  0%
   {
 opacity: 0; transform: 
translateX
(
0)
; }
  20
%  {
 opacity: 1
; }
  80
%  {
 opacity: 1
; }
  100% 
{ opacity
: 0; transform: 
translateX
(
100%)
; }
}
9. LAYOUT SYSTEM
9.1 Responsive Breakpoints
Breakpoint
Range
Grid Columns
Primary Use
Mobile
320px – 640px
1 column
Single-column reading. Mission status, condensed agent list.
Tablet
641px – 1024px
2 columns
Basic dashboard. Agent grid 2-up. Side panel collapses.
Desktop
1025px – 1440px
12 columns
Full Mission Control. 5-column agent grid. Sidebar visible.
Wide
1441px+
12 columns
Extended dashboard. Chart area expands. More data visible.
9.2 Mission Control Layout Architecture
The Mission
 Control UI follows a fixed layout structure. Components must be placed within this structure and must not break it.
┌─────────────────────────────────────────────────────┐
│  TOPBAR
: Logo | Navigation | API Status | User      
│  h
: 64px, sticky
├──────────┬──────────────────────────────────────────┤
│          
│  MAIN
 CONTENT AREA                       │
│ 
SIDEBAR  │
  ┌─────────────────────────────────────┐ │
│          
│  │
  PAGE HEADER (title + 
actions)   
   │ 
│  h
: 72px
│  240
px   
│  ├
─────────────────────────────────────┤ │
│  fixed
   
│  │
                                     │ │
│          
│  │
  PRIMARY CONTENT                    │ 
│  flex
-1, scrollable
│          
│  │
  (Dashboard / Mission / 
Agents)   
  │ │
│          │  │                                     │ │
│          │  └─────────────────────────────────────┘ │
├──────────┴──────────────────────────────────────────┤
│  STATUS
 BAR: System Health | Agent Count | 
Version  │
  h: 32px
└─────────────────────────────────────────────────────┘
10. MARKETING & EXTERNAL COMMUNICATIONS
10.1 Hero Gradient
The primary marketing gradient flows from Refinery Violet through Transform Blue to Output Teal — representing the full transformation journey. This is the signature gradient and should be used for hero sections, key marketing moments, and high-impact visuals.
/* Primary Hero Gradient */
background: linear-
gradient(
135
deg, #
8B5CF6 0
%, #
3B82F6 50
%, #
0D9488 100%
);
/* Dark Mode Hero */
background: linear-
gradient(
135
deg, #
1E293B 0
%, #
0F172A 100%
);
/* Accent Gradient (CTAs on dark backgrounds) */
background: linear-
gradient(
90
deg, #
7C3AED 0
%, #
2563EB 100%
);
10.2 Marketing Typography
Element
Size
Weight
Letter Spacing
Example
Hero Display 1
60px
700 Bold
-0.02em
"Transform Code. Across 14 Languages."
Hero Display 2
48px
700 Bold
-0.02em
"The Semantic Refinery"
Section Headline
36px
700 Bold
-0.01em
"How the Smelt-Cycle Works"
Subheadline
24px
600 Semibold
0
"Pure logic, extracted from any language"
Lead Body
18px
400 Regular
0
"Stop rewriting. Start refining."
Body
16px
400 Regular
0
Standard marketing copy
Caption
14px
400 Regular
0.01em
Footnotes, legal, image captions
10.3 Social Media Asset Specifications
Platform
Format
Dimensions
Background
Typography
Twitter/X Card
PNG
1200 × 628px
Primary hero gradient (
violet→blue→teal
)
Inter Bold, white text. Logo 
top-left
. Tagline center.
LinkedIn Post
PNG
1200 × 627px
Dark hero gradient or white
Inter Bold 36px headline. Semibold 18px body.
LinkedIn Banner
PNG
1584 × 396px
Primary hero gradient
Logo left. Wordmark right. Tagline below.
Twitter/X Banner
PNG
1500 × 500px
Primary hero gradient
Logo centered or left-aligned.
App Icon
PNG
1024 × 1024px
Solid violet #8B5CF6
⚗ icon centered, white, icon-only variant
OG / Open Graph
PNG
1200 × 630px
Dark slate #0F172A
Logo 
top-left
. Feature headline. URL bottom.
Slide Deck Cover
PNG
1920 × 1080px
Primary hero gradient
Display headline, subtitle, logo, date
10.4 Presentation Deck Standards
Slide dimensions: 1920 × 1080px (16:9), never 4:3
Font stack: Inter (required — embed fonts in all exported files)
Max text per slide: 6 bullet points or 80 words — one idea per slide
Code slides: JetBrains Mono on dark slate #1E293B background
Diagrams: Use the official pod colors and agent icon set — no clip art, no stock icons
Data slides: Use recharts-style charts with HGR color system — never Excel default colors
Logo: Always top-left or bottom-right corner, never centered on a content slide
Slide footer: Slide number + 'CONFIDENTIAL' tag if deck is internal — always
11. ASSET LIBRARY STANDARDS
11.1 File Structure
/
assets
  /
logos
    
hgr
-logo-
primary.svg
          ← Vector, full color
    hgr-logo-primary@2x.png       ← Raster 2×, full color
    
hgr
-logo-
monochrome.svg
        ← Black 
version
    
hgr
-logo-
white.svg
             ← White reversed version
    
hgr
-icon-
only.svg
              ← ⚗ icon only, no wordmark
    
hgr
-logo-
horizontal.svg
        ← Header bar version
    favicon.ico                    ← 16×16, 32×32, 64×64 sizes
  /
icons
    /agents                        ← Per-agent SVG icons
    /pods                          ← Pod identity marks
    /status                        ← System state icons
    /
ui
                            ← General UI icons
  /
illustrations
    /
empty
-states                  ← no-
missions.svg
, no-
results.svg
    /onboarding                    ← step-1.svg through step-
N.svg
    /marketing                     ← hero-
bg.svg
, how-it-
works.svg
  /
backgrounds
    grid-
pattern.svg
               ← Subtle grid overlay
    dot-
pattern.svg
                ← Dot grid overlay
    flow-
animation.svg
             ← Animated data flow background
  /
design
-tokens
    
tokens.json
                    ← All CSS variables as JSON (single source of truth)
    tokens.css                     ← Generated CSS custom properties
11.2 File Format Standards
Asset Type
Primary Format
Fallback
Naming Convention
Logos & Wordmarks
SVG (vector, scalable)
PNG @
2x for environments that can't render SVG
hgr
-logo-{variant}.
svg
Icons (UI)
SVG via 
Lucide
 React
PNG @
2x for email/docs
Use 
Lucide
 component name
Custom Icons
SVG optimized (SVGO)
PNG @
2x
hgr
-icon-{name}.
svg
Illustrations
SVG (preferred) or PNG
PNG @
2x minimum
hgr-illus
-{description}.
svg
Background Patterns
SVG or CSS only
PNG @
2x for email
hgr-bg
-{name}.
svg
Photos
WebP
 (primary)
JPEG @
2x fallback
hgr
-
photo-{
description
}.
webp
Social Media Assets
PNG @
2x (1200px+ wide)
—
hgr-social-{platform}-{variant}.png
11.3 Design Token Single Source of Truth
All design decisions — colors, spacing, typography, shadows, radius — live in /assets/design-tokens/
tokens.json
. This file generates CSS custom properties, TypeScript constants, and Tailwind config. Never hard-code a value that should come from a token.
// 
tokens.json
 (excerpt)
{
  "color
": {
    "brand
": {
      "violet":   
   {
 "value"
: "#
8B5CF6", "comment": "Primary brand. Use for primary CTAs.
" }
,
      "blue":     
   {
 "value"
: "#
3B82F6", "comment": "Interactive elements, links.
" }
,
      "teal":     
   {
 "value"
: "#
0D9488", "comment": "Output, success, Pod D.
" }
    },
    "pod
": {
      "a-dynamic":
   {
 "value"
: "#
F97316", "comment": "Python, JS, TS, Ruby, PHP, Go
" }
,
      "b-systems":
   {
 "value"
: "#
71717A", "comment": "C, C++, Rust, Zig
" }
,
      "c-enterprise
":{
 "value": "#1E40AF", "comment": "Java, C#, Scala
" }
,
      "d-math":   
   {
 "value"
: "#
0D9488", "comment": "R, MATLAB, Julia
" }
    }
  },
  "spacing
": {
    "4": 
{ "
value": "1rem", "comment": "16
px —
 standard padding
" }
,
    "6": 
{ "
value": "1.5rem", "comment": "24px — card padding
" }
  }
}
12. ACCESSIBILITY STANDARDS
12.1 WCAG 2.1 AA Compliance (Mandatory)
All HGR interfaces must meet WCAG 2.1 Level AA. This is not optional — enterprise customers and defense sector clients require it. Every new component is verified before merge.
Requirement
Standard
How to Verify
Text Contrast — Body
4.5:1 minimum ratio
Use 
Colour
 Contrast 
Analyser
 or 
WebAIM
 Contrast Checker
Text Contrast — Large Text (18px+)
3:1 minimum
Same tools — verify at actual rendered sizes
UI Component Contrast
3:1 against adjacent color
Verify button borders, input borders, focus rings
Focus Indicators
Visible on all interactive elements, 3:1 contrast
Tab through every interactive element in both modes
Color Alone
Never used as sole conveyor of information
Status badges must have icon + color + text label
Keyboard Navigation
All 
functionality
 reachable via keyboard
Navigate entire app without mouse
Screen Reader
Meaningful aria-labels on all interactive elements
Test with NVDA/
VoiceOver
 — hear what is announced
Motion
prefers-reduced-motion honored throughout
Enable reduced motion in OS settings, verify app respects it
12.2 Approved Color Combinations
These combinations have been verified to meet WCAG AA. Use only approved pairings for text on backgrounds.
Text Color
Background
Ratio
Status
Use For
#FFFFFF White
#8B5CF6 Violet
5.2:1
✅ AA Pass
Primary button text
#FFFFFF White
#2563EB Blue
5.9:1
✅ AA Pass
Secondary button, info badge
#FFFFFF White
#0D9488 Teal
4.7:1
✅ AA Pass
Success badges, Pod D
#FFFFFF White
#EF4444 Red
4.5:1
✅ AA Pass
Error state, danger buttons
#FFFFFF White
#1E40AF Navy
8.1:1
✅ AAA Pass
Enterprise Pod C, heavy headers
#111827 Dark
#FFFFFF White
16.1:1
✅ AAA Pass
Primary body text
#374151 Gray
#F9FAFB Light
7.5:1
✅ AAA Pass
Secondary text on light 
bg
#F1F5F9 Light
#0F172A Dark
14.4:1
✅ AAA Pass
Dark mode body text
#94A3B8 Muted
#1E293B Slate
4.6:1
✅ AA Pass
Dark mode secondary text
#F59E0B Amber
#1E293B Slate
5.1:1
✅ AA Pass
Warning text on dark 
bg
 only
⚗
This style guide is a living document. All visual decisions must reference these standards.
Deviations require design review and must be documented in an ADR before implementation.
Holy Grail Refinery Style Guide 
v1.0  ·
  Feb 
2026  ·
  
Confidential  ·
  Kevin Herrera
