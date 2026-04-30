# ai-tools

Tools the AI uses — scrapers, fetchers, utilities.

## Tools

### fetch_page

Web scraping utility designed for corporate proxy environments. Supports Reddit, GitHub, and HuggingFace API shortcuts, with httpx + Playwright tiered fetching.

```bash
cd fetch_page
pip install -r requirements.txt
playwright install chromium  # optional, for JS-heavy sites

python fetch_page.py https://example.com
python fetch_page.py https://github.com/owner/repo --format markdown
python fetch_page.py https://reddit.com/r/python/comments/abc123 -o post.md
```

See [fetch_page/README.md](fetch_page/README.md) for full documentation.

## License

MIT
