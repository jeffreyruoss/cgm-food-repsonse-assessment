"""Application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-key")

# Crash Analysis Thresholds
DANGER_ZONE_THRESHOLD = 2.0  # mg/dL per minute - velocity threshold for "danger zone"
CRASH_LOOKBACK_MINUTES = 180  # How far back to analyze for crashes after eating

# Auto-Import Settings
AUTO_IMPORT_ENABLED = os.getenv("AUTO_IMPORT_ENABLED", "false").lower() == "true"
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR")  # e.g., ~/Downloads
GLUCOSE_FILE_PATTERN = os.getenv("GLUCOSE_FILE_PATTERN")  # e.g., JeffRuoss_glucose
FOOD_FILE_PATTERN = os.getenv("FOOD_FILE_PATTERN")  # e.g., servings
