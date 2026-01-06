"""Daily data upload page."""
import streamlit as st
import pandas as pd
from utils import parse_libre_csv, parse_cronometer_csv, group_foods_into_meals, merge_meals_with_glucose, calculate_glucose_velocity, detect_crash_events
from database import save_glucose_readings, save_food_logs, save_crash_events

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")

st.title("📤 Daily Data Upload")
st.markdown("Upload your FreeStyle Libre CGM export and Cronometer food log at the end of each day.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🩸 Libre CGM Data")
    st.markdown("Export from FreeStyle Libre app or LibreView")
    libre_file = st.file_uploader(
        "Drop Libre CSV here",
        type=['csv'],
        key='libre_upload'
    )

with col2:
    st.subheader("🍎 Cronometer Food Log")
    st.markdown("Export from Cronometer app/website")
    crono_file = st.file_uploader(
        "Drop Cronometer CSV here",
        type=['csv'],
        key='crono_upload'
    )

# Process uploaded files
if libre_file or crono_file:
    st.divider()
    st.subheader("📊 Data Preview")

    glucose_df = None
    food_df = None

    # Parse Libre data
    if libre_file:
        try:
            libre_content = libre_file.getvalue().decode('utf-8')
            glucose_df = parse_libre_csv(libre_content)

            with st.expander("🩸 Glucose Data Preview", expanded=True):
                st.success(f"✅ Loaded {len(glucose_df)} glucose readings")
                st.dataframe(glucose_df.head(20), use_container_width=True)

                # Quick stats
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Min", f"{glucose_df['glucose_mg_dl'].min():.0f} mg/dL")
                col2.metric("Max", f"{glucose_df['glucose_mg_dl'].max():.0f} mg/dL")
                col3.metric("Average", f"{glucose_df['glucose_mg_dl'].mean():.1f} mg/dL")
                col4.metric("Time Range", f"{(glucose_df['timestamp'].max() - glucose_df['timestamp'].min()).days + 1} days")

        except Exception as e:
            st.error(f"Error parsing Libre CSV: {e}")

    # Parse Cronometer data
    if crono_file:
        try:
            crono_content = crono_file.getvalue().decode('utf-8')
            food_df = parse_cronometer_csv(crono_content)

            with st.expander("🍎 Food Log Preview", expanded=True):
                st.success(f"✅ Loaded {len(food_df)} food entries")
                st.dataframe(food_df.head(20), use_container_width=True)

                # Quick stats
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Calories", f"{food_df['calories'].sum():.0f} kcal")
                col2.metric("Total Carbs", f"{food_df['carbs_g'].sum():.0f}g")
                col3.metric("Total Protein", f"{food_df['protein_g'].sum():.0f}g")
                col4.metric("Entries", len(food_df))

        except Exception as e:
            st.error(f"Error parsing Cronometer CSV: {e}")

# Merge and analyze
if libre_file and crono_file and glucose_df is not None and food_df is not None:
    st.divider()
    st.subheader("🔄 Merged Analysis")

    # Calculate velocity and detect crashes
    glucose_with_velocity = calculate_glucose_velocity(glucose_df)
    crash_events = detect_crash_events(glucose_with_velocity)

    # Group foods into meals, then merge with glucose
    meals_df = group_foods_into_meals(food_df)
    merged_data = merge_meals_with_glucose(glucose_df, meals_df)

    if not merged_data.empty:
        st.success(f"✅ Matched {len(merged_data)} meals with glucose data")

        with st.expander("📈 Meal-Glucose Events", expanded=True):
            display_df = merged_data[['meal_time', 'group', 'food_count', 'carbs_g', 'protein_g', 'peak_glucose']].copy()
            display_df['meal_time'] = display_df['meal_time'].dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(display_df, use_container_width=True)

    # Show crash events
    if crash_events:
        st.warning(f"⚠️ Detected {len(crash_events)} crash events (velocity > 2.0 mg/dL/min)")

        with st.expander("🚨 Crash Events", expanded=True):
            for i, crash in enumerate(crash_events, 1):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    start = crash['start_time']
                    if hasattr(start, 'strftime'):
                        start = start.strftime('%H:%M')
                    st.metric(f"Crash #{i}", start)
                with col2:
                    st.metric("Drop", f"{crash['drop_magnitude']:.1f} mg/dL")
                with col3:
                    st.metric("Velocity", f"{abs(crash['max_velocity']):.2f} mg/dL/min")
                with col4:
                    st.metric("Duration", f"{crash['duration_minutes']:.0f} min")
    else:
        st.success("✅ No dangerous crash events detected!")

    # Save to database
    st.divider()
    if st.button("💾 Save to Database", type="primary", use_container_width=True):
        with st.spinner("Saving data..."):
            # Prepare data for Supabase - replace NaN with None for JSON compatibility
            import numpy as np

            # Define schema columns for each table
            glucose_schema_cols = ['timestamp', 'glucose_mg_dl', 'velocity', 'velocity_smoothed', 'is_danger_zone']
            food_schema_cols = ['timestamp', 'food_name', 'group', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g', 'sugar_g']
            crash_schema_cols = ['start_time', 'end_time', 'start_glucose', 'end_glucose', 'drop_magnitude', 'average_velocity', 'max_velocity', 'duration_minutes']

            # Filter glucose data to schema columns
            glucose_cols = [c for c in glucose_schema_cols if c in glucose_with_velocity.columns]
            glucose_clean = glucose_with_velocity[glucose_cols].replace({np.nan: None})
            glucose_records = glucose_clean.to_dict('records')

            # Filter food data to schema columns
            food_cols = [c for c in food_schema_cols if c in food_df.columns]
            food_clean = food_df[food_cols].replace({np.nan: None})
            food_records = food_clean.to_dict('records')

            # Rename 'group' to 'meal_group' for database (group is a reserved word)
            for record in food_records:
                if 'group' in record:
                    record['meal_group'] = record.pop('group')

            # Convert timestamps to ISO strings for JSON
            for record in glucose_records:
                if 'timestamp' in record and record['timestamp'] is not None:
                    record['timestamp'] = record['timestamp'].isoformat()
            for record in food_records:
                if 'timestamp' in record and record['timestamp'] is not None:
                    record['timestamp'] = record['timestamp'].isoformat()

            # Convert crash events - filter to schema columns
            crash_records = []
            for crash in crash_events:
                crash_record = {k: v for k, v in crash.items() if k in crash_schema_cols}
                for key in ['start_time', 'end_time']:
                    if key in crash_record and hasattr(crash_record[key], 'isoformat'):
                        crash_record[key] = crash_record[key].isoformat()
                crash_records.append(crash_record)

            # Save to Supabase
            glucose_saved = save_glucose_readings(glucose_records)
            food_saved = save_food_logs(food_records)
            crash_saved = save_crash_events(crash_records) if crash_records else True

            if glucose_saved and food_saved and crash_saved:
                st.success("✅ All data saved to database!")
                st.balloons()
            else:
                failed = []
                if not glucose_saved:
                    failed.append("glucose readings")
                if not food_saved:
                    failed.append("food logs")
                if not crash_saved:
                    failed.append("crash events")
                st.warning(f"⚠️ Failed to save: {', '.join(failed)}. Check terminal for error details.")

    # Store in session for other pages
    st.session_state['glucose_df'] = glucose_with_velocity
    st.session_state['food_df'] = food_df
    st.session_state['merged_data'] = merged_data
    st.session_state['crash_events'] = crash_events

# Sidebar help
with st.sidebar:
    st.header("📖 How to Export Data")

    with st.expander("Libre Export Instructions"):
        st.markdown("""
        1. Open **LibreView** (web) or **FreeStyle Libre** app
        2. Go to **Reports** or **Export**
        3. Select date range
        4. Download as CSV
        """)

    with st.expander("Cronometer Export Instructions"):
        st.markdown("""
        1. Open **Cronometer** (web version works best)
        2. Go to **More** → **Export Data**
        3. Select **Servings** export
        4. Choose date range
        5. Download CSV
        """)
