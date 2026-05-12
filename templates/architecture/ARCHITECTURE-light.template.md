# {{PROJECT_NAME}} — Architecture

**Last updated:** {{DATE}}

## Overview

<!-- What does this system do? 2-3 sentences. -->

{{PURPOSE}}

### Goals

| Priority | Goal |
|----------|------|
| 1 | {{GOAL_1}} |
| 2 | {{GOAL_2}} |
| 3 | {{GOAL_3}} |

## Components

```
{{PROJECT_NAME}}/
├── {{COMPONENT_1}}/     # {{RESPONSIBILITY_1}}
├── {{COMPONENT_2}}/     # {{RESPONSIBILITY_2}}
└── {{COMPONENT_3}}/     # {{RESPONSIBILITY_3}}
```

### {{COMPONENT_1}}

**Does:** {{RESPONSIBILITY_1}}
**Key files:** `{{FILES}}`

<!-- Repeat for each component -->

### How They Connect

```
{{COMPONENT_1}} ──▶ {{COMPONENT_2}} ──▶ {{COMPONENT_3}}
```

## Constraints

| Constraint | Reason |
|-----------|--------|
| {{CONSTRAINT}} | {{REASON}} |

## Getting It Running

```bash
{{SETUP_COMMANDS}}
```

---

*For design decisions, see [`docs/decisions/`](./decisions/).*
