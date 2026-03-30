# Terms of Service — theFactory

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Draft; legal review required  
Audience: Operators, maintainers, and legal reviewers

## 1. Scope

These Terms of Service govern use of theFactory, including the self-hosted software, the repository contents, and any environments where the platform is deployed by an operator.

If you deploy or operate theFactory for an organization, you represent that you have authority to accept these terms on that organization’s behalf.

## 2. License and Permitted Use

Use of theFactory is subject to the repository license and any separate commercial or internal-use agreement that applies to your copy of the software.

You may use theFactory to:
- run AI-assisted mission orchestration workloads
- develop and test integrations against the documented APIs
- operate self-hosted environments for internal business purposes

You may not use theFactory to:
- violate law or regulation
- process data you are not authorized to control
- bypass security controls, rate limits, or access restrictions
- interfere with other operators, systems, or third-party providers

## 3. Operator Responsibilities

Because theFactory is self-hosted, the operator is responsible for:
- configuring secure infrastructure, storage, backups, and access controls
- managing API keys, certificates, and rotation policies
- reviewing and approving any LLM provider usage
- defining retention, deletion, and incident-response policies
- complying with privacy, export, employment, and sector-specific regulations that apply to their workloads

## 4. AI and Third-Party Services

theFactory can integrate with third-party AI providers, data systems, and observability services. Those services are governed by their own terms, pricing, retention policies, and data-processing commitments.

Operators are responsible for verifying that their chosen providers are acceptable for the data they submit through theFactory.

## 5. Availability and Support

theFactory is provided on an `as-is` basis unless a separate support or service-level agreement says otherwise. Repository maintainers may change, improve, deprecate, or remove features at any time.

Operational support, response times, and maintenance windows are defined by the operator or by any separate support agreement, not by the existence of this repository alone.

## 6. Security and Responsible Use

You must:
- keep credentials and certificates confidential
- apply updates and security patches in a timely manner
- report suspected vulnerabilities through the process described in [`SECURITY.md`](../SECURITY.md)
- avoid submitting prompts, payloads, or code that you are not authorized to disclose to configured external services

## 7. Disclaimers

theFactory is an orchestration and operator platform. It can produce incomplete, unsafe, or incorrect output, especially when external models or integrations fail or return low-quality results.

Operators must validate outputs before using them in production, compliance, security, financial, or safety-sensitive workflows.

## 8. Limitation of Liability

To the maximum extent allowed by law, repository maintainers and contributors are not liable for indirect, incidental, consequential, special, or exemplary damages arising from use of theFactory.

Nothing in this document limits liability that cannot legally be limited.

## 9. Changes

These terms may be updated as the platform changes. Material changes should be tracked in repository history and referenced from the documentation index.

## 10. Contact

Security issues should be reported using the process in [`SECURITY.md`](../SECURITY.md). Other questions should be routed through the repository maintainers or the operator support channel for the environment you are using.
