"""Application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Crash Analysis Thresholds
DANGER_ZONE_THRESHOLD = 2.0  # mg/dL per minute - velocity threshold for "danger zone"
CRASH_LOOKBACK_MINUTES = 180  # How far back to analyze for crashes after eating
