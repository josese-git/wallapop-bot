"""
WallaHunter — Storage
Manages the seen_listings.json file to track which listings
have been already notified, detect price drops, and prevent
duplicate notifications between GitHub Actions runs.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from . import config

logger = logging.getLogger(__name__)


def load_seen_listings() -> dict:
    """Load previously seen listings from JSON file.
    
    Returns:
        dict: Mapping of listing_id -> {price, title, first_seen, last_notified_price, console}
    """
    path = config.SEEN_LISTINGS_PATH
    if not os.path.exists(path):
        logger.info("No seen_listings.json found, starting fresh.")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} previously seen listings.")
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading {path}: {e}. Starting fresh.")
        return {}


def save_seen_listings(seen: dict) -> None:
    """Save seen listings to JSON file, with automatic cleanup of old entries.
    
    Args:
        seen: The seen listings dict to save.
    """
    # Clean up old entries first
    cleaned = _cleanup_old_entries(seen)

    path = config.SEEN_LISTINGS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(cleaned)} seen listings ({len(seen) - len(cleaned)} old entries removed).")


def is_new_listing(listing_id: str, seen: dict) -> bool:
    """Check if a listing has never been seen before.
    
    Args:
        listing_id: The Wallapop listing ID.
        seen: The seen listings dict.
    
    Returns:
        True if this listing has never been notified.
    """
    return listing_id not in seen


def detect_price_drop(listing_id: str, current_price: float, seen: dict) -> float | None:
    """Check if a listing's price has dropped since we last saw it.
    
    Args:
        listing_id: The Wallapop listing ID.
        current_price: The current price.
        seen: The seen listings dict.
    
    Returns:
        The previous price if it dropped, None otherwise.
    """
    if listing_id not in seen:
        return None

    previous_price = seen[listing_id].get("last_notified_price", seen[listing_id].get("price", 0))
    if current_price < previous_price:
        return previous_price

    return None


def mark_as_seen(listing: dict, seen: dict) -> None:
    """Mark a listing as seen/notified.
    
    Args:
        listing: The listing dict with id, price, title, console_type.
        seen: The seen listings dict (modified in place).
    """
    now = datetime.now(timezone.utc).isoformat()
    listing_id = listing["id"]

    if listing_id in seen:
        # Update existing entry
        seen[listing_id]["last_notified_price"] = listing["price"]
        seen[listing_id]["last_seen"] = now
    else:
        # New entry
        seen[listing_id] = {
            "price": listing["price"],
            "last_notified_price": listing["price"],
            "title": listing.get("title", ""),
            "console": listing.get("console_type", ""),
            "first_seen": now,
            "last_seen": now,
        }


def _cleanup_old_entries(seen: dict) -> dict:
    """Remove entries older than MAX_LISTING_AGE_DAYS.
    
    Args:
        seen: The seen listings dict.
    
    Returns:
        Cleaned dict with old entries removed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.MAX_LISTING_AGE_DAYS)
    cleaned = {}

    for listing_id, data in seen.items():
        try:
            last_seen_str = data.get("last_seen", data.get("first_seen", ""))
            if not last_seen_str:
                cleaned[listing_id] = data
                continue

            last_seen = datetime.fromisoformat(last_seen_str)
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)

            if last_seen >= cutoff:
                cleaned[listing_id] = data
        except (ValueError, TypeError):
            # If we can't parse the date, keep the entry
            cleaned[listing_id] = data

    return cleaned
