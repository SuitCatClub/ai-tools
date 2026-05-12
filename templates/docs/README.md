# Documentation Templates

Standardized open-source documentation templates. Apply to any project for a recognizable, professional presence.

## What's Included

| File | Purpose |
|------|---------|
| `README.template.md` | Full README with badges, nav, epigraph, ToC, FAQ, reference links |
| `CONTRIBUTING.template.md` | Contributing guidelines with project principles |
| `CHANGELOG.template.md` | Keep a Changelog format starter |
| `github/bug-report.template.md` | GitHub issue template for bugs |
| `github/feature-request.template.md` | GitHub issue template for features |
| `github/pull-request.template.md` | GitHub PR template |

## Design Methodology

These templates were derived by studying curated examples from [awesome-readme](https://github.com/matiassingers/awesome-readme), specifically projects that match the "developer tool with philosophical depth" profile:

- **re-frame** — literary epigraph as hook, radical minimalism, restrained badges
- **choo** — nav menu above fold, FAQ with personality, good language
- **gofiber/fiber** — collapsible `<details>` blocks, emoji section headers
- **create-go-app/cli** — reference-style links, structured option tables

### Principles

1. **Format is a trust signal.** People recognize the visual grammar before reading content.
2. **Restraint over noise.** 2-3 badges, not 15. Philosophy section, not marketing.
3. **Personality in voice.** These aren't corporate docs — they should sound like someone built this with care.
4. **Collapsible depth.** Show the hook, hide the details behind `<details>`.
5. **Reference-style links.** Keep the markdown source readable.

## Placeholders

Templates use `{{PLACEHOLDER}}` syntax. The `doc-standard` skill fills these automatically from project context, or you can do find-and-replace manually.

| Placeholder | Meaning |
|-------------|---------|
| `{{PROJECT_NAME}}` | Human-readable project name |
| `{{PROJECT_SLUG}}` | GitHub repo name (lowercase, hyphens) |
| `{{GITHUB_ORG}}` | GitHub org or username |
| `{{ONE_LINE_DESCRIPTION}}` | Tagline — under 120 chars, italic |
| `{{EPIGRAPH}}` | Philosophical quote or framing (optional) |
| `{{OVERVIEW}}` | 2-3 paragraph description |
| `{{FEATURES}}` | Bullet list of 4-7 key features |
| `{{PHILOSOPHY}}` | 2-3 paragraphs on why and how |
| `{{QUICK_START}}` | Install + minimal working example |
| `{{ARCHITECTURE}}` | System overview (optional) |
| `{{FAQ_ITEMS}}` | 3-5 collapsible Q&A pairs |
| `{{LICENSE_NAME}}` | SPDX identifier (e.g., AGPL-3.0, MIT) |
| `{{LANGUAGE}}` | Primary language (Python, TypeScript, etc.) |
| `{{LANGUAGE_BADGE_COLOR}}` | Shields.io color code for language badge |

## Usage

### With the skill (recommended)

```
/doc-standard
```

The skill reads your project, asks a few questions, and generates all files.

### Manual

Copy templates to your project and replace `{{PLACEHOLDERS}}` by hand.
