# 🎮 WallaHunter

Bot automatizado que escanea Wallapop cada 5 minutos buscando **PS5** y **Xbox Series X** baratas, las clasifica por categorías y te avisa al instante por **Telegram**.

Corre en **GitHub Actions** — no necesitas tener tu PC encendido. Cada ejecución usa una IP diferente, lo que hace casi imposible que Wallapop te banee.

---

## 🚀 Setup rápido (5 minutos)

### 1. Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. Ponle un nombre: `WallaHunter` (o el que quieras)
4. Ponle un username: `wallahunter_TUNOMBRE_bot` (debe acabar en `_bot`)
5. **Copia el token** que te da (algo como `1234567890:ABCdefGHIjklmno...`)

### 2. Obtener tu Chat ID

1. Busca **@userinfobot** en Telegram
2. Envía `/start`
3. Te responderá con tu **ID numérico** (algo como `123456789`)

### 3. Configurar el repositorio

1. Haz fork de este repo (o súbelo a tu cuenta de GitHub)
2. Ve a **Settings → Secrets and variables → Actions**
3. Añade estos **Repository Secrets**:

| Secret | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | El token del paso 1 |
| `TELEGRAM_CHAT_ID` | Tu ID del paso 2 |

### 4. ¡Listo!

El bot empezará a escanear automáticamente cada 5 minutos. También puedes ejecutarlo manualmente:

1. Ve a la pestaña **Actions**
2. Selecciona **🎮 WallaHunter**
3. Click en **Run workflow**

---

## 📊 Categorías de clasificación

| Categoría | Condición | Notificación |
|---|---|---|
| ⚡ **CHOLLO EXTREMO** | Precio ≤ 150€ | 🔔 Con sonido |
| 🔧 **REPARAR** | ≤ 200€ o keywords de avería | 🔔 Con sonido |
| 💰 **BARATITO** | ≤ 300€ | 🔕 Silenciosa |
| 🤝 **PARA NEGOCIAR** | ≤ 350€ y cerca de Málaga | 🔕 Silenciosa |
| 📦 **LOTE / PACK** | Bundle/pack ≤ 350€ | 🔕 Silenciosa |

Además, si un anuncio **baja de precio**, se re-notifica con etiqueta 📉.

---

## 🛠️ Personalización

Edita [`src/config.py`](src/config.py) para ajustar:

- **Búsquedas**: Añade o quita consolas/productos
- **Precios**: Ajusta los umbrales de cada categoría
- **Ubicación**: Cambia las coordenadas para "Para Negociar"
- **Keywords**: Añade palabras clave de reparación o bundles

---

## 📁 Estructura

```
wallapop-bot/
├── .github/workflows/hunt.yml    ← GitHub Actions (cron cada 5 min)
├── src/
│   ├── config.py                 ← Configuración
│   ├── scraper.py                ← Scraping con Playwright
│   ├── classifier.py             ← Clasificación por categorías
│   ├── notifier.py               ← Telegram notifications
│   ├── storage.py                ← Persistencia (JSON)
│   └── main.py                   ← Orquestador
├── data/
│   └── seen_listings.json        ← Anuncios ya notificados
└── requirements.txt
```

---

## 🧪 Testing local

```bash
# Instalar dependencias
pip install -r requirements.txt
playwright install chromium --with-deps

# Configurar variables de entorno
export TELEGRAM_BOT_TOKEN="tu_token_aquí"
export TELEGRAM_CHAT_ID="tu_chat_id_aquí"

# Ejecutar un scan
python -m src.main
```

---

## 💡 FAQ

### ¿Me pueden banear la IP?
Muy improbable. GitHub Actions usa IPs diferentes en cada ejecución (infraestructura Azure). Además, solo hacemos ~5 búsquedas cada 5 minutos con delays aleatorios entre ellas.

### ¿Cuántos minutos de GitHub Actions consume?
Repo público = **ilimitado y gratis**. Cada scan dura ~2 minutos.

### ¿Y si quiero buscar otros productos?
Edita `SEARCH_QUERIES` en `src/config.py`. Puedes añadir Steam Deck, Nintendo Switch, o lo que quieras.

### ¿Se repiten las notificaciones?
No. Cada anuncio se guarda en `seen_listings.json`. Solo se re-notifica si **baja de precio**.

---

## 📜 Licencia

Uso personal. Wallapop no tiene API pública; este proyecto es para uso educativo y personal.
