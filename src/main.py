"""
WallaHunter — Main Orchestrator
Entry point for the Wallapop deal scanner.

Flow:
1. Load previously seen listings from JSON
2. Scrape Wallapop for each configured search query
3. Classify listings into deal categories
4. Filter out already-notified listings (unless price dropped)
5. Send Telegram notifications for new/updated deals
6. Save updated seen listings to JSON
"""

import logging
import sys
import time
from collections import Counter

from . import config
from .scraper import scrape_all_queries
from .classifier import classify_listings
from .notifier import (
    send_listing_notification,
    send_summary,
    send_error_alert,
)
from .storage import (
    load_seen_listings,
    save_seen_listings,
    is_new_listing,
    detect_price_drop,
    mark_as_seen,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("WallaHunter")


def main() -> None:
    """Main entry point — run a single scan cycle."""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("🎮 WallaHunter — Starting scan")
    logger.info("=" * 60)

    # Validate Telegram configuration
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning(
            "⚠️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. "
            "Notifications will be skipped."
        )

    try:
        _run_scan()
    except Exception as e:
        logger.error(f"💥 Critical error during scan: {e}", exc_info=True)
        try:
            send_error_alert(f"Error crítico: {e}")
        except Exception:
            pass

    elapsed = time.time() - start_time
    logger.info(f"⏱️  Scan completed in {elapsed:.1f}s")
    logger.info("=" * 60)


def _run_scan() -> None:
    """Execute the full scan pipeline."""
    # Step 1: Load seen listings
    logger.info("📂 Loading previously seen listings...")
    seen = load_seen_listings()
    logger.info(f"   {len(seen)} listings in history")

    # Step 2: Scrape Wallapop
    logger.info("🔍 Scraping Wallapop...")
    raw_listings = scrape_all_queries()
    logger.info(f"   Found {len(raw_listings)} raw listings")

    if not raw_listings:
        logger.info("   No listings found. Nothing to do.")
        save_seen_listings(seen)  # Save to trigger cleanup
        return

    # Step 3: Classify listings
    logger.info("🧠 Classifying listings...")
    classified = classify_listings(raw_listings, seen)
    logger.info(f"   {len(classified)} listings matched our criteria")

    if not classified:
        logger.info("   No listings match our filters. Better luck next scan!")
        save_seen_listings(seen)
        return

    # Step 4: Filter new + price drops
    logger.info("🔎 Filtering new and price-dropped listings...")
    to_notify = []

    for listing in classified:
        lid = listing["id"]

        if is_new_listing(lid, seen):
            listing["is_new"] = True
            to_notify.append(listing)
        elif listing.get("price_drop"):
            listing["is_new"] = False
            to_notify.append(listing)

    logger.info(
        f"   {len(to_notify)} new notifications "
        f"({sum(1 for l in to_notify if l.get('is_new'))} new, "
        f"{sum(1 for l in to_notify if l.get('price_drop'))} price drops)"
    )

    # Step 5: Send notifications
    if to_notify:
        logger.info("📱 Sending Telegram notifications...")
        sent_count = 0
        for listing in to_notify:
            success = send_listing_notification(listing)
            if success:
                sent_count += 1
            # Small delay between messages to avoid Telegram rate limits
            time.sleep(0.5)

        logger.info(f"   Sent {sent_count}/{len(to_notify)} notifications")

        # Send summary
        category_counts = Counter(l["category"] for l in to_notify)
        new_count = sum(1 for l in to_notify if l.get("is_new"))
        price_drop_count = sum(1 for l in to_notify if l.get("price_drop"))
        send_summary(
            total_found=len(raw_listings),
            new_count=new_count,
            price_drops=price_drop_count,
            categories=dict(category_counts),
        )
    else:
        logger.info("   No new notifications to send.")

    # Step 6: Mark all classified listings as seen
    # (even ones we didn't notify about, to prevent re-checking)
    for listing in classified:
        mark_as_seen(listing, seen)

    # Step 7: Save
    logger.info("💾 Saving seen listings...")
    save_seen_listings(seen)
    logger.info("   Done!")

    # Log summary
    if to_notify:
        logger.info("📊 Summary:")
        for listing in to_notify:
            tag = "🆕" if listing.get("is_new") else "📉"
            logger.info(
                f"   {tag} [{listing['category_label']}] "
                f"{listing['title'][:50]} — {listing['price']}€"
            )


if __name__ == "__main__":
    main()
