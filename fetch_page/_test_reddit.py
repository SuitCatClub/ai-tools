from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="ResearchFetcher/2.0", ignore_https_errors=True)
    page = ctx.new_page()
    page.goto(
        "https://www.reddit.com/r/Python/comments/1kd3c2n/what_are_the_best_python_libraries_for_llm/",
        timeout=20000,
        wait_until="networkidle",
    )

    print("Title:", page.title())

    # Check for interstitial component
    js_interstitial = 'document.querySelector("shreddit-interstitial") ? "found" : "not found"'
    print("Interstitial:", page.evaluate(js_interstitial))

    # Look for slotted elements (Reddit uses web components)
    js_slots = """
    Array.from(document.querySelectorAll("[slot]"))
        .map(e => e.tagName + " slot=" + e.getAttribute("slot") + " text=" + e.textContent.trim().substring(0,80))
    """
    for item in page.evaluate(js_slots):
        print("  Slot:", item)

    # Check for Accept All type buttons in any shadow DOM
    js_buttons = """
    (() => {
        const results = [];
        document.querySelectorAll("*").forEach(el => {
            if (el.shadowRoot) {
                el.shadowRoot.querySelectorAll("button").forEach(btn => {
                    const text = btn.textContent.trim();
                    if (text && text.length < 60) {
                        results.push(el.tagName + " > button: " + text);
                    }
                });
            }
        });
        return results;
    })()
    """
    shadow_buttons = page.evaluate(js_buttons)
    print(f"\nShadow DOM buttons ({len(shadow_buttons)}):")
    for b in shadow_buttons[:20]:
        print("  ", b)

    ctx.close()
    browser.close()
