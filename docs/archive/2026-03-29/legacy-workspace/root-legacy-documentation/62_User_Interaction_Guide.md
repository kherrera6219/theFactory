# DOCUMENT 62: USER INTERACTION GUIDE
## Holy Grail Refinery - UI/UX Patterns & Interaction Design

**Document ID:** 62  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training (Supplemental)  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document defines **user interaction patterns, UI/UX guidelines, and conversational design** for the Holy Grail Refinery system. It specifies how users interact with the PM Agent and Mission Control interface to accomplish their goals.

**Design Philosophy:**
- 🗣️ **Conversational First** - Natural language interaction with PM Agent
- 👁️ **Visual Feedback** - Real-time progress visualization
- 🎯 **Goal-Oriented** - Interfaces organized around user tasks
- 🚀 **Progressive Disclosure** - Simple by default, powerful when needed
- ♿ **Accessible** - WCAG 2.1 AA compliance

---

## TABLE OF CONTENTS

1. [Conversational Interface Patterns](#1-conversational-interface-patterns)
2. [Visual Design System](#2-visual-design-system)
3. [Mission Submission Flow](#3-mission-submission-flow)
4. [Progress Visualization](#4-progress-visualization)
5. [Results Exploration](#5-results-exploration)
6. [Error Handling & Recovery](#6-error-handling--recovery)
7. [Accessibility Guidelines](#7-accessibility-guidelines)
8. [Mobile & Responsive Design](#8-mobile--responsive-design)

---

## 1. CONVERSATIONAL INTERFACE PATTERNS

### 1.1 PM Agent Personality

**Voice & Tone:**
- Professional but friendly
- Proactive and helpful
- Clear and concise
- Celebrates successes
- Honest about limitations

**Example Interactions:**

✅ **Good:**
```
PM Agent: I'll analyze your Python web scraper for optimization 
opportunities. This will take about 8 minutes.

I'll specifically look for:
• List operation inefficiencies
• Redundant iterations
• I/O bottlenecks

[Start Analysis] [Customize Scope]
```

❌ **Bad:**
```
PM Agent: I have initiated the analysis subroutine via Protocol Alpha 
delegation to the CEO Agent who will decompose the task into...
[Technical jargon continues]
```

### 1.2 Conversational Patterns

**Pattern 1: Requirement Gathering**

```
User: "I want to optimize my code"

PM Agent: I can help with that! To give you the best recommendations, 
I have a few questions:

1. What programming language is your code in?
   [Python] [JavaScript] [Java] [Other...]

2. What's your main concern?
   [Speed] [Memory Usage] [Code Quality] [All of the above]

3. Do you have any specific performance targets?
   [Yes, let me specify] [No, just make it faster]
```

**Pattern 2: Clarifying Questions**

```
User: "Analyze this code"

PM Agent: I'll analyze your code! I see you've uploaded Python files.

Quick question: Are you more interested in:
• Finding bugs and quality issues
• Optimizing for performance
• Understanding what the code does
• Comparing with another implementation

This helps me focus the analysis on what matters most to you.

[Quality] [Performance] [Understanding] [Comparison]
```

**Pattern 3: Progress Updates**

```
PM Agent: Great! Analysis is underway.

✓ Files parsed successfully (500 lines of Python)
⏳ Python Specialist extracting patterns... 47%
⏳ Audit Agent will verify findings next

Estimated completion: 4 minutes

[View Detailed Progress] [Minimize]
```

**Pattern 4: Results Delivery**

```
PM Agent: ✓ Analysis complete! Here's what I found:

📊 Overall Code Quality: 7.5/10

🔍 Key Findings:
• 5 optimization opportunities (could be 3x faster)
• 2 potential bugs detected
• 47 patterns successfully extracted

🎯 Top Recommendation:
Your nested loops in scraper.py could be replaced with list 
comprehensions for 3x speedup.

[View All Details] [Implement Suggestions] [Export Report]
```

### 1.3 Question Types

**Multiple Choice (for bounded options):**
```
What type of analysis do you need?
○ Performance Optimization
○ Quality Audit
○ Cross-Language Comparison
○ Legacy Code Documentation
```

**Slider (for numerical values):**
```
How aggressive should optimizations be?

Conservative ←──────●────→ Aggressive
(maintains readability)    (maximum performance)
```

**Text Input (for open-ended):**
```
Describe what your code does (optional but helpful):
┌─────────────────────────────────────────────┐
│ This script scrapes product data from...    │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 2. VISUAL DESIGN SYSTEM

### 2.1 Color Palette

**Primary Colors:**
- **Brand Blue:** `#2563EB` - Primary actions, links
- **Success Green:** `#10B981` - Completed states, positive feedback
- **Warning Amber:** `#F59E0B` - Alerts, caution states
- **Error Red:** `#EF4444` - Errors, failures
- **Neutral Gray:** `#6B7280` - Body text, secondary elements

**Agent Status Colors:**
- **Active:** `#10B981` (Green) - Agent currently processing
- **Idle:** `#6B7280` (Gray) - Agent waiting for work
- **Error:** `#EF4444` (Red) - Agent encountered error
- **Paused:** `#F59E0B` (Amber) - Agent paused

### 2.2 Typography

**Font Stack:**
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
```

**Type Scale:**
- **H1:** 2.5rem (40px) - Page titles
- **H2:** 2rem (32px) - Section headers
- **H3:** 1.5rem (24px) - Subsection headers
- **Body:** 1rem (16px) - Default text
- **Small:** 0.875rem (14px) - Captions, metadata
- **Code:** 0.875rem (14px) - Code snippets, LogicNode IDs

### 2.3 Spacing System

```
--space-1: 0.25rem (4px)
--space-2: 0.5rem (8px)
--space-3: 0.75rem (12px)
--space-4: 1rem (16px)
--space-6: 1.5rem (24px)
--space-8: 2rem (32px)
--space-12: 3rem (48px)
```

### 2.4 Component Library

**Button Variants:**

```
Primary Button:
┌─────────────────────┐
│  Start Analysis     │  ← Blue background, white text
└─────────────────────┘

Secondary Button:
┌─────────────────────┐
│  Cancel             │  ← White background, blue text, blue border
└─────────────────────┘

Danger Button:
┌─────────────────────┐
│  Delete Mission     │  ← Red background, white text
└─────────────────────┘
```

**Cards:**
```
┌──────────────────────────────────────────┐
│ Mission #m4a8f9b2                        │
│                                          │
│ Status: Processing ⏳                    │
│ Progress: 47%                            │
│ ████████████░░░░░░░░░░░░                 │
│                                          │
│ Started: 2 minutes ago                   │
│ Estimated: 4 minutes remaining           │
│                                          │
│ [View Details] [Cancel]                  │
└──────────────────────────────────────────┘
```

---

## 3. MISSION SUBMISSION FLOW

### 3.1 Step-by-Step Wizard

**Step 1: Mission Type Selection**

```
┌─────────────────────────────────────────────────────────┐
│  What would you like to do?                             │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  📊 Analyze      │  │  ⚡ Optimize     │            │
│  │                  │  │                  │            │
│  │  Understand code │  │  Make code       │            │
│  │  quality and     │  │  faster and more │            │
│  │  patterns        │  │  efficient       │            │
│  └──────────────────┘  └──────────────────┘            │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │  🔄 Compare      │  │  📚 Document     │            │
│  │                  │  │                  │            │
│  │  Check if two    │  │  Generate docs   │            │
│  │  implementations │  │  from legacy     │            │
│  │  match           │  │  code            │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

**Step 2: Source Selection**

```
┌─────────────────────────────────────────────────────────┐
│  How would you like to provide your code?               │
│                                                          │
│  ┌─────────────────────────────────────────────┐       │
│  │  📁 Upload Files                             │       │
│  │                                              │       │
│  │  Drag and drop files here or click to browse│       │
│  │  Supports: .py .js .java .cpp .rb .php      │       │
│  │  Max size: 100MB                             │       │
│  └─────────────────────────────────────────────┘       │
│                                                          │
│  ┌─────────────────────────────────────────────┐       │
│  │  🔗 GitHub Repository                        │       │
│  │                                              │       │
│  │  https://github.com/user/repo               │       │
│  │  Branch: [main ▼]  Path: [/ ▼]              │       │
│  └─────────────────────────────────────────────┘       │
│                                                          │
│  ┌─────────────────────────────────────────────┐       │
│  │  ✏️ Paste Code                               │       │
│  │                                              │       │
│  │  Paste your code directly into the editor   │       │
│  └─────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

**Step 3: Configuration**

```
┌─────────────────────────────────────────────────────────┐
│  Optimization Goals (select all that apply)             │
│                                                          │
│  ☑ Speed - Make code run faster                         │
│  ☑ Memory - Reduce memory usage                         │
│  ☐ Readability - Improve code clarity                   │
│  ☐ Maintainability - Make code easier to change         │
│                                                          │
│  ─────────────────────────────────────────────          │
│                                                          │
│  Focus Areas (optional)                                 │
│                                                          │
│  ☑ List operations                                      │
│  ☑ I/O operations                                       │
│  ☐ String manipulation                                  │
│  ☐ Async patterns                                       │
│                                                          │
│  ─────────────────────────────────────────────          │
│                                                          │
│  Additional Notes (optional)                            │
│  ┌────────────────────────────────────────────┐        │
│  │ This code processes customer data and...   │        │
│  └────────────────────────────────────────────┘        │
│                                                          │
│              [Back]  [Submit Mission]                    │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Quick Submit (Expert Mode)

**For experienced users:**

```
┌─────────────────────────────────────────────────────────┐
│  New Mission                                             │
│                                                          │
│  [Analyze ▼] my [Python ▼] code for [performance ▼]    │
│                                                          │
│  📁 Drop files here or [Browse]                         │
│                                                          │
│  [Submit] [Advanced Options]                            │
└─────────────────────────────────────────────────────────┘
```

---

## 4. PROGRESS VISUALIZATION

### 4.1 Mission Status Card

```
┌──────────────────────────────────────────────────────────┐
│  Mission #m4a8f9b2 - Python Web Scraper Analysis         │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  Status: Processing ⏳                                    │
│  Progress: 47% ████████████░░░░░░░░░░░░                  │
│                                                           │
│  Current Phase: Extracting LogicNodes                    │
│  ⏱️ Started: 4 minutes ago                                │
│  ⏰ Estimated: 4 minutes remaining                        │
│                                                           │
│  Active Agents:                                          │
│  • PM Agent: Monitoring                                  │
│  • CEO Agent: Coordinating                               │
│  • Python Specialist: Extracting (47%)                   │
│  • Audit Agent: Waiting                                  │
│                                                           │
│  [View Detailed Logs] [Cancel Mission]                   │
└──────────────────────────────────────────────────────────┘
```

### 4.2 Agent Activity Visualization

```
┌──────────────────────────────────────────────────────────┐
│  Agent Activity                                           │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  PM-001        ● Active   │ Monitoring mission            │
│  CEO-001       ● Active   │ Coordinating work             │
│  AGENT-PY-001  ● Active   │ Extracting patterns... 47%    │
│  AUDIT-001     ○ Idle     │ Waiting for work              │
│  MANAGER-A-001 ○ Idle     │ Standing by                   │
│                                                           │
│  ● Active  ○ Idle  ⚠️ Error  ⏸️ Paused                     │
└──────────────────────────────────────────────────────────┘
```

### 4.3 Timeline Visualization

```
┌──────────────────────────────────────────────────────────┐
│  Mission Timeline                                         │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  ✓ Mission Created          [14:30:00]                   │
│  ✓ PM Agent accepted        [14:30:02]                   │
│  ✓ CEO Agent decomposed     [14:30:15]                   │
│  ⏳ Python Specialist        [14:32:00] - In progress     │
│  ⏹️ Audit verification       [Pending]                    │
│  ⏹️ Results delivery         [Pending]                    │
│                                                           │
│  ──●──────────●──────────●────────●─────────────────────  │
│  Start      Accepted   Analyzing  Audit    Complete      │
└──────────────────────────────────────────────────────────┘
```

---

## 5. RESULTS EXPLORATION

### 5.1 Results Dashboard

```
┌──────────────────────────────────────────────────────────┐
│  Results: Python Web Scraper Analysis                    │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  📊 Summary                                               │
│  ───────                                                  │
│  • LogicNodes Extracted: 47                              │
│  • Code Quality Score: 7.5/10                            │
│  • Optimization Opportunities: 5                         │
│  • Verification Pass Rate: 99.2%                         │
│                                                           │
│  ⚡ Top Recommendations                                   │
│  ────────────────────                                     │
│  1. Replace nested loops with list comprehension         │
│     Location: scraper.py:45-52                           │
│     Impact: 3x faster ⭐⭐⭐                               │
│     [View Details] [Apply Fix]                           │
│                                                           │
│  2. Use generator for large datasets                     │
│     Location: scraper.py:78-85                           │
│     Impact: 50% less memory ⭐⭐                          │
│     [View Details] [Apply Fix]                           │
│                                                           │
│  [View All 5 Recommendations]                            │
│  [Export Report] [Download LogicNodes]                   │
└──────────────────────────────────────────────────────────┘
```

### 5.2 LogicNode Viewer

```
┌──────────────────────────────────────────────────────────┐
│  LogicNode: list_filter                                  │
│  ID: ln-abc123xyz                                        │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  Intent:                                                 │
│  Remove elements from collection that don't satisfy      │
│  predicate function                                      │
│                                                           │
│  Source Code (scraper.py:45):                            │
│  ┌────────────────────────────────────────────────┐     │
│  │ items = [x for x in data if x['price'] > 100] │     │
│  └────────────────────────────────────────────────┘     │
│                                                           │
│  Inputs:                                                 │
│  • collection: List[T]                                   │
│  • predicate: Callable[[T], bool]                        │
│                                                           │
│  Outputs:                                                │
│  • filtered: List[T]                                     │
│                                                           │
│  Verification:                                           │
│  Tests Passed: 999/1000 ✓                                │
│  Confidence: 95%                                         │
│                                                           │
│  Equivalent In:                                          │
│  • JavaScript: items.filter(x => x.price > 100)         │
│  • Ruby: items.select { |x| x['price'] > 100 }          │
│                                                           │
│  [View Full Details] [Export]                            │
└──────────────────────────────────────────────────────────┘
```

### 5.3 Code Comparison View

```
┌──────────────────────────────────────────────────────────┐
│  Before & After Comparison                                │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  Before (Current)         │  After (Optimized)            │
│  ─────────────────────    │  ──────────────────           │
│  for i in range(len(items)):│  result = [x for x in items│
│    for j in range(len(items)):│  if x > threshold]      │
│      if items[i] == items[j]:│                           │
│        result.append(items[i])│                          │
│                            │                              │
│  Complexity: O(n²)         │  Complexity: O(n)            │
│  Time: 450ms               │  Time: 150ms (3x faster)     │
│                            │                              │
│  [Copy Before] [Copy After] [Apply Change]               │
└──────────────────────────────────────────────────────────┘
```

---

## 6. ERROR HANDLING & RECOVERY

### 6.1 Error Message Patterns

**Syntax Error:**
```
┌──────────────────────────────────────────────────────────┐
│  ⚠️ Syntax Error Detected                                 │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  I found a syntax error in your Python code:             │
│                                                           │
│  File: scraper.py                                        │
│  Line: 42                                                │
│  Error: Missing closing parenthesis                      │
│                                                           │
│  Code:                                                   │
│  ┌────────────────────────────────────────────────┐     │
│  │ 41: def fetch_data(url:                        │     │
│  │ 42:     response = requests.get(url            │ ←   │
│  │ 43:     return response.json()                 │     │
│  └────────────────────────────────────────────────┘     │
│                                                           │
│  Suggestion:                                             │
│  Add closing ) on line 42:                               │
│  response = requests.get(url)                            │
│                                                           │
│  [Fix Automatically] [Edit Code] [Ignore]                │
└──────────────────────────────────────────────────────────┘
```

**Mission Failed:**
```
┌──────────────────────────────────────────────────────────┐
│  ❌ Mission Failed                                        │
│  ──────────────────────────────────────────────────────  │
│                                                           │
│  Mission #m4a8f9b2 encountered an error during           │
│  processing.                                             │
│                                                           │
│  What happened:                                          │
│  The Python Specialist couldn't extract patterns from    │
│  your code due to complex nested structures.             │
│                                                           │
│  What you can do:                                        │
│  • Simplify complex functions and try again              │
│  • Upload smaller code sections                          │
│  • Contact support for help                              │
│                                                           │
│  Error Details:                                          │
│  Agent: AGENT-PY-001                                     │
│  Code: EXTRACTION_TIMEOUT                                │
│  Time: 2026-02-06 14:45:23                               │
│                                                           │
│  [Retry with Simpler Code] [Contact Support] [Dismiss]   │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Recovery Actions

**Auto-Recovery Options:**
- ✓ Retry automatically (for transient errors)
- ✓ Suggest fixes (for syntax errors)
- ✓ Partial results (if some parts succeeded)
- ✓ Alternative approaches (for timeout/complexity)

---

## 7. ACCESSIBILITY GUIDELINES

### 7.1 WCAG 2.1 AA Compliance

**Color Contrast:**
- Text: 4.5:1 minimum contrast ratio
- Large text: 3:1 minimum
- Interactive elements: 3:1 minimum

**Keyboard Navigation:**
- All interactive elements keyboard accessible
- Visible focus indicators
- Logical tab order
- Skip navigation links

**Screen Reader Support:**
```html
<button aria-label="Start mission analysis">
  Start Analysis
</button>

<div role="status" aria-live="polite">
  Mission progress: 47%
</div>

<div role="alert" aria-live="assertive">
  Error: Mission failed
</div>
```

### 7.2 Alternative Text

**Images:**
```html
<img src="agent-status.png" alt="Agent status showing 35 active agents">
```

**Icons:**
```html
<svg aria-hidden="true">...</svg>
<span class="sr-only">Loading</span>
```

### 7.3 Semantic HTML

```html
<main>
  <h1>Mission Control</h1>
  
  <section aria-labelledby="active-missions">
    <h2 id="active-missions">Active Missions</h2>
    <!-- Mission cards -->
  </section>
  
  <section aria-labelledby="agent-status">
    <h2 id="agent-status">Agent Status</h2>
    <!-- Agent list -->
  </section>
</main>
```

---

## 8. MOBILE & RESPONSIVE DESIGN

### 8.1 Breakpoints

```css
/* Mobile */
@media (max-width: 640px) { ... }

/* Tablet */
@media (min-width: 641px) and (max-width: 1024px) { ... }

/* Desktop */
@media (min-width: 1025px) { ... }
```

### 8.2 Mobile Adaptations

**Mission Submission (Mobile):**
```
┌──────────────────────┐
│  New Mission         │
│  ──────────────────  │
│                      │
│  Mission Type        │
│  [Analyze ▼]         │
│                      │
│  Language            │
│  [Python ▼]          │
│                      │
│  📁 Upload Files     │
│  ┌─────────────────┐│
│  │ Tap to upload   ││
│  └─────────────────┘│
│                      │
│  [Submit]            │
└──────────────────────┘
```

**Progress View (Mobile):**
```
┌──────────────────────┐
│  Mission #m4a8f9b2   │
│  ──────────────────  │
│                      │
│  ⏳ Processing       │
│  47% ████████░░░░░   │
│                      │
│  Phase: Extracting   │
│  Time: 4 min left    │
│                      │
│  [Details] [Cancel]  │
└──────────────────────┘
```

---

## DOCUMENT METADATA

**Document ID:** 62  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training (Supplemental)  
**Owner:** UX/UI Design Lead  
**Related Documents:** 15 (Mission Control UI), 59 (User Guide), 61 (User Stories)

---

*End of User Interaction Guide*
