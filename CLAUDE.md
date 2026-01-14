# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
streamlit run app.py

# Push database migrations
supabase db push

# Link to Supabase project (first time)
supabase link --project-ref <project-ref>
```

## Environment Variables

Required in `.env`:
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...  # anon/public key
GEMINI_API_KEY=AIza...
```

Optional for auto-import:
```
AUTO_IMPORT_ENABLED=true
DOWNLOADS_DIR=~/Downloads
GLUCOSE_FILE_PATTERN=<pattern>
FOOD_FILE_PATTERN=<pattern>
```

## Architecture

**Streamlit multi-page app** for CGM data analysis to detect reactive hypoglycemia patterns.

### Data Flow

1. User uploads CSVs → `utils/csv_parser.py` normalizes to standardized DataFrames
2. `crash_analysis.calculate_glucose_velocity()` adds `velocity_smoothed` and `is_danger_zone` columns
3. `crash_analysis.detect_crash_events()` extracts crash event dicts
4. Data stored in `st.session_state` AND optionally persisted to Supabase
5. Dashboard/AI pages read from session state first, fall back to database

### Module Responsibilities

- **`utils/`** - Pure data processing (no Streamlit imports) for testability
- **`services/`** - External API integrations (Gemini, PDF generation) with graceful API key handling
- **`database/`** - Supabase persistence layer with CRUD operations

### Key Domain Concepts

| Term | Definition |
|------|------------|
| **Glucose velocity** | Rate of change in mg/dL per minute |
| **Danger zone** | Velocity ≤ -2.0 mg/dL/min (configurable in `config.py`) |
| **Crash event** | Contiguous period where velocity stays in danger zone |
| **Meal response** | Glucose readings 15 min before to 3 hours after a meal |

## Critical Conventions

### DataFrame Standards

All glucose DataFrames must have these columns after processing:
- `timestamp` (datetime64)
- `glucose_mg_dl` (float)
- `velocity_smoothed` (float, after velocity calculation)
- `is_danger_zone` (bool)

### Streamlit State Management

- Store processed DataFrames in `st.session_state['glucose_df']`, `st.session_state['food_df']`
- Check session state before database: `glucose_df = st.session_state.get('glucose_df')` then fall back

### Supabase Patterns

- Always check for client: `client = get_supabase_client(); if not client: return`
- Use `upsert()` for idempotent writes (handles re-uploads)
- Convert timestamps to ISO strings before saving: `record['timestamp'].isoformat()`
- Use `gen_random_uuid()` for UUIDs in schema

### Adding Features

1. **New data processing** → Add to `utils/` (keep Streamlit-free)
2. **New external API** → Add to `services/` with graceful API key handling
3. **New page** → Create in `pages/` with emoji + number prefix for ordering
4. **New table** → Add to `database/schema.sql`, then add CRUD functions to `supabase_client.py`
