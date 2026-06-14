# CloudEIP / CloudBPM / CloudISO — Architecture Reverse‑Engineering Dossier

> **Subject platform:** CloudEIP (Cloud Enterprise Information Portal), CloudBPM
> (雲端電子簽核), CloudISO (雲端文件管制) — by **Riyalab Co., Ltd. (瑞研網技)**,
> built on the proprietary **CloudGears** low‑code cloud platform.
>
> **Method:** Black‑box reverse engineering from product manuals, user guides,
> website copy and the public API documentation. Every inference is traced to
> concrete evidence and carries a confidence score. Nothing here is taken from
> Riyalab source code (none was available); it is *inferred* architecture.
>
> **Status:** Analytical / advisory. This is an independent technical teardown,
> not an official Riyalab artifact.

---

## How this dossier is organised

The work is delivered as **11 phases** plus a foundational evidence log. Each
phase is a self‑contained Markdown file with Mermaid diagrams. Read the
evidence log first — every later phase references its evidence IDs (e.g.
`E‑BACKEND‑03`).

| # | File | What it answers |
|---|------|-----------------|
| — | [`00-evidence-log.md`](00-evidence-log.md) | Raw fingerprints extracted from the inputs, each with an evidence ID |
| 1 | [`phase-01-capability-matrix.md`](phase-01-capability-matrix.md) | Every feature, classified into Collaboration / BPM / ECM / CRM / Analytics |
| 2 | [`phase-02-architecture.md`](phase-02-architecture.md) | Frontend, backend, DB, search, storage, auth — with evidence scores + architecture diagram |
| 3 | [`phase-03-workflow-engine.md`](phase-03-workflow-engine.md) | Workflow meta‑model, DB schema, state machine, API |
| 4 | [`phase-04-form-engine.md`](phase-04-form-engine.md) | Dynamic form metadata schema, JSON structure, runtime + rendering engines, versioning |
| 5 | [`phase-05-permission-architecture.md`](phase-05-permission-architecture.md) | RBAC/ABAC model, permission matrix, permission DB design |
| 6 | [`phase-06-integration-framework.md`](phase-06-integration-framework.md) | API catalog, event model, message flows, EAI architecture |
| 7 | [`phase-07-tech-stack-estimation.md`](phase-07-tech-stack-estimation.md) | Full stack estimate with evidence + confidence + alternatives |
| 8 | [`phase-08-nextgen-design.md`](phase-08-nextgen-design.md) | **CloudEIP NextGen** target architecture for a regulated (ISO 13485 / 21 CFR Part 11) QMS |
| 9 | [`phase-09-development-blueprint.md`](phase-09-development-blueprint.md) | C4 model, ERD, API spec, microservice list, deployment + CI/CD |
| 10 | [`phase-10-project-generation.md`](phase-10-project-generation.md) | Concrete repo/project structure + prompt library for Claude Code |
| 11 | [`phase-11-weaknesses.md`](phase-11-weaknesses.md) | Architectural weaknesses + root cause / impact / remediation |

---

## Executive summary of the teardown

CloudEIP is a **single‑tenant ("獨佔雲" / dedicated‑cloud) enterprise portal +
BPM + document‑control suite** whose entire runtime is hosted on **Google App
Engine (Java standard runtime)** with **Google Cloud Datastore** as the system
of record, **Google Drive** as the encrypted blob store, **Firebase Cloud
Messaging** for push, and the **App Engine Search API** for full‑text search.
It is generated from a metadata/low‑code platform called **CloudGears** whose
schema artifacts are XML (`JDO_Member`, `JDO_Resource`) and whose form
instances are schema‑less JSON documents.

The decisive fingerprints:

- **`appspot.com`** trial domain and **scale‑to‑zero** behaviour (idle
  shutdown after 15 min, 5–10 s cold start) → App Engine standard.
- **`JDO_` entity‑kind prefixes** exposed by the `getXml` API → Java Data
  Objects over Cloud Datastore (the classic GAE‑Java persistence stack).
- **Java epoch‑millisecond** date encoding and **Java regular expressions** in
  validation → JVM backend.
- **Firebase** named explicitly for push; **Google Drive** named explicitly for
  files; **AES‑256** at rest; **OWASP ZAP** in the test pipeline.
- **Schema‑less form evolution** ("new and old formats coexist, no data
  re‑org") → document store, not a relational table‑per‑form design.

The single most important architectural consequence — and the spine of the
NextGen redesign in Phases 8–11 — is that **JSON form bodies are stored
encrypted and opaque in a NoSQL store**. That choice buys effortless dynamic
forms and zero‑migration versioning, but it is exactly what makes
**relational reporting, field‑level audit trails, e‑signature manifest
integrity, and 21 CFR Part 11 / ISO 13485 evidentiary requirements** hard to
satisfy without a redesign.

> Confidence legend used throughout: **0–39** speculative · **40–69** plausible
> · **70–89** strong · **90–100** near‑certain (multiple independent
> fingerprints).
