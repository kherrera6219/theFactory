# Agent LLM Provider Model Matrix

Document version: 2026.08.15
Last updated: 2026-08-20
Status: Canonical runtime matrix
Audience: Architects, developers, AI operators, and release reviewers

This document is the current model-routing source of truth for the 41-agent
runtime. Older phase plans and archived evidence may still mention 35-agent,
38-agent, or mixed OpenAI/Gemini defaults. Those references are historical.

## Current Default

As of commit `1b10d8c`, every runtime agent recommendation defaults to:

| Provider | Model | Runtime mode | Effort / thinking |
|---|---|---|---|
| Gemini | `gemini-4-argon` | `thinking` | `high` |

The default test path is Gemini-first so all agents can be validated with one
Google API key during local operator testing.

## Operator-Selectable Model Catalog

Mission Control Settings and the Gateway builder preview expose only these
three model routes. All routes default to high effort / high thinking.

| UI label | Provider key | Model ID | Provider endpoint | High-effort field |
|---|---|---|---|---|
| Gemini 4 Argon | `gemini` | `gemini-4-argon` | `POST /v1beta/models/gemini-4-argon:generateContent` | Gemini thinking level `high` |
| ChatGPT 6.1 Terrea | `openai` | `gpt-6.1-terrea` | `POST /v1/responses` | `reasoning.effort=high` |
| Claude Ops 5.5 | `anthropic` | `claude-ops-5.5` | `POST /v1/messages` | Thinking enabled with high token budget |

The non-Gemini routes are available for vault-slot testing and future
comparison, but they are not the default assignment for any agent.

## Per-Agent Defaults

| Agent ID | Agent | Provider | Model | Effort / thinking |
|---|---|---|---|---|
| AGENT-01-PM | PM Agent | Gemini | `gemini-4-argon` | high |
| AGENT-02-CEO | CEO Agent | Gemini | `gemini-4-argon` | high |
| AGENT-03-BROKER | API Broker | Gemini | `gemini-4-argon` | high |
| AGENT-04-ACCOUNTANT | Accountant | Gemini | `gemini-4-argon` | high |
| AGENT-05-SECURITY | Security Agent | Gemini | `gemini-4-argon` | high |
| AGENT-06-IS | IS Agent | Gemini | `gemini-4-argon` | high |
| AGENT-07-VC | Version Control Agent | Gemini | `gemini-4-argon` | high |
| AGENT-08-COMPLIANCE | Compliance Agent | Gemini | `gemini-4-argon` | high |
| AGENT-09-HW | Hardware-Mapping Injector | Gemini | `gemini-4-argon` | high |
| AGENT-10-TESTER | System Integration Tester | Gemini | `gemini-4-argon` | high |
| AGENT-11-DEPLOY | Deployment Agent | Gemini | `gemini-4-argon` | high |
| AGENT-12-PODA-MGR | Pod A Sub-Manager | Gemini | `gemini-4-argon` | high |
| AGENT-13-PODA-AUDIT | Pod A QC/Audit | Gemini | `gemini-4-argon` | high |
| AGENT-14-PYTHON | Python Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-15-JAVASCRIPT | JavaScript Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-16-RUBY | Ruby Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-17-PHP | PHP Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-18-PODB-MGR | Pod B Sub-Manager | Gemini | `gemini-4-argon` | high |
| AGENT-19-PODB-AUDIT | Pod B QC/Audit | Gemini | `gemini-4-argon` | high |
| AGENT-20-C | C Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-21-CPP | C++ Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-22-RUST | Rust Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-23-ZIG | Zig Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-24-PODC-MGR | Pod C Sub-Manager | Gemini | `gemini-4-argon` | high |
| AGENT-25-PODC-AUDIT | Pod C QC/Audit | Gemini | `gemini-4-argon` | high |
| AGENT-26-JAVA | Java Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-27-CSHARP | C# Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-28-SCALA | Scala Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-29-KOTLIN | Kotlin Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-30-PODD-MGR | Pod D Sub-Manager | Gemini | `gemini-4-argon` | high |
| AGENT-31-PODD-AUDIT | Pod D QC/Audit | Gemini | `gemini-4-argon` | high |
| AGENT-32-MATLAB | MATLAB Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-33-R | R Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-34-JULIA | Julia Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-35-MATHEMATICA | Mathematica Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-36-GO | Go Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-37-HASKELL | Haskell Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-38-OCAML | OCaml Specialist | Gemini | `gemini-4-argon` | high |
| AGENT-39-DEPABS | Dependency Absorption Agent | Gemini | `gemini-4-argon` | high |
| AGENT-40-TESTDATA | Database and Test Data Agent | Gemini | `gemini-4-argon` | high |
| AGENT-41-RQCA | Runtime QC Agent | Gemini | `gemini-4-argon` | high |

## Runtime Defaults

The shipped local defaults are:

```env
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-4-argon
GEMINI_THINKING_LEVEL=high
OPENAI_MODEL=gpt-6.1-terrea
OPENAI_REASONING_EFFORT=high
ANTHROPIC_MODEL=claude-ops-5.5
ANTHROPIC_THINKING_BUDGET_TOKENS=8192
```

Provider keys remain externally supplied. Without a live key, the orchestrator
falls back to deterministic output so local runtime checks can still complete.
