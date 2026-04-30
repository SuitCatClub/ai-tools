#!/usr/bin/env python3
"""
fetch_page.py — Web scraping utility for corporate proxy environments.

Tiered fetching: API shortcuts → httpx → Playwright fallback.
Supports Reddit, GitHub, and HuggingFace API shortcuts.

Usage:
    python fetch_page.py <url> [--output FILE] [--format markdown|html|text]
           [--timeout 30] [--delay 1] [--no-verify] [--ignore-robots]

Built from 38 bug reports discovered during multi-model chain review research.
See: https://github.com/SuitCatClub/ai-tools/issues
"""

import argparse
import base64
import html as html_lib
import json
import os
import re
import sys
import threading
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

import httpx


# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    import trafilatura

    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    from markdownify import markdownify as md

    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False

try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


USER_AGENT = "ResearchFetcher/2.0 (+corporate-cli; respectful scraping)"
ROBOTS_USER_AGENT = "ResearchFetcher"
MAX_CRAWL_DELAY = 120  # Cap to prevent DoS via hostile robots.txt [#unbounded-crawl-delay]

# Playwright fallback triggers — includes 407 for corporate proxy [#http-407-proxy-auth]
PLAYWRIGHT_FALLBACK_CODES = {403, 407, 429, 503}

_LAST_FETCH_BY_HOST: dict[str, float] = {}
_LAST_FETCH_LOCK = threading.Lock()


class FetchPageError(RuntimeError):
    """Raised when page fetching fails without terminating the caller."""


# Patterns that indicate a JS challenge page (httpx got 200 but content is useless)
_CHALLENGE_SIGNATURES = [
    "Please wait for verification",
    "Just a moment...",           # Cloudflare
    "Checking your browser",      # Cloudflare
    "challenge-platform",         # Generic
]

# Soft bot walls — HTTP 200 but content is a gate page, not real content.
# Detected by: short body + presence of a gate phrase.
_BOT_GATE_PHRASES = [
    "click the button below to continue shopping",  # Amazon
    "continue shopping",                              # Amazon variant
    "verify you are a human",
    "are you a robot",
    "please verify you are a human",
    "access to this page has been denied",
    "pardon our interruption",                        # Amazon CAPTCHA
    "crawler is not allowed",                         # Unity Forums
]

_BOT_GATE_MAX_VISIBLE = 1500  # Visible text shorter than this with a gate phrase → wall

# Minimum time (ms) to give Playwright — even if httpx consumed most of the budget
_PLAYWRIGHT_MIN_TIMEOUT_MS = 10_000


# ---------------------------------------------------------------------------
# Input validation [#url-scheme-validation, #timeout-zero-instant-fail,
#                   #negative-delay-validation]
# ---------------------------------------------------------------------------


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchPageError(
            f"Unsupported URL scheme '{parsed.scheme}'. "
            "Only http:// and https:// are allowed."
        )


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"Must be positive, got {n}")
    return n


def _non_negative_float(value: str) -> float:
    f = float(value)
    if f < 0:
        raise argparse.ArgumentTypeError(f"Must be non-negative, got {f}")
    return f


# ---------------------------------------------------------------------------
# Deadline — shared timeout budget across all tiers
# [#timeout-budget-double]
# ---------------------------------------------------------------------------


class Deadline:
    def __init__(self, timeout: int):
        self._end = time.monotonic() + timeout
        self._total = timeout

    def remaining(self) -> float:
        left = self._end - time.monotonic()
        if left <= 0:
            raise FetchPageError(f"Total timeout of {self._total}s exceeded.")
        return left

    def remaining_int(self) -> int:
        return max(1, int(self.remaining()))


# ---------------------------------------------------------------------------
# SSL / HTTP client [#ca-bundle-no-verify, #httpx-resource-leak]
# ---------------------------------------------------------------------------


def _ssl_verify_arg(verify: bool):
    if not verify:
        return False
    ca = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    return ca if ca else True


def _make_client(verify: bool, timeout: float) -> httpx.Client:
    return httpx.Client(
        verify=_ssl_verify_arg(verify),
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Host matching (handles ports, IPv6, userinfo)
# ---------------------------------------------------------------------------


def _host_matches(netloc: str, domain: str) -> bool:
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    if netloc.startswith("["):
        bracket_end = netloc.find("]")
        host = netloc[1:bracket_end] if bracket_end > 0 else netloc[1:]
    else:
        host = netloc.split(":", 1)[0]
    host = host.lower()
    domain = domain.lower()
    return host == domain or host.endswith(f".{domain}")


# ---------------------------------------------------------------------------
# robots.txt [#robots-exception-safety, #crawl-delay-first,
#             #crawl-delay-race, #delay-stacking,
#             #crawl-delay-slot-timeout]
# ---------------------------------------------------------------------------


def _robots_policy(url: str, client: httpx.Client) -> tuple[bool, float | None]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True, None
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = client.get(robots_url)
        if resp.status_code >= 400:
            return True, None
        rp.parse(resp.text.splitlines())
        crawl_delay = rp.crawl_delay(ROBOTS_USER_AGENT)
        if crawl_delay is None:
            crawl_delay = rp.crawl_delay("*")
        allowed = rp.can_fetch(ROBOTS_USER_AGENT, url)
        delay = min(float(crawl_delay), MAX_CRAWL_DELAY) if crawl_delay else None
        return allowed, delay
    except Exception:
        return True, None


def _respect_crawl_delay(
    host: str, crawl_delay: float | None, user_delay: float
) -> None:
    effective = max(crawl_delay or 0, user_delay)
    if effective <= 0:
        return

    with _LAST_FETCH_LOCK:
        last = _LAST_FETCH_BY_HOST.get(host)
        if last is None:
            # First request to this host — no sleep needed [#crawl-delay-first]
            _LAST_FETCH_BY_HOST[host] = time.monotonic()
            return
        wait = effective - (time.monotonic() - last)
        if wait > 0:
            _LAST_FETCH_BY_HOST[host] = time.monotonic() + wait
        else:
            _LAST_FETCH_BY_HOST[host] = time.monotonic()
            wait = 0

    if wait > 0:
        print(
            f"[info] Respecting crawl-delay: sleeping {wait:.1f}s", file=sys.stderr
        )
        time.sleep(wait)
        with _LAST_FETCH_LOCK:
            _LAST_FETCH_BY_HOST[host] = time.monotonic()


# ---------------------------------------------------------------------------
# Retry-After [#retry-after-429]
# ---------------------------------------------------------------------------


def _parse_retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(header)
        return max(0, (dt - datetime.now(timezone.utc)).total_seconds())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API shortcuts [#api-shortcut-title, #api-shortcuts-unbounded,
#   #crawl-delay-api-shortcuts, #reddit-raw-json, #reddit-indexerror,
#   #reddit-nonthread-misfire, #raw-github-garbage, #github-lfs-quota,
#   #github-blob-continue, #github-branch-slash,
#   #huggingface-datasets-guard, + null-value propagation cluster]
# ---------------------------------------------------------------------------


def _extract_api_title(content: str, fallback: str) -> str:
    first_line = content.split("\n", 1)[0].strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return fallback


def _try_reddit(url: str, client: httpx.Client, deadline: Deadline) -> str | None:
    parsed = urlparse(url)
    if not _host_matches(parsed.netloc, "reddit.com"):
        return None

    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    json_url = clean if clean.endswith(".json") else clean + ".json"
    json_url += "?raw_json=1"  # [#reddit-raw-json]

    try:
        resp = client.get(
            json_url,
            headers={"Accept": "application/json"},
            timeout=deadline.remaining_int(),
        )
        resp.raise_for_status()
        data = resp.json()

        # Validate shape — reject non-thread pages [#reddit-nonthread-misfire]
        if not isinstance(data, list) or len(data) == 0:
            return None
        children = data[0].get("data", {}).get("children", [])
        if not children:  # [#reddit-indexerror]
            return None
        post = children[0].get("data", {})
        if not post.get("title"):
            return None

        lines = [f"# {post['title']}\n"]
        subreddit = post.get("subreddit", "")
        author = post.get("author", "")
        if subreddit:
            line = f"**r/{subreddit}**"
            if author:
                line += f" | by u/{author}"
            lines.append(line)
        selftext = (post.get("selftext") or "").strip()
        if selftext:
            lines.append(f"\n{selftext}\n")

        if len(data) > 1:
            for comment in data[1].get("data", {}).get("children", [])[:10]:
                c = comment.get("data", {})
                body = c.get("body")
                if body:
                    lines.append(f"\n> **u/{c.get('author', '')}**: {body}")

        return "\n".join(lines)
    except Exception:
        return None


def _try_github(url: str, client: httpx.Client, deadline: Deadline) -> str | None:
    parsed = urlparse(url)

    # raw.githubusercontent.com — fetch directly [#raw-github-garbage]
    if _host_matches(parsed.netloc, "raw.githubusercontent.com"):
        try:
            resp = client.get(url, timeout=deadline.remaining_int())
            resp.raise_for_status()
            path = parsed.path.strip("/")
            return f"# {path}\n\n```\n{resp.text}\n```"
        except Exception:
            return None

    if not _host_matches(parsed.netloc, "github.com"):
        return None

    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None

    owner, repo = parts[0], parts[1]
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # File blob [#github-branch-slash]: try progressively longer refs
    if len(parts) >= 5 and parts[2] == "blob":
        for split in range(4, len(parts)):
            ref = "/".join(parts[3:split])
            path = "/".join(parts[split:])
            if not path:
                continue
            api = (
                f"https://api.github.com/repos/{owner}/{repo}"
                f"/contents/{path}?ref={ref}"
            )
            try:
                resp = client.get(
                    api, headers=headers, timeout=deadline.remaining_int()
                )
                if resp.status_code == 404:
                    continue  # [#github-blob-continue]
                resp.raise_for_status()
                data = resp.json()
                content_b64 = data.get("content", "")
                if not content_b64 or not content_b64.strip():
                    # LFS or empty — don't burn quota retrying [#github-lfs-quota]
                    size = data.get("size", 0)
                    if size > 0:
                        return (
                            f"# {path}\n\n"
                            f"(LFS file, {size} bytes — not available via API)"
                        )
                    continue
                content = base64.b64decode(content_b64).decode()
                return f"# {path}\n\n```\n{content}\n```"
            except httpx.HTTPStatusError:
                continue
            except Exception:
                continue
        return None

    # Repo root — null-safe field access
    try:
        resp = client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
            timeout=deadline.remaining_int(),
        )
        resp.raise_for_status()
        info = resp.json()
        full_name = info.get("full_name") or f"{owner}/{repo}"
        description = info.get("description") or ""
        stars = info.get("stargazers_count") or 0
        forks = info.get("forks_count") or 0
        language = info.get("language") or "Unknown"
        html_url = info.get("html_url") or url
        return (
            f"# {full_name}\n\n{description}\n\n"
            f"⭐ {stars} | 🍴 {forks} | Language: {language}\n\n"
            f"URL: {html_url}"
        )
    except Exception:
        return None


def _try_huggingface(url: str, client: httpx.Client, deadline: Deadline) -> str | None:
    parsed = urlparse(url)
    if not _host_matches(parsed.netloc, "huggingface.co"):
        return None

    parts = parsed.path.strip("/").split("/")
    if not parts or not parts[0]:
        return None

    try:
        if parts[0] == "datasets":
            if len(parts) < 3:
                return None  # [#huggingface-datasets-guard]
            api_url = f"https://huggingface.co/api/datasets/{parts[1]}/{parts[2]}"
        elif len(parts) >= 2:
            api_url = f"https://huggingface.co/api/models/{parts[0]}/{parts[1]}"
        else:
            return None

        resp = client.get(api_url, timeout=deadline.remaining_int())
        resp.raise_for_status()
        data = resp.json()

        # Null-safe: every field gets a fallback [Phase 2 propagation cluster]
        model_id = data.get("modelId") or data.get("id") or "Unknown"
        tags = ", ".join(data.get("tags", [])[:10]) or "none"
        downloads = data.get("downloads") or data.get("downloadsAllTime") or 0
        likes = data.get("likes") or 0

        return (
            f"# {model_id}\n\n"
            f"**Tags:** {tags}\n"
            f"**Downloads:** {downloads} | **Likes:** {likes}\n\n"
            f"URL: {url}"
        )
    except Exception:
        return None


def _try_mouser(url: str, client: httpx.Client, deadline: Deadline) -> str | None:
    """Mouser Search API shortcut. Requires MOUSER_API_KEY env var.

    Triggers on:
      - mouser.com URLs (extracts part number from path or query)
      - mouser.com/ProductDetail/<part> or Search/Refine?Keyword=<part>
    """
    api_key = os.environ.get("MOUSER_API_KEY", "").strip()
    if not api_key:
        return None

    parsed = urlparse(url)
    if not _host_matches(parsed.netloc, "mouser.com"):
        return None

    # Extract part number from URL
    part_number = None
    path = parsed.path.strip("/")

    # /ProductDetail/<manufacturer-part-number>
    if path.lower().startswith("productdetail/"):
        segments = path.split("/")
        if len(segments) >= 2:
            part_number = segments[-1]

    # /Search/Refine?Keyword=<part>
    if not part_number and "keyword" in parsed.query.lower():
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        # Case-insensitive query param lookup
        for k, v in qs.items():
            if k.lower() == "keyword" and v:
                part_number = v[0]
                break

    # /<mouser-sku> or /<manufacturer-part>
    if not part_number and path and "/" not in path:
        part_number = path

    if not part_number:
        return None

    return _mouser_api_search(part_number, api_key, client, deadline)


def _mouser_api_search(
    part_number: str, api_key: str, client: httpx.Client, deadline: Deadline
) -> str | None:
    """Call Mouser Search API and format results as markdown."""
    api_url = f"https://api.mouser.com/api/v1.0/search/partnumber?apiKey={api_key}"
    payload = {
        "SearchByPartRequest": {
            "mouserPartNumber": part_number,
            "partSearchOptions": "Exact",
        }
    }

    try:
        resp = client.post(
            api_url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=deadline.remaining_int(),
        )
        resp.raise_for_status()
        data = resp.json()

        errors = data.get("Errors", [])
        if errors:
            msg = errors[0].get("Message", "Unknown error")
            print(f"[mouser-api] Error: {msg}", file=sys.stderr)
            return None

        results = data.get("SearchResults", {})
        parts = results.get("Parts", [])
        if not parts:
            return None

        lines = []
        for part in parts[:5]:  # Cap at 5 results
            mpn = part.get("ManufacturerPartNumber") or part_number
            mfr = part.get("Manufacturer") or "Unknown"
            desc = part.get("Description") or ""
            mouser_pn = part.get("MouserPartNumber") or ""
            stock = part.get("Availability") or "Unknown"
            datasheet = part.get("DataSheetUrl") or ""
            product_url = part.get("ProductDetailUrl") or ""
            rohs = part.get("ROHSStatus") or ""
            lifecycle = part.get("LifecycleStatus") or ""

            lines.append(f"# {mpn}\n")
            lines.append(f"**Manufacturer:** {mfr}")
            lines.append(f"**Description:** {desc}")
            if mouser_pn:
                lines.append(f"**Mouser P/N:** {mouser_pn}")
            lines.append(f"**Stock:** {stock}")
            if lifecycle:
                lines.append(f"**Lifecycle:** {lifecycle}")
            if rohs:
                lines.append(f"**RoHS:** {rohs}")

            # Pricing tiers
            pricing = part.get("PriceBreaks", [])
            if pricing:
                lines.append("\n**Pricing:**")
                lines.append("| Qty | Price |")
                lines.append("|-----|-------|")
                for tier in pricing:
                    qty = tier.get("Quantity", "?")
                    price = tier.get("Price", "?")
                    currency = tier.get("Currency", "")
                    lines.append(f"| {qty} | {price} {currency} |")

            # Specs
            attrs = part.get("ProductAttributes", [])
            if attrs:
                lines.append("\n**Specifications:**")
                for attr in attrs:
                    name = attr.get("AttributeName", "")
                    val = attr.get("AttributeValue", "")
                    if name and val:
                        lines.append(f"- {name}: {val}")

            if datasheet:
                lines.append(f"\n📄 **Datasheet:** {datasheet}")
            if product_url:
                lines.append(f"🔗 **Product page:** {product_url}")

            lines.append("")  # Separator between parts

        return "\n".join(lines)
    except Exception:
        return None


def _try_api_shortcuts(
    url: str, client: httpx.Client, deadline: Deadline
) -> tuple[str, str] | None:
    for fn in (_try_reddit, _try_github, _try_huggingface, _try_mouser):
        try:
            deadline.remaining()  # Check before each attempt [#api-shortcuts-unbounded]
        except FetchPageError:
            return None
        result = fn(url, client, deadline)
        if result:
            title = _extract_api_title(result, urlparse(url).netloc)
            return title, result
    return None


# ---------------------------------------------------------------------------
# JSON handling [#json-sniff-hardened, #bogus-json-decode-error,
#                #malformed-json-body, #json-html-format]
# ---------------------------------------------------------------------------


def _try_parse_json(raw: str) -> object | None:
    stripped = raw.lstrip()
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _format_json(data: object, fmt: str) -> str:
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    if fmt in ("html", "text"):
        return pretty
    return f"```json\n{pretty}\n```"


def _handle_json_response(resp: httpx.Response, fmt: str) -> str | None:
    ct = resp.headers.get("content-type", "")
    if "json" in ct:
        try:
            return _format_json(resp.json(), fmt)
        except (json.JSONDecodeError, ValueError):
            return None  # [#bogus-json-decode-error] graceful fallback
    parsed = _try_parse_json(resp.text)
    if parsed is not None:
        return _format_json(parsed, fmt)
    return None


# ---------------------------------------------------------------------------
# HTML → content [#format-text-crash, #noscript-strip-list,
#                  #html-entity-title]
# ---------------------------------------------------------------------------


def _extract_content(html: str, fmt: str, url: str) -> tuple[str, str]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = html_lib.unescape(m.group(1).strip()) if m else ""  # [#html-entity-title]

    # Pre-strip <script> tags — trafilatura/markdownify miss some inline JS
    # (e.g. window.* assignments, JSON config blocks inside <script>)
    clean_html = re.sub(
        r"(?is)<script[^>]*>.*?</script>", "", html
    )

    if fmt in ("markdown", "text") and HAS_TRAFILATURA:
        tf_fmt = "markdown" if fmt == "markdown" else "txt"  # [#format-text-crash]
        extracted = trafilatura.extract(
            clean_html,
            output_format=tf_fmt,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if extracted:
            return title, extracted

    if fmt == "html":
        return title, html  # Return original HTML for html format

    if fmt == "markdown" and HAS_MARKDOWNIFY:
        return title, md(
            clean_html,
            heading_style="ATX",
            strip=["script", "style", "noscript"],  # [#noscript-strip-list]
        )

    # Last resort: regex strip
    clean = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
    clean = re.sub(r"(?i)<br\s*/?>", "\n", clean)
    clean = re.sub(
        r"(?i)</(p|div|section|article|li|tr|h[1-6])\s*>", "\n", clean
    )
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = html_lib.unescape(clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return title, clean


# ---------------------------------------------------------------------------
# Playwright [#playwright-proxy-auth, #ssl-playwright-propagation,
#             #playwright-none-timeout-crash]
# ---------------------------------------------------------------------------


def _playwright_proxy_config() -> dict | None:
    # Case-insensitive env var check [#proxy-env-case]
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
    )
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)
    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    config: dict = {"server": server}
    if parsed.username:
        config["username"] = unquote(parsed.username)
    if parsed.password:
        config["password"] = unquote(parsed.password)
    return config


def _fetch_playwright(url: str, timeout_ms: int, verify: bool) -> str:
    if timeout_ms <= 0:
        timeout_ms = 30_000

    with sync_playwright() as p:
        launch_args: dict = {"headless": True}
        proxy = _playwright_proxy_config()
        if proxy:
            launch_args["proxy"] = proxy

        browser = p.chromium.launch(**launch_args)
        try:
            ctx_args: dict = {"user_agent": USER_AGENT}
            if not verify:
                ctx_args["ignore_https_errors"] = True
            ctx = browser.new_context(**ctx_args)
            try:
                page = ctx.new_page()
                # Use "load" first, then wait briefly for JS to settle.
                # "networkidle" hangs on SPAs (Reddit, etc.) that never stop fetching.
                page.goto(url, timeout=timeout_ms, wait_until="load")
                # Give JS challenges and dynamic content a moment to render
                page.wait_for_timeout(min(3000, timeout_ms // 3))
                return page.content()
            finally:
                ctx.close()
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_output(url: str, title: str, content: str, fmt: str) -> str:
    if fmt == "html":
        return content
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = title.replace("\r", " ").replace("\n", " ").strip()
    return (
        "---\n"
        f"url: {json.dumps(url)}\n"
        f"fetched: {json.dumps(ts)}\n"
        f"title: {json.dumps(title)}\n"
        "---\n\n" + content
    )


# ---------------------------------------------------------------------------
# Main fetch orchestrator
# ---------------------------------------------------------------------------


def fetch(
    url: str,
    fmt: str = "markdown",
    timeout: int = 30,
    verify: bool = True,
    ignore_robots: bool = False,
    delay: float = 0.0,
) -> str:
    """Fetch a URL and return formatted content. Library entry point."""
    _validate_url(url)
    deadline = Deadline(timeout)
    ssl_retried = False

    if not verify:
        print("[warning] SSL verification disabled (--no-verify)", file=sys.stderr)

    client = _make_client(verify, deadline.remaining_int())
    try:
        # --- Robots compliance ---
        if not ignore_robots:
            try:
                allowed, crawl_delay = _robots_policy(url, client)
            except httpx.RequestError as e:
                # SSL failure during robots check — rebuild client now
                # so API shortcuts benefit from the fix
                err_str = str(e).lower()
                ssl_kw = ("ssl", "certificate", "handshake", "tls", "wrong version", "cert")
                if verify and any(k in err_str for k in ssl_kw):
                    ssl_retried = True
                    print(
                        "[warning] SSL failed during robots check — "
                        "switching to verify=False",
                        file=sys.stderr,
                    )
                    client.close()
                    client = _make_client(False, deadline.remaining_int())
                    try:
                        allowed, crawl_delay = _robots_policy(url, client)
                    except Exception:
                        allowed, crawl_delay = True, None
                else:
                    allowed, crawl_delay = True, None
            except Exception:
                allowed, crawl_delay = True, None
            if not allowed:
                raise FetchPageError(
                    f"robots.txt disallows scraping {url}. "
                    "Use --ignore-robots to override."
                )
            _respect_crawl_delay(urlparse(url).netloc, crawl_delay, delay)
        elif delay > 0:
            time.sleep(delay)

        # --- API shortcuts ---
        if fmt != "html":
            api_result = _try_api_shortcuts(url, client, deadline)
            if api_result:
                title, content = api_result
                return _format_output(url, title, content, fmt)

        # --- Tier 1: httpx ---
        html = None
        try:
            resp = client.get(url, timeout=deadline.remaining_int())
            resp.raise_for_status()
            json_out = _handle_json_response(resp, fmt)
            if json_out:
                return _format_output(url, url, json_out, fmt)

            # Detect JS challenge pages — httpx got 200 but content needs a browser
            raw_text = resp.text
            if HAS_PLAYWRIGHT and any(sig in raw_text[:2000] for sig in _CHALLENGE_SIGNATURES):
                print(
                    "[info] JS challenge detected — falling back to Playwright",
                    file=sys.stderr,
                )
                html = None  # Force Playwright fallback

            # Detect soft bot walls — HTTP 200 but thin visible content with gate phrases
            elif HAS_PLAYWRIGHT:
                visible = re.sub(r"<[^>]+>", " ", raw_text)
                visible = re.sub(r"\s+", " ", visible).strip()
                if len(visible) < _BOT_GATE_MAX_VISIBLE:
                    lower_vis = visible.lower()
                    gate = next(
                        (p for p in _BOT_GATE_PHRASES if p in lower_vis), None
                    )
                    if gate:
                        print(
                            f'[info] Soft bot wall detected ("{gate}") — '
                            "falling back to Playwright",
                            file=sys.stderr,
                        )
                        html = None  # Force Playwright fallback
                    else:
                        html = raw_text
                else:
                    html = raw_text

        except httpx.HTTPStatusError as e:
            status = e.response.status_code

            # Honor Retry-After on 429 [#retry-after-429]
            if status == 429:
                retry_after = _parse_retry_after(e.response)
                if retry_after and retry_after <= deadline.remaining():
                    print(
                        f"[info] 429 — honoring Retry-After: {retry_after:.0f}s",
                        file=sys.stderr,
                    )
                    time.sleep(retry_after)
                    try:
                        resp = client.get(url, timeout=deadline.remaining_int())
                        resp.raise_for_status()
                        json_out = _handle_json_response(resp, fmt)
                        if json_out:
                            return _format_output(url, url, json_out, fmt)
                        html = resp.text
                    except Exception:
                        pass

            if html is None:
                if status in PLAYWRIGHT_FALLBACK_CODES and HAS_PLAYWRIGHT:
                    print(
                        f"[warning] HTTP {status} — falling back to Playwright",
                        file=sys.stderr,
                    )
                else:
                    hint = ""
                    if status in PLAYWRIGHT_FALLBACK_CODES and not HAS_PLAYWRIGHT:
                        hint = (
                            " Install playwright for JS fallback: "
                            "pip install playwright && playwright install chromium"
                        )
                    raise FetchPageError(
                        f"HTTP {status} from {url}.{hint}"
                    ) from e

        except httpx.RequestError as e:
            err_str = str(e).lower()
            ssl_kw = ("ssl", "certificate", "handshake", "tls", "wrong version", "cert")

            if verify and any(k in err_str for k in ssl_kw):
                ssl_retried = True
                print(
                    "[warning] SSL failed — retrying with verify=False",
                    file=sys.stderr,
                )
                retry_client = _make_client(False, deadline.remaining_int())
                try:
                    resp = retry_client.get(url, timeout=deadline.remaining_int())
                    resp.raise_for_status()
                    json_out = _handle_json_response(resp, fmt)
                    if json_out:
                        return _format_output(url, url, json_out, fmt)
                    html = resp.text
                except Exception as e2:
                    print(f"[tier1 ssl-retry failed] {e2}", file=sys.stderr)
                finally:
                    retry_client.close()

            if html is None:
                if ssl_retried:
                    hint = "SSL verification failed even with auto-retry."
                else:
                    hint = f"{type(e).__name__}: {e}"

                if HAS_PLAYWRIGHT:
                    print(f"[tier1 failed] {hint}", file=sys.stderr)
                    print("[info] Falling back to Playwright...", file=sys.stderr)
                else:
                    suggestions = []
                    if not ssl_retried:
                        suggestions.append("--no-verify")
                    suggestions.append(
                        "pip install playwright && playwright install chromium"
                    )
                    raise FetchPageError(
                        f"{hint}\nNo fallback. Try: {' or '.join(suggestions)}"
                    ) from e

        # --- Tier 2: Playwright fallback ---
        if html is None and HAS_PLAYWRIGHT:
            try:
                pw_verify = verify and not ssl_retried  # [#ssl-playwright-propagation]
                remaining_ms = max(
                    int(deadline.remaining() * 1000),
                    _PLAYWRIGHT_MIN_TIMEOUT_MS,  # Don't starve Playwright
                )
                html = _fetch_playwright(url, remaining_ms, pw_verify)
            except FetchPageError:
                raise
            except Exception as e:
                raise FetchPageError(f"Playwright fallback failed: {e}") from e

        if html is None:
            raise FetchPageError("All fetch strategies failed.")

        title, content = _extract_content(html, fmt, url)
        return _format_output(url, title, content, fmt)

    finally:
        client.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Fetch web pages through corporate proxies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument(
        "--output", "-o", metavar="FILE", help="Write output to file"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "html", "text"],
        default="markdown",
        dest="fmt",
    )
    parser.add_argument(
        "--timeout", type=_positive_int, default=30, metavar="SEC"
    )
    parser.add_argument(
        "--delay", type=_non_negative_float, default=1.0, metavar="SEC",
        help="Delay between requests (rate limiting)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Disable SSL certificate verification",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Ignore robots.txt restrictions",
    )
    args = parser.parse_args()

    try:
        result = fetch(
            url=args.url,
            fmt=args.fmt,
            timeout=args.timeout,
            verify=not args.no_verify,
            ignore_robots=args.ignore_robots,
            delay=args.delay,
        )
    except FetchPageError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[saved] {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
