# CGM Food Response Assessment - AI Coding Instructions

## Architecture Overview

This is a **Streamlit multi-page app** for analyzing CGM (Continuous Glucose Monitor) data to detect reactive hypoglycemia patterns.

```
app.py                    # Entry point - home page with config status
pages/                    # Streamlit pages (numbered for sidebar order)
├── 1_📤_Upload_Data.py   # CSV upload, parsing, crash detection
├── 2_📊_Dashboard.py     # Plotly visualizations, glucose trends
├── 3_🤖_AI_Assistant.py  # Gemini chat with glucose context
└── 4_📋_Doctor_Report.py # PDF generation for physicians
utils/                    # Pure data processing (no Streamlit imports)
├── csv_parser.py         # Parse Libre CGM & Cronometer food CSVs
└── crash_analysis.py     # Velocity calculation, crash detection
services/                 # External API integrations
├── gemini_service.py     # Google Gemini AI calls
└── pdf_generator.py      # FPDF2 report generation
database/                 # Supabase persistence layer
├── supabase_client.py    # CRUD operations for all tables
└── schema.sql            # PostgreSQL schema (use gen_random_uuid())
```

## Key Domain Concepts

- **Glucose velocity**: Rate of change in mg/dL per minute (calculated in `crash_analysis.py`)
- **Danger zone**: Velocity ≤ -2.0 mg/dL/min indicates a crash (configurable in `config.py`) - this threshold is a starting point, not medically validated
- **Crash event**: Contiguous period where velocity stays in danger zone
- **Meal response**: Glucose readings 15 min before to 3 hours after a meal

## Data Flow Pattern

1. User uploads CSVs → `csv_parser.py` normalizes to standardized DataFrames
2. `crash_analysis.calculate_glucose_velocity()` adds `velocity_smoothed` and `is_danger_zone` columns
3. `crash_analysis.detect_crash_events()` extracts crash event dicts
4. Data stored in `st.session_state` AND optionally persisted to Supabase
5. Dashboard/AI pages read from session state first, fall back to database

## Critical Conventions

### Streamlit State Management

- Store processed DataFrames in `st.session_state['glucose_df']`, `st.session_state['food_df']`
- Check session state before database: `glucose_df = st.session_state.get('glucose_df')` then fall back

### DataFrame Standards

All glucose DataFrames must have these columns after processing:

- `timestamp` (datetime64)
- `glucose_mg_dl` (float)
- `velocity_smoothed` (float, after velocity calculation)
- `is_danger_zone` (bool)

### Supabase Patterns

- Always check for client: `client = get_supabase_client(); if not client: return`
- Use `upsert()` for idempotent writes (handles re-uploads)
- Convert timestamps to ISO strings before saving: `record['timestamp'].isoformat()`

### Gemini Prompts

- Include structured context (## headers) for crash events and food data
- Always handle missing API key gracefully: `if not model: return "API not configured..."`

## Commands

```bash
# Run the app
source .venv/bin/activate && streamlit run app.py

# Push database migrations
supabase db push

# Link to Supabase project (first time)
supabase link --project-ref <project-ref>
```

## Environment Variables (.env)

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...  # anon/public key
GEMINI_API_KEY=AIza...
```

## When Adding Features

1. **New data processing** → Add to `utils/` (keep Streamlit-free for testability)
2. **New external API** → Add to `services/` with graceful API key handling
3. **New page** → Create in `pages/` with emoji + number prefix for ordering
4. **New table** → Add to `database/schema.sql` using `gen_random_uuid()`, then add CRUD functions to `supabase_client.py`
