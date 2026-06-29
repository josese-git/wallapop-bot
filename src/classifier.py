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
    from .ai_classifier import analyze_with_ai
    classified = []

    for listing in listings:
        price = listing["price"]
        title = listing.get("title", "")
        description = listing.get("description", "")

        # 1. Try AI classification first
        ai_analysis = analyze_with_ai(title, description, price)

        if ai_analysis is not None:
            # AI classified the listing
            if not ai_analysis.is_console:
                logger.debug(f"AI skipped listing (not a console): {title} ({ai_analysis.explanation})")
                continue

            # It IS a console according to AI!
            category = None

            # ⚡ CHOLLO EXTREMO — absurdly cheap
            if price <= config.PRICE_CHOLLO_MAX:
                category = config.CATEGORY_CHOLLO
            # 🔧 REPARAR — AI says it's broken, or price fits
            elif ai_analysis.is_broken_or_for_parts or price <= config.PRICE_REPARAR_MAX:
                category = config.CATEGORY_REPARAR
            # 📦 LOTE/PACK — AI says it's a bundle, or title mentions bundle keywords
            elif ai_analysis.is_bundle or _has_keywords(title.lower(), config.BUNDLE_KEYWORDS):
                category = config.CATEGORY_LOTE
            # 💰 BARATITO — just a good price
            elif price <= config.PRICE_BARATITO_MAX:
                category = config.CATEGORY_BARATITO
            # 🤝 PARA NEGOCIAR — nearby and worth haggling
            elif price <= config.PRICE_NEGOCIAR_MAX:
                distance = _calculate_distance(listing)
                if distance is not None and distance <= config.NEARBY_RADIUS_KM:
                    category = config.CATEGORY_NEGOCIAR

            if category is None:
                continue

            logger.info(f"AI matched console: {title} ({price}€) -> Category: {category} ({ai_analysis.explanation})")

        else:
            # 2. Fallback to deterministic rules if AI key is missing or failed
            # Skip probable scams / games / accessories by price
            if price < config.PRICE_MIN_FILTER:
                logger.debug(f"Skipping cheap listing (likely games/accessories): {title} ({price}€)")
                continue

            # Ensure the title actually refers to the target console
            if not _contains_console_keywords(listing):
                logger.debug(f"Skipping unrelated listing (title lacks console keywords): {title}")
                continue

            # Skip accessories that aren't actual consoles
            if _is_accessory_only(listing):
                logger.debug(f"Skipping accessory: {title}")
                continue

            # Classify using deterministic rules
            category = _determine_category(listing)
            if category is None:
                continue

        # Set listing classification fields
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
    """Check if a listing is for an accessory or game, not a console.
    
    Returns:
        True if this is likely an accessory or game listing.
    """
    title = listing.get("title", "").strip()
    title_lower = title.lower()
    
    # 1. Split title and strip starter filler words to inspect the actual first word
    words = title_lower.split()
    if not words:
        return True
        
    while words and words[0] in config.START_FILLER_WORDS:
        words.pop(0)
        
    if not words:
        return True
        
    first_word = "".join(c for c in words[0] if c.isalnum())
    
    # Check if the title starts with a console keyword
    starts_with_console = any(kw in first_word for kw in ["ps5", "playstation", "xbox", "series", "consola", "console"])
    
    # Check if title has strong console indicators anywhere
    has_console_indicator = any(kw in title_lower for kw in ["consola", "console", "pack", "lote"]) or starts_with_console
    
    # 2. Check ALWAYS accessory keywords (blocked anywhere in title)
    always_accessory = [
        "volante", "pedales", "shifter", "g29", "g920", "g923", "thrustmaster", "t150", "t300", "t248", "logitech", "playseat", "cockpit",
        "psvr", "psvr2", "gafas", "oculus", "meta quest",
        "cascos", "auriculares", "headset", "headphones", "pulse 3d", "pulse elite",
        "portal", "playstation portal", "remote play",
        "funda", "carcasa", "skin", "vinilo", "soporte", "base de carga", "estacion de carga", "teclado", "raton", "ratón", "cable", "cargador", "adaptador", "cámara", "camara", "media remote", "placas", "chasis", "refrigeracion", "ventilador", "hdmi", "ssd", "disco duro", "tarjeta de memoria", "caja vacia", "caja vacía", "solo caja", "caja original",
        "cuenta", "cuentas", "suscripcion", "suscripción", "plus", "psn", "game pass", "gamepass", "codigo", "código", "card", "tarjeta prepago"
    ]
    for kw in always_accessory:
        if kw in title_lower:
            return True
            
    # 3. Check start words (if title starts with these, it is an accessory)
    if first_word in config.ACCESSORY_START_WORDS:
        return True
        
    # 4. Check conditional accessory keywords (blocked unless console indicator is present)
    conditional_accessory = ["mando", "mandos", "controller", "gamepad", "joystick", "dualsense", "dual sense", "juego", "juegos", "game", "games"]
    for kw in conditional_accessory:
        if kw in title_lower:
            if not has_console_indicator:
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


def _contains_console_keywords(listing: dict) -> bool:
    """Verify that the listing title contains console keywords.
    
    Prevents unrelated search results from being classified.
    """
    title_lower = listing.get("title", "").lower()
    console_type = listing.get("console_type", "")
    
    if console_type == "PS5":
        return any(kw in title_lower for kw in ["ps5", "playstation 5", "play station 5", "play 5"])
    elif console_type == "Xbox Series X":
        # Must contain "xbox" AND some variation of "series x" or "sx"
        has_xbox = "xbox" in title_lower
        has_series_x = any(kw in title_lower for kw in ["series x", "seriesx", "sx"])
        return has_xbox and has_series_x
        
    return False
