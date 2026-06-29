"""
WallaHunter — Classifier
Takes raw listings from the scraper and assigns each one a category
based on price, keywords in title/description, and proximity to user.
"""

import logging
import math

from . import config

logger = logging.getLogger(__name__)


def classify_listings(listings: list[dict], seen: dict) -> list[dict]:
    """Classify a list of raw listings into categories.
    
    Each listing gets a 'category' field and a 'priority' field.
    Listings that don't match any category are excluded.
    Results are sorted by priority (highest first).
    
    Args:
        listings: Raw listings from the scraper.
        seen: Previously seen listings dict (for price drop detection).
    
    Returns:
        List of classified listings, sorted by priority.
    """
    classified = []

    for listing in listings:
        # Skip probable scams
        if listing["price"] < config.PRICE_MIN_FILTER:
            logger.debug(f"Skipping scam-priced listing: {listing['title']} ({listing['price']}€)")
            continue

        # Skip accessories that aren't actual consoles
        if _is_accessory_only(listing):
            logger.debug(f"Skipping accessory: {listing['title']}")
            continue

        # Classify
        category = _determine_category(listing)
        if category is None:
            continue

        listing["category"] = category
        listing["priority"] = config.CATEGORY_DISPLAY[category]["priority"]
        listing["category_emoji"] = config.CATEGORY_DISPLAY[category]["emoji"]
        listing["category_label"] = config.CATEGORY_DISPLAY[category]["label"]

        # Check for price drop
        from . import storage
        old_price = storage.detect_price_drop(listing["id"], listing["price"], seen)
        if old_price is not None:
            listing["price_drop"] = True
            listing["old_price"] = old_price
        else:
            listing["price_drop"] = False

        classified.append(listing)

    # Sort by priority (1 = highest)
    classified.sort(key=lambda x: x["priority"])

    logger.info(f"Classified {len(classified)} listings out of {len(listings)} raw results.")
    return classified


def _determine_category(listing: dict) -> str | None:
    """Determine the category for a single listing.
    
    Categories are checked in priority order. A listing gets the
    HIGHEST priority category it qualifies for.
    
    Args:
        listing: A single listing dict.
    
    Returns:
        Category string constant, or None if no category matches.
    """
    price = listing["price"]
    text = f"{listing.get('title', '')} {listing.get('description', '')}".lower()
    has_repair_keywords = _has_keywords(text, config.REPAIR_KEYWORDS)
    has_bundle_keywords = _has_keywords(text, config.BUNDLE_KEYWORDS)

    # ⚡ CHOLLO EXTREMO — absurdly cheap, whatever condition
    if price <= config.PRICE_CHOLLO_MAX:
        return config.CATEGORY_CHOLLO

    # 🔧 REPARAR — cheap OR mentions repair/broken keywords
    if price <= config.PRICE_REPARAR_MAX or (has_repair_keywords and price <= config.PRICE_BARATITO_MAX):
        return config.CATEGORY_REPARAR

    # 📦 LOTE/PACK — bundle deal at reasonable price
    if has_bundle_keywords and price <= config.PRICE_LOTE_MAX:
        return config.CATEGORY_LOTE

    # 💰 BARATITO — just a good price, no issues mentioned
    if price <= config.PRICE_BARATITO_MAX:
        return config.CATEGORY_BARATITO

    # 🤝 PARA NEGOCIAR — nearby and worth trying to haggle
    if price <= config.PRICE_NEGOCIAR_MAX:
        distance = _calculate_distance(listing)
        if distance is not None and distance <= config.NEARBY_RADIUS_KM:
            return config.CATEGORY_NEGOCIAR

    return None


def _is_accessory_only(listing: dict) -> bool:
    """Check if a listing is for an accessory, not a console.
    
    We check if the title matches known accessory-only patterns.
    Only excludes items that seem to be ONLY accessories.
    
    Args:
        listing: A single listing dict.
    
    Returns:
        True if this is likely an accessory-only listing.
    """
    title_lower = listing.get("title", "").lower().strip()

    # Check if title matches any accessory-only pattern
    for keyword in config.ACCESSORY_ONLY_KEYWORDS:
        if keyword in title_lower:
            # But if the price is high enough, it might be console + accessory
            if listing["price"] >= 120:
                return False
            return True

    return False


def _has_keywords(text: str, keywords: list[str]) -> bool:
    """Check if any of the keywords appear in the text.
    
    Args:
        text: Text to search (already lowered).
        keywords: List of keywords to look for.
    
    Returns:
        True if any keyword is found.
    """
    return any(kw in text for kw in keywords)


def _calculate_distance(listing: dict) -> float | None:
    """Calculate distance in km between listing and user location.
    
    Uses the Haversine formula for great-circle distance.
    
    Args:
        listing: Listing dict with latitude/longitude fields.
    
    Returns:
        Distance in km, or None if coordinates are missing.
    """
    lat = listing.get("latitude")
    lon = listing.get("longitude")

    if lat is None or lon is None:
        # If no coordinates, check city name
        city = listing.get("city", "").lower()
        malaga_cities = [
            "málaga", "malaga", "rincón de la victoria", "rincon de la victoria",
            "torre del mar", "vélez-málaga", "velez-malaga", "torremolinos",
            "benalmádena", "benalmadena", "fuengirola", "mijas",
            "alhaurín", "alhaurin", "cártama", "cartama",
            "nerja", "torrox", "axarquía", "axarquia",
        ]
        if any(c in city for c in malaga_cities):
            return 15.0  # Approximate — within Málaga province
        return None

    # Haversine formula
    R = 6371  # Earth radius in km
    lat1 = math.radians(config.USER_LATITUDE)
    lat2 = math.radians(lat)
    dlat = math.radians(lat - config.USER_LATITUDE)
    dlon = math.radians(lon - config.USER_LONGITUDE)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
