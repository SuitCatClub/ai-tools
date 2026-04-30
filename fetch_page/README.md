# fetch_page

Web scraping utility designed for corporate proxy environments. Fetches web pages with tiered strategies: API shortcuts → httpx → Playwright fallback.

## Quick Start

```bash
pip install -r requirements.txt
playwright install chromium  # optional, for JS-heavy sites

python fetch_page.py https://example.com
python fetch_page.py https://example.com --format html -o page.html
python fetch_page.py https://reddit.com/r/python/comments/abc123 --format markdown
```

## Features

- **Tiered fetching:** API shortcuts (Reddit, GitHub, HuggingFace) → httpx → Playwright
- **Corporate proxy support:** Auto-detects `HTTPS_PROXY`/`HTTP_PROXY`, handles proxy auth, MITM CAs
- **SSL resilience:** Auto-retries with `verify=False` on SSL failures, propagates state to Playwright
- **robots.txt compliance:** Respects `Disallow` and `Crawl-Delay` (capped at 120s to prevent DoS)
- **Shared deadline:** Single timeout budget across all tiers — no silent 3× timeout multiplication
- **JSON handling:** Content-type detection + body sniffing, format-aware output (no markdown fences in HTML mode)

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` / `-f` | `markdown` | Output format: `markdown`, `html`, or `text` |
| `--output` / `-o` | stdout | Write to file instead of stdout |
| `--timeout` | `30` | Total timeout in seconds (shared across all tiers) |
| `--delay` | `1.0` | Rate-limit delay between requests |
| `--no-verify` | off | Disable SSL certificate verification |
| `--ignore-robots` | off | Ignore robots.txt restrictions |

## API Shortcuts

When the URL matches a known API, fetch_page uses the structured API instead of scraping HTML:

- **Reddit:** `reddit.com` → JSON API with `?raw_json=1`
- **GitHub:** `github.com` + `raw.githubusercontent.com` → GitHub REST API (honors `GITHUB_TOKEN`)
- **HuggingFace:** `huggingface.co` → HF API for models and datasets

## Library Usage

```python
from fetch_page import fetch, FetchPageError

try:
    content = fetch("https://example.com", fmt="markdown", timeout=15)
    print(content)
except FetchPageError as e:
    print(f"Failed: {e}")
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `HTTPS_PROXY` / `HTTP_PROXY` | Proxy server URL (supports credentials) |
| `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` | Custom CA bundle path |
| `GITHUB_TOKEN` | GitHub API authentication |

## Origin

This tool was rewritten from scratch based on 38 bug reports discovered during [multi-model chain review research](https://github.com/SuitCatClub/multi-model-chain-research). Each issue is tracked at [SuitCatClub/ai-tools/issues](https://github.com/SuitCatClub/ai-tools/issues).
