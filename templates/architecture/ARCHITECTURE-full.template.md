# {{PROJECT_NAME}} — Architecture

**Last updated:** {{DATE}}
**Version:** {{VERSION}}

## Overview

### Purpose

<!-- What does this system do? Who is it for? What problem does it solve? -->

{{PURPOSE}}

### Goals

<!-- The top 3-5 architectural goals that drive decisions -->

| Priority | Goal | Meaning |
|----------|------|---------|
| 1 | {{GOAL_1}} | {{GOAL_1_MEANING}} |
| 2 | {{GOAL_2}} | {{GOAL_2_MEANING}} |
| 3 | {{GOAL_3}} | {{GOAL_3_MEANING}} |

### Non-Goals

<!-- What this system explicitly does NOT try to do -->

- {{NON_GOAL}}

## Constraints

### Technical

<!-- Hard technical constraints: language, platform, compatibility requirements -->

| Constraint | Reason |
|-----------|--------|
| {{CONSTRAINT}} | {{REASON}} |

### Organizational

<!-- Team, timeline, budget, licensing, regulatory constraints -->

- {{ORG_CONSTRAINT}}

### Quality Requirements

<!-- Performance, security, reliability, maintainability targets -->

| Quality | Requirement | Measure |
|---------|-------------|---------|
| {{QUALITY}} | {{REQUIREMENT}} | {{MEASURE}} |

## System Context

<!-- How does this system interact with the outside world? -->

### External Interfaces

```
┌─────────────┐          ┌──────────────┐
│  {{ACTOR}}  │ ──────── │  {{SYSTEM}}  │
└─────────────┘          └──────────────┘
                                │
                         ┌──────┴──────┐
                         │ {{EXTERNAL}}│
                         └─────────────┘
```

| Interface | Direction | Protocol | Purpose |
|-----------|-----------|----------|---------|
| {{INTERFACE}} | in/out/both | {{PROTOCOL}} | {{PURPOSE}} |

## Solution Strategy

<!-- The fundamental approach: key technology decisions, architectural style, patterns -->

### Key Technology Choices

| Decision | Choice | Why |
|----------|--------|-----|
| {{DECISION}} | {{CHOICE}} | {{WHY}} |

### Architectural Style

<!-- Monolith? Microservices? Event-driven? Plugin architecture? Layered? -->

{{ARCHITECTURAL_STYLE}}

### Core Patterns

<!-- 2-3 patterns that define how the system works -->

- **{{PATTERN}}:** {{DESCRIPTION}}

## Components

<!-- The main building blocks and their responsibilities -->

### Component Overview

```
{{PROJECT_NAME}}/
├── {{COMPONENT_1}}/     # {{RESPONSIBILITY_1}}
├── {{COMPONENT_2}}/     # {{RESPONSIBILITY_2}}
└── {{COMPONENT_3}}/     # {{RESPONSIBILITY_3}}
```

### {{COMPONENT_1}}

**Responsibility:** {{RESPONSIBILITY_1}}
**Key files:** `{{FILES}}`
**Depends on:** {{DEPENDENCIES}}

<!-- Repeat for each major component -->

### Component Interactions

<!-- How do components talk to each other? Data flow? -->

```
{{COMPONENT_1}} ──data──▶ {{COMPONENT_2}} ──result──▶ {{COMPONENT_3}}
```

## Deployment

<!-- How does this run? Where? What's needed? -->

### Requirements

- {{RUNTIME_REQUIREMENT}}

### Setup

```bash
{{SETUP_COMMANDS}}
```

### Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| {{SETTING}} | {{DEFAULT}} | {{PURPOSE}} |

## Cross-cutting Concerns

### Security

<!-- Authentication, authorization, encryption, secrets management -->

{{SECURITY}}

### Error Handling

<!-- Strategy for errors, logging, monitoring, recovery -->

{{ERROR_HANDLING}}

### Testing Strategy

<!-- What's tested, how, at what level -->

| Level | What | How |
|-------|------|-----|
| {{TEST_LEVEL}} | {{WHAT_TESTED}} | {{HOW}} |

### Known Risks

<!-- Technical debt, scaling limits, single points of failure -->

| Risk | Impact | Mitigation |
|------|--------|-----------|
| {{RISK}} | {{IMPACT}} | {{MITIGATION}} |

---

*Decisions that shaped this architecture are documented in [`docs/decisions/`](./decisions/) as ADRs.*
