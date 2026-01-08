"""Supabase client initialization and database operations."""
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY


def get_supabase_client() -> Client | None:
    """Get Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Database operations for glucose readings
def save_glucose_readings(readings: list[dict]) -> bool:
    """Save glucose readings to Supabase."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("glucose_readings").upsert(readings, on_conflict="timestamp").execute()
        return True
    except Exception as e:
        print(f"Error saving glucose readings: {e}")
        return False


def get_glucose_readings(start_date: str = None, end_date: str = None) -> list[dict]:
    """Fetch glucose readings from Supabase."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        query = client.table("glucose_readings").select("*")
        if start_date:
            query = query.gte("timestamp", start_date)
        if end_date:
            query = query.lte("timestamp", end_date)
        result = query.order("timestamp").execute()
        return result.data
    except Exception as e:
        print(f"Error fetching glucose readings: {e}")
        return []


# Database operations for food logs
def save_food_logs(logs: list[dict]) -> bool:
    """Save food logs to Supabase."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Deduplicate by timestamp + food_name (keep first occurrence)
        seen = set()
        unique_logs = []
        for log in logs:
            key = (log.get('timestamp'), log.get('food_name'))
            if key not in seen:
                seen.add(key)
                unique_logs.append(log)
        client.table("food_logs").upsert(unique_logs, on_conflict="timestamp,food_name").execute()
        return True
    except Exception as e:
        print(f"Error saving food logs: {e}")
        return False


def get_food_logs(start_date: str = None, end_date: str = None) -> list[dict]:
    """Fetch food logs from Supabase."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        query = client.table("food_logs").select("*")
        if start_date:
            query = query.gte("timestamp", start_date)
        if end_date:
            query = query.lte("timestamp", end_date)
        result = query.order("timestamp").execute()
        return result.data
    except Exception as e:
        print(f"Error fetching food logs: {e}")
        return []


# Database operations for crash events
def save_crash_events(events: list[dict]) -> bool:
    """Save crash events to Supabase."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("crash_events").upsert(events, on_conflict="start_time,end_time").execute()
        return True
    except Exception as e:
        print(f"Error saving crash events: {e}")
        return False


def get_crash_events(start_date: str = None, end_date: str = None) -> list[dict]:
    """Fetch crash events from Supabase."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        query = client.table("crash_events").select("*")
        if start_date:
            query = query.gte("timestamp", start_date)
        if end_date:
            query = query.lte("timestamp", end_date)
        result = query.order("timestamp").execute()
        return result.data
    except Exception as e:
        print(f"Error fetching crash events: {e}")
        return []


# Chat history operations
def save_chat_message(role: str, content: str) -> bool:
    """Save a chat message to Supabase."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("chat_history").insert({
            "role": role,
            "content": content
        }).execute()
        return True
    except Exception as e:
        print(f"Error saving chat message: {e}")
        return False


def get_chat_history(limit: int = 50) -> list[dict]:
    """Fetch recent chat history from Supabase."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = client.table("chat_history").select("*").order("created_at", desc=True).limit(limit).execute()
        return list(reversed(result.data))
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return []


# Meal AI Assessment operations
def get_meal_ai_assessment(meal_key: str) -> dict | None:
    """Fetch a meal AI assessment by meal_key."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = client.table("meal_ai_assessments").select("*").eq("meal_key", meal_key).single().execute()
        return result.data
    except Exception:
        return None


def save_meal_ai_assessment(assessment: dict) -> bool:
    """Save or update a meal AI assessment."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Add updated_at timestamp
        assessment['updated_at'] = 'now()'
        client.table("meal_ai_assessments").upsert(assessment, on_conflict="meal_key").execute()
        return True
    except Exception as e:
        print(f"Error saving meal AI assessment: {e}")
        return False


def get_all_meal_ai_assessments() -> dict:
    """Fetch all meal AI assessments, indexed by meal_key."""
    client = get_supabase_client()
    if not client:
        return {}
    try:
        result = client.table("meal_ai_assessments").select("*").execute()
        return {row['meal_key']: row for row in result.data}
    except Exception as e:
        print(f"Error fetching meal AI assessments: {e}")
        return {}

# Imported Files Tracking
def is_file_already_imported(file_name: str, mtime: float) -> bool:
    """Check if a file with the given name and modification time has already been imported."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Use integer (milliseconds) to avoid floating point precision issues
        mtime_ms = int(mtime * 1000)
        result = client.table("imported_files").select("id").eq("file_name", file_name).eq("file_mtime", mtime_ms).execute()
        return len(result.data) > 0
    except Exception as e:
        error_str = str(e)
        if "PGRST205" in error_str or "does not exist" in error_str:
            print(f"⚠️ Table 'imported_files' missing. Please run the SQL migration.")
        else:
            print(f"Error checking imported file: {e}")
        return False

def record_imported_file(file_name: str, mtime: float, file_type: str) -> bool:
    """Record that a file has been successfully imported."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        # Use integer (milliseconds) to avoid floating point precision issues
        mtime_ms = int(mtime * 1000)
        client.table("imported_files").upsert({
            "file_name": file_name,
            "file_mtime": mtime_ms,
            "file_type": file_type
        }, on_conflict="file_name,file_mtime").execute()
        return True
    except Exception as e:
        print(f"Error recording imported file: {e}")
        return False

def get_recently_imported_files(limit: int = 2) -> list[dict]:
    """Fetch the most recently imported files from the database."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = client.table("imported_files").select("file_name, file_mtime, imported_at").order("imported_at", desc=True).limit(limit).execute()
        return result.data
    except Exception as e:
        print(f"Error fetching recently imported files: {e}")
        return []
