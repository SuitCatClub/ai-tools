# Architecture Documentation Templates

A simplified architecture document template inspired by [arc42](https://arc42.org) (12 sections) but distilled to what actually matters for our projects. Markdown-native, git-friendly, no build tools required.

## arc42 → Our Sections

arc42 has 12 sections. We keep 7 that consistently provide value:

| arc42 Section | Our Section | Kept? |
|---------------|-------------|-------|
| Introduction & Goals | **Overview** | ✅ |
| Constraints | **Constraints** | ✅ |
| Context & Scope | **System Context** | ✅ |
| Solution Strategy | **Solution Strategy** | ✅ |
| Building Block View | **Components** | ✅ |
| Runtime View | *(folded into Components)* | ⚡ |
| Deployment View | **Deployment** | ✅ |
| Cross-cutting Concepts | **Cross-cutting Concerns** | ✅ |
| Architecture Decisions | *(separate ADRs)* | → `/doc-adr` |
| Quality Requirements | *(in Constraints)* | → folded |
| Risks | *(in Cross-cutting)* | → folded |
| Glossary | *(only if needed)* | optional |

## Template Variants

| Variant | Use Case | Sections |
|---------|----------|----------|
| `ARCHITECTURE-full.template.md` | System with multiple components | All 7 sections |
| `ARCHITECTURE-light.template.md` | Single-module tool or library | Overview + Components + Constraints |

## Usage

### With the skill
```
/doc-architecture
```

### Manual
Copy the appropriate template to your project's `docs/` directory and fill in.
