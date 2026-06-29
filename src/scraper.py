"""
WallaHunter — Scraper
Uses Playwright to search Wallapop and extract listing data.

Strategy:
1. Navigate to Wallapop search URL with Playwright (headless Chromium)
2. Intercept the internal API responses (structured JSON data)
3. If interception fails, fall back to DOM parsing
4. Return normalized listing dicts

Anti-detection:
- Realistic browser context (viewport, locale, timezone)
- Random delays between searches (3-8 seconds)
- Running on GitHub Actions = different IP every execution
"""

import json
import logging
import random
import time
import urllib.parse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from . import config

logger = logging.getLogger(__name__)


def scrape_all_queries() -> list[dict]:
    """Run all configured search queries and return deduplicated listings.
    
    Returns:
        List of normalized listing dicts.
    """
    all_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="es-ES",
            timezone_id="Europe/Madrid",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        # Remove the webdriver flag to appear more human
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = context.new_page()

        # Apply stealth mode to bypass CloudFront WAF
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
            logger.debug("  Playwright stealth applied successfully.")
        except Exception as e:
            logger.warning(f"  Could not apply playwright-stealth: {e}")

        # Handle cookie consent on first visit
        _handle_cookie_consent(page)

        for i, query in enumerate(config.SEARCH_QUERIES):
            logger.info(f"[{i+1}/{len(config.SEARCH_QUERIES)}] Searching: '{query['keywords']}' ({query['console']})")

            try:
                listings = _search_single_query(page, query)
                all_listings.extend(listings)
                logger.info(f"  → Found {len(listings)} listings")
            except Exception as e:
                logger.error(f"  → Error searching '{query['keywords']}': {e}")

            # Random delay between searches (not after the last one)
            if i < len(config.SEARCH_QUERIES) - 1:
                delay = random.uniform(3, 8)
                logger.debug(f"  Waiting {delay:.1f}s before next search...")
                time.sleep(delay)

        browser.close()

    # Deduplicate by listing ID
    unique = _deduplicate(all_listings)
    logger.info(f"Total unique listings: {len(unique)} (from {len(all_listings)} raw)")
    return unique


def _handle_cookie_consent(page) -> None:
    """Navigate to Wallapop and dismiss the cookie consent banner.
    
    Args:
        page: Playwright page instance.
    """
    try:
        logger.debug("Navigating to Wallapop to handle cookies...")
        page.goto(config.WALLAPOP_BASE_URL, wait_until="domcontentloaded", timeout=20000)

        # Try common cookie consent button selectors
        consent_selectors = [
            "#onetrust-accept-btn-handler",
            "button[id*='accept']",
            "[data-testid='accept-cookies']",
            "button:has-text('Aceptar')",
            "button:has-text('Aceptar todo')",
            "button:has-text('Aceptar todas')",
            "button:has-text('Accept')",
        ]

        for selector in consent_selectors:
            try:
                page.click(selector, timeout=3000)
                logger.debug(f"Cookie consent dismissed with: {selector}")
                time.sleep(1)
                return
            except PlaywrightTimeout:
                continue

        logger.debug("No cookie consent banner found (might be OK).")
    except Exception as e:
        logger.warning(f"Could not handle cookie consent: {e}")


def _search_single_query(page, query: dict) -> list[dict]:
    """Execute a single search query and return listings.
    
    Uses API response interception as primary method,
    with DOM parsing as fallback.
    
    Args:
        page: Playwright page instance.
        query: Search query dict with 'keywords' and 'console'.
    
    Returns:
        List of normalized listing dicts.
    """
    # Storage for intercepted API responses
    api_responses = []

    def on_response(response):
        """Capture Wallapop API search responses."""
        url = response.url
        if "api.wallapop.com" in url and "search" in url:
            try:
                if response.status == 200:
                    body = response.json()
                    api_responses.append(body)
                    logger.debug(f"  Intercepted API response from: {url[:100]}...")
            except Exception:
                pass

    # Set up response interception
    page.on("response", on_response)

    # Build search URL — Wallapop redirects /app/search to /search
    params = {
        "keywords": query["keywords"],
        "latitude": config.USER_LATITUDE,
        "longitude": config.USER_LONGITUDE,
        "order_by": "newest",
        "max_sale_price": config.PRICE_NEGOCIAR_MAX,
    }
    search_url = f"{config.WALLAPOP_BASE_URL}/search?{urllib.parse.urlencode(params)}"

    try:
        # Navigate to search page
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

        # Wait for listing cards to actually appear in the DOM
        try:
            page.wait_for_selector('a[href^="/item/"]', timeout=15000)
            logger.debug("  Listing cards detected in DOM.")
        except PlaywrightTimeout:
            logger.warning("  No listing cards appeared within timeout.")

        # Extra wait for all cards to render
        page.wait_for_timeout(2000)

        # === DIAGNOSTIC: Capture what Playwright actually sees ===
        import os
        debug_dir = "debug"
        os.makedirs(debug_dir, exist_ok=True)
        safe_kw = query["keywords"].replace(" ", "_")

        # Screenshot
        screenshot_path = f"{debug_dir}/search_{safe_kw}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"  📸 Screenshot saved: {screenshot_path}")

        # Page URL (check for redirects)
        logger.info(f"  📍 Current URL: {page.url}")

        # HTML snippet (first 2000 chars of body)
        body_html = page.inner_html("body")[:3000]
        html_path = f"{debug_dir}/html_{safe_kw}.txt"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(body_html)
        logger.info(f"  📄 HTML dump saved: {html_path}")

        # Count all <a> tags to understand the DOM
        all_links = page.query_selector_all("a")
        item_links = page.query_selector_all('a[href*="/item/"]')
        logger.info(f"  🔗 Total <a> tags: {len(all_links)}, <a> with /item/: {len(item_links)}")

    except PlaywrightTimeout:
        logger.warning(f"  Page load timeout for '{query['keywords']}'")
    except Exception as e:
        logger.error(f"  Navigation error: {e}")
    finally:
        # Remove listener to avoid capturing responses from next search
        page.remove_listener("response", on_response)

    # Try API data first (preferred — structured JSON)
    if api_responses:
        logger.debug(f"  Processing {len(api_responses)} API response(s)...")
        listings = _parse_api_responses(api_responses, query["console"])
        if listings:
            return listings

    # Fallback: parse from DOM (primary method based on live testing)
    logger.info(f"  Parsing listings from DOM...")
    return _parse_dom(page, query["console"])


def _parse_api_responses(api_responses: list[dict], console_type: str) -> list[dict]:
    """Parse listings from intercepted Wallapop API responses.
    
    The API response format may vary, so we handle multiple possible structures.
    
    Args:
        api_responses: List of parsed JSON API responses.
        console_type: Console type string (e.g., "PS5").
    
    Returns:
        List of normalized listing dicts.
    """
    listings = []

    for data in api_responses:
        # The API may use different keys for the listings array
        items = (
            data.get("search_objects")
            or data.get("items")
            or data.get("data", {}).get("items")
            or data.get("data", {}).get("search_objects")
            or []
        )

        for item in items:
            listing = _normalize_api_item(item, console_type)
            if listing:
                listings.append(listing)

    return listings


def _normalize_api_item(item: dict, console_type: str) -> dict | None:
    """Normalize a single API item into our standard listing format.
    
    Handles various possible API response structures gracefully.
    
    Args:
        item: Raw API item dict.
        console_type: Console type string.
    
    Returns:
        Normalized listing dict, or None if parsing fails.
    """
    try:
        # Extract price (handle multiple formats)
        price_raw = item.get("price") or item.get("sale_price") or item.get("salePrice")
        if isinstance(price_raw, dict):
            price = float(price_raw.get("amount", 0))
        else:
            price = float(price_raw or 0)

        # Extract location
        location = item.get("location", {})
        lat = location.get("approximated_latitude") or location.get("latitude")
        lon = location.get("approximated_longitude") or location.get("longitude")
        city = location.get("city", location.get("postal_code", "Desconocida"))

        # Extract images
        images = item.get("images", [])
        image_url = ""
        if images and isinstance(images, list):
            first_img = images[0]
            if isinstance(first_img, dict):
                urls = first_img.get("urls_by_size", {})
                image_url = (
                    urls.get("medium")
                    or urls.get("large")
                    or urls.get("small")
                    or first_img.get("original")
                    or first_img.get("url")
                    or ""
                )
            elif isinstance(first_img, str):
                image_url = first_img

        # Build web URL
        web_slug = item.get("web_slug", "")
        item_id = str(item.get("id", ""))
        if web_slug:
            url = f"{config.WALLAPOP_BASE_URL}/item/{web_slug}"
        elif item_id:
            url = f"{config.WALLAPOP_BASE_URL}/item/{item_id}"
        else:
            url = ""

        return {
            "id": item_id,
            "title": item.get("title", "Sin título"),
            "description": item.get("description", ""),
            "price": price,
            "currency": item.get("currency_code", item.get("currency", "EUR")),
            "city": city,
            "latitude": float(lat) if lat else None,
            "longitude": float(lon) if lon else None,
            "url": url,
            "image": image_url,
            "console_type": console_type,
            "creation_date": item.get("creation_date", ""),
        }
    except Exception as e:
        logger.error(f"  Error parsing API item: {e}")
        return None


def _parse_dom(page, console_type: str) -> list[dict]:
    """Fallback: parse listings directly from the rendered DOM.
    
    This is less reliable than API interception but works when
    the API response can't be captured.
    
    Args:
        page: Playwright page instance.
        console_type: Console type string.
    
    Returns:
        List of normalized listing dicts.
    """
    listings = []

    # Wallapop uses CSS modules with hashed class names, so we target
    # stable attributes instead. Listing cards are <a> tags linking to /item/.
    card_selector = 'a[href^="/item/"]'

    try:
        cards = page.query_selector_all(card_selector)
    except Exception as e:
        logger.error(f"  Error querying cards: {e}")
        cards = []

    if not cards:
        logger.warning("  No listing cards found in DOM.")
        return []

    logger.info(f"  Found {len(cards)} listing cards in DOM.")

    for card in cards:
        try:
            listing = _parse_dom_card(card, console_type)
            if listing:
                listings.append(listing)
        except Exception as e:
            logger.debug(f"  Error parsing DOM card: {e}")

    return listings


def _parse_dom_card(card, console_type: str) -> dict | None:
    """Parse a single listing card from the DOM.
    
    Args:
        card: Playwright element handle for the card.
        console_type: Console type string.
    
    Returns:
        Normalized listing dict, or None if parsing fails.
    """
    # The card itself is an <a> tag with href like /item/slug-12345
    href = card.get_attribute("href") or ""
    if not href or not href.startswith("/item/"):
        return None

    # Extract listing ID from URL (last segment, often contains numeric ID)
    listing_id = href.rstrip("/").split("/")[-1]
    full_url = f"{config.WALLAPOP_BASE_URL}{href}"

    # Title — from <h3> tag inside the card, or from the title/aria-label attribute
    title = ""
    title_el = card.query_selector("h3")
    if title_el:
        title = (title_el.text_content() or "").strip()
    if not title:
        title = card.get_attribute("title") or card.get_attribute("aria-label") or ""
    title = title.strip()

    # Price — from <strong> tag inside the card
    price = 0.0
    price_el = card.query_selector("strong")
    if price_el:
        price_text = (price_el.text_content() or "").strip()
        # Remove currency symbols and whitespace, handle "120 €" or "120€" or "1.200 €"
        price_clean = price_text.replace("€", "").replace("\u20ac", "").strip()
        price_clean = price_clean.replace(".", "").replace(",", ".")
        try:
            price = float(price_clean) if price_clean else 0.0
        except ValueError:
            price = 0.0

    # Location — not available in search grid cards per inspection.
    # Wallapop only shows shipping badges, not city names.
    # Location will be inferred from the search coordinates filter.
    city = "Zona configurada"

    if not title and price == 0:
        return None

    return {
        "id": listing_id,
        "title": title,
        "description": "",
        "price": price,
        "currency": "EUR",
        "city": city,
        "latitude": None,
        "longitude": None,
        "url": full_url,
        "image": "",
        "console_type": console_type,
        "creation_date": "",
    }


def _deduplicate(listings: list[dict]) -> list[dict]:
    """Remove duplicate listings based on ID.
    
    Args:
        listings: List of listing dicts.
    
    Returns:
        Deduplicated list preserving first occurrence order.
    """
    seen_ids = set()
    unique = []

    for listing in listings:
        lid = listing.get("id", "")
        if lid and lid not in seen_ids:
            seen_ids.add(lid)
            unique.append(listing)

    return unique
