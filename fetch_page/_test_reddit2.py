from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", ignore_https_errors=True)
    page = ctx.new_page()
    page.goto(
        "https://www.reddit.com/r/Python/comments/1kd3c2n/what_are_the_best_python_libraries_for_llm/",
        timeout=25000,
        wait_until="networkidle",
    )

    print("Title:", page.title())
    
    # Check if actual post content is somewhere on the page
    h1 = page.query_selector("h1")
    print("H1:", h1.inner_text() if h1 else "none")
    
    # Look for post title specifically
    post_title = page.query_selector("[slot='title']")
    print("Post title slot:", post_title.inner_text() if post_title else "none")
    
    # Check for shreddit-post element
    posts = page.query_selector_all("shreddit-post")
    print(f"Posts found: {len(posts)}")
    if posts:
        for attr in ["post-title", "author", "subreddit-prefixed-name"]:
            val = posts[0].get_attribute(attr)
            print(f"  {attr}: {val}")
    
    # Get visible text content (first 500 chars)
    body_text = page.evaluate("document.body.innerText.substring(0, 1000)")
    print(f"\nVisible text:\n{body_text}")

    ctx.close()
    browser.close()
