# Architecture Decision Records (ADR) Templates

Lightweight templates for capturing design decisions with context and consequences. Works for software, hardware, and system architecture.

## What's an ADR?

A short document that captures **one** architectural decision — what was decided, why, and what follows from it. They accumulate over time to form a decision log that explains *how the system got to where it is*.

## Template

See `ADR.template.md` — our version synthesizes:
- [Michael Nygard's original](http://thinkrelevance.com/blog/2011/11/15/documenting-architecture-decisions) (Status, Context, Decision, Consequences)
- [Paulo Merson's enhanced](https://github.com/pmerson/ADR-template) (adds Rationale, rejected alternatives)

## File Naming Convention

```
docs/decisions/
├── 0001-use-sqlite-for-memory-storage.md
├── 0002-post-quantum-encryption-over-aes-only.md
├── 0003-agpl-license-for-identity-system.md
└── INDEX.md
```

Sequential numbering. Lowercase with hyphens. Verb-noun format preferred.

## Statuses

| Status | Meaning |
|--------|---------|
| **Proposed** | Under discussion, not yet decided |
| **Accepted** | Decision made, in effect |
| **Deprecated** | No longer applies (explain why) |
| **Superseded** | Replaced by another ADR (link it) |

## When to Write an ADR

- Choosing a library, framework, or tool over alternatives
- Selecting a data format, protocol, or storage approach
- Making a non-obvious tradeoff (performance vs simplicity, etc.)
- Setting a constraint that future work must respect
- Rejecting an approach (documenting what you chose NOT to do is valuable)

## Usage

### With the skill
```
/doc-adr
```

### Manual
Copy `ADR.template.md` to `docs/decisions/NNNN-title.md` and fill in.
