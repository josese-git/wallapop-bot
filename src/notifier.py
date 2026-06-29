"""
WallaHunter — Telegram Notifier
Sends formatted deal alerts to Telegram using the Bot API.
Different formatting and urgency per category.
"""

import logging

import requests

from . import config

logger = logging.getLogger(__name__)

# Telegram API base
API_BASE = "https://api.telegram.org/bot{token}"


def send_listing_notification(listing: dict) -> bool:
    """Send a single listing notification to Telegram.
    
    Args:
        listing: Classified listing dict with category info.
    
    Returns:
        True if sent successfully, False otherwise.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Skipping notification.")
        return False

    message = _format_listing_message(listing)
    disable_notification = listing.get("priority", 5) > 2  # Silent for lower priority

    return _send_message(
        text=message,
        parse_mode="HTML",
        disable_notification=disable_notification,
        disable_web_page_preview=False,
    )


def send_summary(total_found: int, new_count: int, price_drops: int, categories: dict) -> bool:
    """Send a scan summary message.
    
    Args:
        total_found: Total listings found in this scan.
        new_count: Number of new listings notified.
        price_drops: Number of price drop re-notifications.
        categories: Dict of category -> count.
    
    Returns:
        True if sent successfully.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False

    if new_count == 0 and price_drops == 0:
        # Don't spam with "nothing found" messages
        return True

    lines = ["━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"📊 <b>Resumen del scan</b>")
    lines.append(f"🔍 Total encontrados: {total_found}")
    lines.append(f"🆕 Nuevos notificados: {new_count}")

    if price_drops > 0:
        lines.append(f"📉 Bajadas de precio: {price_drops}")

    if categories:
        lines.append("")
        for cat, count in categories.items():
            display = config.CATEGORY_DISPLAY.get(cat, {})
            emoji = display.get("emoji", "❓")
            label = display.get("label", cat)
            lines.append(f"  {emoji} {label}: {count}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 <i>WallaHunter Bot</i>")

    return _send_message(
        text="\n".join(lines),
        parse_mode="HTML",
        disable_notification=True,
    )


def send_error_alert(error_message: str) -> bool:
    """Send an error alert to Telegram.
    
    Args:
        error_message: Description of the error.
    
    Returns:
        True if sent successfully.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False

    text = (
        f"🚨 <b>WallaHunter Error</b>\n\n"
        f"{error_message}\n\n"
        f"<i>El bot sigue funcionando, reintentará en el próximo scan.</i>"
    )
    return _send_message(text=text, parse_mode="HTML", disable_notification=False)


def send_startup_message() -> bool:
    """Send a startup confirmation message."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False

    text = (
        "🎮 <b>WallaHunter activado</b>\n\n"
        "Buscando:\n"
        "• PS5\n"
        "• Xbox Series X\n\n"
        f"📍 Ubicación: Rincón de la Victoria\n"
        f"💶 Precio máximo: {config.PRICE_NEGOCIAR_MAX}€\n"
        f"🔄 Escaneando cada 5 minutos\n\n"
        "🤖 <i>Te avisaré en cuanto encuentre algo bueno.</i>"
    )
    return _send_message(text=text, parse_mode="HTML", disable_notification=True)


# ═══════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════


def _format_listing_message(listing: dict) -> str:
    """Format a listing into a Telegram-friendly HTML message.
    
    Args:
        listing: Classified listing dict.
    
    Returns:
        Formatted HTML string.
    """
    emoji = listing.get("category_emoji", "🎮")
    label = listing.get("category_label", "DEAL")
    title = _escape_html(listing.get("title", "Sin título"))
    price = listing.get("price", 0)
    city = _escape_html(listing.get("city", "Desconocida"))
    description = _escape_html(listing.get("description", ""))
    url = listing.get("url", "")
    console = listing.get("console_type", "Consola")
    distance = listing.get("distance_km")

    # Header with category emphasis
    lines = []

    if listing.get("price_drop"):
        old_price = listing.get("old_price", 0)
        lines.append(f"📉 <b>¡BAJADA DE PRECIO!</b> 📉")
        lines.append(f"<s>{old_price}€</s> → <b>{price}€</b>")
        lines.append("")

    lines.append(f"{emoji} <b>{label}</b> {emoji}")
    lines.append("")
    lines.append(f"🎮 <b>{title}</b>")
    lines.append(f"🏷️ {console}")
    lines.append(f"💶 <b>{price}€</b>")

    # Location with distance if available
    location_line = f"📍 {city}"
    if distance is not None:
        location_line += f" ({distance:.0f}km de ti)"
    lines.append(location_line)

    # Description preview (first 150 chars)
    if description:
        desc_preview = description[:150]
        if len(description) > 150:
            desc_preview += "..."
        lines.append(f'📝 "<i>{desc_preview}</i>"')

    # Link
    if url:
        lines.append("")
        lines.append(f'🔗 <a href="{url}">Ver en Wallapop</a>')

    # Footer
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 <i>WallaHunter Bot</i>")

    return "\n".join(lines)


def _send_message(
    text: str,
    parse_mode: str = "HTML",
    disable_notification: bool = False,
    disable_web_page_preview: bool = True,
) -> bool:
    """Send a message via Telegram Bot API.
    
    Args:
        text: Message text.
        parse_mode: HTML or Markdown.
        disable_notification: If True, send silently.
        disable_web_page_preview: If True, don't show link previews.
    
    Returns:
        True if successful, False otherwise.
    """
    url = f"{API_BASE.format(token=config.TELEGRAM_BOT_TOKEN)}/sendMessage"

    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
        "disable_web_page_preview": disable_web_page_preview,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()

        if result.get("ok"):
            logger.debug("Telegram message sent successfully.")
            return True
        else:
            logger.error(f"Telegram API error: {result.get('description', 'Unknown error')}")
            return False
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML mode.
    
    Args:
        text: Raw text string.
    
    Returns:
        HTML-escaped string.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
