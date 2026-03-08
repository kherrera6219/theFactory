# Agent LLM Provider and Model Matrix

Date: 2026-03-08

## Objective

Select the best primary provider/model for each of the 35 agents, and align runtime support to:

- OpenAI (including thinking controls)
- Anthropic
- Gemini

This matrix is now reflected in runtime operations output:

- `GET /internal/operations/agent-integrations`
- `GET /v1/operations/agent-integrations`

## Selection Inputs

OpenAI references indicate:

- GPT-5.2-Pro is the highest-quality general GPT-5 model in current API docs.
- GPT-5.3-Codex is the newest coding-focused model in current API docs.
- Reasoning effort controls support thinking-depth tuning.

Anthropic references indicate:

- Claude Opus 4.6 is positioned for highest-complexity reasoning.
- Claude Sonnet 4.6 is optimized for strong quality with better speed/cost.
- 1M token context and extended/adaptive thinking are available on current major tiers.

Gemini references indicate:

- Gemini 2.5 Pro is the production-approved deep-reasoning route for the heaviest STEM and knowledge workloads.
- Gemini 2.5 Flash is the production-approved low-latency route for operational and delivery tasks.
- Preview Gemini routes are no longer used as default production recommendations.

## Per-Agent Primary Recommendation

| Agent ID | Agent | Provider | Model | Thinking Profile |
|---|---|---|---|---|
| AGENT-01-PM | PM Agent | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-02-CEO | CEO Agent | OpenAI | gpt-5.2-pro | high reasoning effort |
| AGENT-03-BROKER | API Broker | Gemini | gemini-2.5-flash | thinking level low; fallback `openai/gpt-5.2` |
| AGENT-04-ACCOUNTANT | Accountant | OpenAI | gpt-5.2 | low reasoning effort |
| AGENT-05-SECURITY | Security Agent | Anthropic | claude-opus-4-6 | adaptive thinking |
| AGENT-06-IS | IS Agent | Gemini | gemini-2.5-pro | thinking level high; fallback `anthropic/claude-sonnet-4-6` |
| AGENT-07-VC | Version Control Agent | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-08-COMPLIANCE | Compliance Agent | Anthropic | claude-opus-4-6 | adaptive thinking |
| AGENT-09-HW | Hardware-Mapping Injector | Gemini | gemini-2.5-pro | thinking level high; fallback `openai/gpt-5.2-pro` |
| AGENT-10-TESTER | System Integration Tester | Anthropic | claude-opus-4-6 | adaptive thinking |
| AGENT-11-DEPLOY | Deployment Agent | Gemini | gemini-2.5-flash | thinking level medium; fallback `openai/gpt-5.2` |
| AGENT-12-PODA-MGR | Pod A Sub-Manager | OpenAI | gpt-5.2-pro | high reasoning effort |
| AGENT-13-PODA-AUDIT | Pod A QC/Audit | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-14-PYTHON | Python Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-15-JAVASCRIPT | JavaScript Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-16-RUBY | Ruby Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-17-PHP | PHP Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-18-PODB-MGR | Pod B Sub-Manager | OpenAI | gpt-5.2-pro | high reasoning effort |
| AGENT-19-PODB-AUDIT | Pod B QC/Audit | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-20-C | C Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-21-CPP | C++ Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-22-RUST | Rust Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-23-ZIG | Zig Specialist | OpenAI | gpt-5.3-codex | xhigh reasoning effort |
| AGENT-24-PODC-MGR | Pod C Sub-Manager | OpenAI | gpt-5.2-pro | high reasoning effort |
| AGENT-25-PODC-AUDIT | Pod C QC/Audit | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-26-JAVA | Java Specialist | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-27-CSHARP | C# Specialist | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-28-SCALA | Scala Specialist | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-29-KOTLIN | Kotlin Specialist | Anthropic | claude-sonnet-4-6 | enabled, budget 8192 |
| AGENT-30-PODD-MGR | Pod D Sub-Manager | Gemini | gemini-2.5-pro | thinking level high; fallback `openai/gpt-5.2-pro` |
| AGENT-31-PODD-AUDIT | Pod D QC/Audit | Anthropic | claude-opus-4-6 | adaptive thinking |
| AGENT-32-MATLAB | MATLAB Specialist | Gemini | gemini-2.5-pro | thinking level high |
| AGENT-33-R | R Specialist | Gemini | gemini-2.5-pro | thinking level high |
| AGENT-34-JULIA | Julia Specialist | Gemini | gemini-2.5-pro | thinking level high |
| AGENT-35-MATHEMATICA | Mathematica Specialist | Gemini | gemini-2.5-pro | thinking level high |

## Runtime Configuration for Initial Key-Based Tests

Set one key per provider in `.env`:

- `OPENAI_API_KEY=...`
- `ANTHROPIC_API_KEY=...`
- `GEMINI_API_KEY=...`

Then select provider under test for builder endpoint:

- `LLM_PROVIDER=openai|anthropic|gemini`

Optional thinking controls:

- OpenAI: `OPENAI_REASONING_EFFORT=none|minimal|low|medium|high|xhigh`
- Anthropic: `ANTHROPIC_THINKING_MODE=enabled|adaptive`
- Gemini: `GEMINI_THINKING_LEVEL=low|medium|high` and `GEMINI_THINKING_BUDGET=-1|0|N`

## Coding-Model Strategy Decision

- OpenAI pod specialists: use coding model (`gpt-5.3-codex`) for language-specialist and VC coding loops.
- Tester stays on Claude Opus 4.6 to prioritize adversarial test design and failure-mode reasoning over code-generation throughput.
- Anthropic pod agents: keep Claude general models (`claude-sonnet-4-6` primary, Opus for deep audits) because Anthropic does not publish a separate codex-style API model; Claude Code runs on Claude models.
- Gemini pod agents: use general Gemini reasoning models (`gemini-2.5-pro` / `gemini-2.5-flash`), since Google does not expose a separate coding-only model family in Gemini API; coding performance is built into these general models.

## Sources

OpenAI (official):

- https://platform.openai.com/docs/models
- https://platform.openai.com/docs/guides/reasoning
- https://platform.openai.com/docs/guides/code-generation
- https://platform.openai.com/docs/pricing

Anthropic (official):

- https://docs.anthropic.com/en/docs/about-claude/models/overview
- https://docs.anthropic.com/en/api/messages
- https://docs.anthropic.com/en/docs/claude-code/model-config

Google Gemini (official):

- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/text-generation
- https://ai.google.dev/gemini-api/docs/thinking
- https://ai.google.dev/gemini-api/docs/changelog
- https://ai.google.dev/gemini-api/docs/pricing
- https://developers.google.com/gemini-code-assist/docs/models
