# 🩸 CGM Food Response Assessment

A Streamlit app for analyzing Continuous Glucose Monitor (CGM) data and correlating it with food intake to detect and understand **reactive hypoglycemia** patterns.

## Features

- **📤 Upload Data** - Import daily CGM exports from FreeStyle Libre and food logs from Cronometer
- **🔄 Automatic Merging** - Aligns timestamps to show exactly what you ate when glucose changes occurred
- **🚨 Crash Detection** - Identifies dangerous glucose drops using velocity analysis (rate of change > 2.0 mg/dL/min)
- **📊 Dashboard** - Interactive Plotly visualizations of glucose trends, crashes, and meal responses
- **🤖 AI Assistant** - Gemini-powered analysis explaining *why* crashes happen based on macro-nutrients
- **📋 Doctor Reports** - Generate professional PDF summaries for your physician

## Quick Start

### 1. Clone and set up environment

```bash
git clone <your-repo-url>
cd cgm-food-response-assessment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
GEMINI_API_KEY=your-gemini-api-key
```

### 3. Run the app

```bash
streamlit run app.py
```

## Project Structure

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
└── schema.sql            # PostgreSQL schema
```

## Key Concepts

| Term | Definition |
|------|------------|
| **Glucose Velocity** | Rate of change in mg/dL per minute |
| **Danger Zone** | Velocity ≤ -2.0 mg/dL/min (configurable) |
| **Crash Event** | Contiguous period where velocity stays in danger zone |
| **Meal Response** | Glucose readings 15 min before to 3 hours after a meal |

## Supported Data Sources

- **CGM Data**: FreeStyle Libre 3 CSV exports
- **Food Logs**: Cronometer daily export (CSV format)

## Tech Stack

- **Frontend**: Streamlit
- **Database**: Supabase (PostgreSQL)
- **AI**: Google Gemini Flash
- **Visualization**: Plotly
- **PDF Generation**: FPDF2

## Database Setup

If using Supabase, push the schema:

```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

## ⚠️ Disclaimer

This app is for **personal tracking and educational purposes only**. It is not a medical device and should not be used for diagnosis or treatment decisions. Always consult your healthcare provider for medical advice.

The crash detection threshold (-2.0 mg/dL/min) is a starting point and has not been clinically validated.

## License

MIT
