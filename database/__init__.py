"""Database module."""
from .supabase_client import (
    get_supabase_client,
    save_glucose_readings,
    get_glucose_readings,
    save_food_logs,
    get_food_logs,
    save_crash_events,
    get_crash_events,
    save_chat_message,
    get_chat_history,
    get_meal_ai_assessment,
    save_meal_ai_assessment,
    get_all_meal_ai_assessments,
)

__all__ = [
    "get_supabase_client",
    "save_glucose_readings",
    "get_glucose_readings",
    "save_food_logs",
    "get_food_logs",
    "save_crash_events",
    "get_crash_events",
    "save_chat_message",
    "get_chat_history",
    "get_meal_ai_assessment",
    "save_meal_ai_assessment",
    "get_all_meal_ai_assessments",
]
