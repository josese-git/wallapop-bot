"""
WallaHunter — Configuration & Constants
All tunable parameters for the Wallapop deal scanner.
"""

import os

# ═══════════════════════════════════════════════════════════════
# SEARCH QUERIES
# Each entry triggers a separate Wallapop search.
# Keep this list small to avoid excessive requests.
# ═══════════════════════════════════════════════════════════════
SEARCH_QUERIES = [
    {"keywords": "ps5", "console": "PS5"},
    {"keywords": "playstation 5", "console": "PS5"},
    {"keywords": "play station 5", "console": "PS5"},
    {"keywords": "xbox series x", "console": "Xbox Series X"},
    {"keywords": "series x", "console": "Xbox Series X"},
]

# ═══════════════════════════════════════════════════════════════
# LOCATION — Rincón de la Victoria, Málaga
# Used for distance calculations and "Para Negociar" category.
# ═══════════════════════════════════════════════════════════════
USER_LATITUDE = 36.7133
USER_LONGITUDE = -4.2756
NEARBY_RADIUS_KM = 30  # Max distance for "Para Negociar"

# ═══════════════════════════════════════════════════════════════
# PRICE THRESHOLDS (EUR)
# Categories are applied in priority order (top = highest priority).
# ═══════════════════════════════════════════════════════════════
PRICE_CHOLLO_MAX = 150       # ⚡ CHOLLO EXTREMO — drop everything, BUY NOW
PRICE_REPARAR_MAX = 200      # 🔧 REPARAR — cheap enough to fix
PRICE_BARATITO_MAX = 300     # 💰 BARATITO — good deal
PRICE_NEGOCIAR_MAX = 350     # 🤝 PARA NEGOCIAR — nearby, worth haggling
PRICE_LOTE_MAX = 350         # 📦 LOTE/PACK — bundle deal
PRICE_MIN_FILTER = 70        # Below this = games/accessories/scams, ignore

# ═══════════════════════════════════════════════════════════════
# KEYWORD DETECTION
# Used to classify listings into categories.
# ═══════════════════════════════════════════════════════════════
REPAIR_KEYWORDS = [
    "reparar", "reparación", "reparacion", "averiada", "averiado",
    "rota", "roto", "no funciona", "no enciende", "no lee",
    "hdmi", "blod", "error ce-", "piezas", "recambio", "para piezas",
    "estropeada", "estropeado", "falla", "se apaga", "arreglar",
    "arreglo", "defectuosa", "defectuoso", "no arranca",
    "pantalla azul", "lector roto", "lector no", "sobrecalienta",
    "se calienta mucho", "ruido fuerte", "ventilador roto",
    "puerto hdmi", "placa", "no da imagen", "luz azul",
]

BUNDLE_KEYWORDS = [
    "lote", "pack", "bundle", "conjunto", "kit",
    "con juegos", "juegos incluidos", "con mando extra",
    "con mandos", "completa con", "incluye juegos",
    "todo incluido", "set completo",
]

# Keywords that, if present ANYWHERE in the title, strongly indicate it's an accessory/game, NOT a console.
STRICT_ACCESSORY_KEYWORDS = [
    # Controllers / Mandos
    "dualsense", "dual sense", "controller", "gamepad", "joystick", "mando suelto", "solo mando",
    "mando inalámbrico", "mando inalambrico", "razer raiju", "nacon", "scuf", "aim controller",
    "edge", "dualsense edge", "elite series", "mando elite",
    # Steering wheels / Volantes
    "volante", "pedales", "shifter", "g29", "g920", "g923", "thrustmaster", "t150", "t300", 
    "t248", "logitech", "playseat", "cockpit",
    # VR / Realidad Virtual
    "vr", "psvr", "psvr2", "gafas", "realidad virtual", "oculus", "meta quest",
    # Audio / Cascos
    "cascos", "auriculares", "headset", "headphones", "pulse 3d", "pulse elite",
    # Other accessories / Parts
    "funda", "carcasa", "skin", "vinilo", "soporte", "base de carga", "estacion de carga",
    "teclado", "raton", "ratón", "cable", "cargador", "adaptador", "cámara", "camara",
    "media remote", "placas", "chasis", "refrigeracion", "ventilador", "hdmi", "ssd", 
    "disco duro", "tarjeta de memoria", "caja vacia", "caja vacía", "solo caja", "caja original",
    # Games & Accounts
    "juego", "juegos", "game", "games", "cuenta", "cuentas", "suscripcion", "suscripción", 
    "plus", "psn", "game pass", "gamepass", "codigo", "código", "card", "tarjeta prepago",
    # PlayStation Portal
    "portal", "playstation portal", "remote play"
]

# Words that, if they are the first word of the title (after stripping common fillers),
# indicate the listing is about that item. E.g. "Mando PS5" -> starts with "Mando" (Accessory).
ACCESSORY_START_WORDS = [
    "mando", "mandos", "volante", "volantes", "cascos", "auriculares", "juego", "juegos", 
    "funda", "fundas", "carcasa", "carcasas", "soporte", "soportes", "cable", "cables", 
    "caja", "cajas", "cuenta", "cuentas", "gafas", "camara", "cámara", "ssd", "disco", 
    "chasis", "placas", "base", "cargador", "cargadores"
]

# Verbs/Fillers commonly found at the start of Wallapop listings.
# We strip these before checking the first word.
START_FILLER_WORDS = [
    "vendo", "se vende", "venda", "compro", "busco", "lote de", "pack de", "caja de", 
    "exclusivo", "nuevo", "nueva", "seminuevo", "semi-nuevo", "oportunidad", "ganga", 
    "original", "oficial", "magnifico", "magnífico", "espectacular", "increible", "increíble",
    "se", "a", "la", "el", "un", "una"
]

# ═══════════════════════════════════════════════════════════════
# CATEGORIES — used throughout the app
# ═══════════════════════════════════════════════════════════════
CATEGORY_CHOLLO = "CHOLLO_EXTREMO"
CATEGORY_REPARAR = "REPARAR"
CATEGORY_BARATITO = "BARATITO"
CATEGORY_NEGOCIAR = "PARA_NEGOCIAR"
CATEGORY_LOTE = "LOTE_PACK"

CATEGORY_DISPLAY = {
    CATEGORY_CHOLLO: {"emoji": "⚡", "label": "CHOLLO EXTREMO", "priority": 1},
    CATEGORY_REPARAR: {"emoji": "🔧", "label": "REPARAR", "priority": 2},
    CATEGORY_BARATITO: {"emoji": "💰", "label": "BARATITO", "priority": 3},
    CATEGORY_NEGOCIAR: {"emoji": "🤝", "label": "PARA NEGOCIAR", "priority": 4},
    CATEGORY_LOTE: {"emoji": "📦", "label": "LOTE / PACK", "priority": 5},
}

# ═══════════════════════════════════════════════════════════════
# TELEGRAM
# Set via GitHub Secrets → environment variables.
# ═══════════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ═══════════════════════════════════════════════════════════════
# WALLAPOP
# ═══════════════════════════════════════════════════════════════
WALLAPOP_BASE_URL = "https://es.wallapop.com"

# ═══════════════════════════════════════════════════════════════
# STORAGE
# ═══════════════════════════════════════════════════════════════
SEEN_LISTINGS_PATH = "data/seen_listings.json"
MAX_LISTING_AGE_DAYS = 60
