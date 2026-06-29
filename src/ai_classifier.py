"""
WallaHunter — AI Classifier
Uses the Gemini API to analyze listing details and determine if it's a real console
and what category it fits into.
"""

import os
import logging
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

# Define the Pydantic schema for structured output
class ConsoleAnalysis(BaseModel):
    is_console: bool = Field(
        description="True if this listing is specifically for an actual PS5 or Xbox Series X console (even if broken, damaged, or for parts). False if it is just a game, controller, accessory, box, VR, headset, account, skin, or PlayStation Portal."
    )
    is_broken_or_for_parts: bool = Field(
        description="True if the console has hardware faults, does not turn on, has error codes, or is explicitly sold for parts/repair."
    )
    is_bundle: bool = Field(
        description="True if this is a console bundle containing games or extra controllers alongside the console itself."
    )
    explanation: str = Field(
        description="A short sentence explaining why it is or isn't a console (e.g., 'This is a controller', 'This is a console for parts', 'This is a console bundle')."
    )

# Cache client initialization
_client = None

def get_genai_client():
    """Retrieve or initialize the GenAI client using GEMINI_API_KEY env var."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        # Fallback to TELEGRAM_BOT_TOKEN for local testing if GEMINI_API_KEY is missing but we are testing
        # (Though we require GEMINI_API_KEY for real AI usage)
        return None

    try:
        _client = genai.Client(api_key=api_key)
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}")
        return None


def analyze_with_ai(title: str, description: str, price: float) -> ConsoleAnalysis | None:
    """Analyze a listing using Gemini 2.5 Flash.
    
    Args:
        title: The listing title.
        description: The listing description.
        price: The listing price in EUR.
        
    Returns:
        ConsoleAnalysis object or None if the API call fails or is not configured.
    """
    client = get_genai_client()
    if client is None:
        return None

    prompt = f"""
    Analyze this Wallapop listing to determine if it is an actual PS5 (PlayStation 5) or Xbox Series X console.
    
    Listing Details:
    - Title: {title}
    - Description: {description}
    - Price: {price} EUR
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ConsoleAnalysis,
                temperature=0.0,  # Deterministic output
            )
        )
        # Parse the structured response
        analysis: ConsoleAnalysis = response.parsed
        return analysis
    except APIError as e:
        logger.error(f"Gemini API Error classifying '{title}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in Gemini classification for '{title}': {e}")
        return None
