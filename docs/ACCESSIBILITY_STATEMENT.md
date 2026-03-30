# Accessibility Statement — Mission Control and theFactory

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Draft; accessibility review required  
Audience: Operators, users, accessibility reviewers, and legal reviewers

## 1. Commitment

theFactory aims to provide an operator experience that is usable with keyboard navigation, screen readers, reduced-motion preferences, and common browser zoom levels. This statement covers the repository’s current Mission Control UI and the documented local operator workflows.

## 2. Current Accessibility Baseline

The current UI includes:
- semantic navigation landmarks in the Mission Control shell
- visible focus styles for interactive controls
- reduced-motion handling in the global stylesheet
- accessible status and alert messaging on key mission views
- keyboard support for the global shortcuts dialog

## 3. Known Limitations

The following areas still need improvement:
- full end-to-end accessibility regression coverage across all routes
- broader screen-reader validation across complex data tables
- stronger consistency in tokenized visual styling across every page
- more explicit accessibility review of newly added features before release

## 4. Operator Responsibilities

Because theFactory is self-hosted, the operator is responsible for:
- deploying supported browser and OS combinations for end users
- maintaining any custom themes, branding, or downstream forks in an accessible way
- testing integrated auth and reverse-proxy layers for keyboard and screen-reader compatibility

## 5. Feedback

If you encounter an accessibility issue, document:
- the page or workflow affected
- the browser and OS used
- the assistive technology involved, if any
- the exact failure mode and reproduction steps

Security-sensitive accessibility issues should follow [`SECURITY.md`](../SECURITY.md). All other issues should be filed through the repository issue tracker or the operator’s internal support channel.

## 6. Improvement Process

Accessibility issues should be triaged alongside other release-blocking defects. Fixes should include:
- a reproducible test case
- verification in keyboard-only navigation
- regression coverage where practical

This statement should be reviewed whenever Mission Control navigation, design tokens, or major workflows change.
