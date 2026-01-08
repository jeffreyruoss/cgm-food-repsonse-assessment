"""Utility for automatically importing CSV files from the local Downloads directory."""
import os
import glob
import pandas as pd
import streamlit as st
import numpy as np
from datetime import datetime
from config import DOWNLOADS_DIR, GLUCOSE_FILE_PATTERN, FOOD_FILE_PATTERN, AUTO_IMPORT_ENABLED
from utils.csv_parser import (
    parse_libre_csv,
    parse_cronometer_csv,
    group_foods_into_meals,
    merge_meals_with_glucose
)
from utils.crash_analysis import (
    calculate_glucose_velocity,
    detect_crash_events
)
from database import (
    save_glucose_readings,
    save_food_logs,
    save_crash_events,
    is_file_already_imported,
    record_imported_file,
    get_recently_imported_files
)

def get_latest_file(directory: str, pattern: str) -> str | None:
    """Find the most recently modified file matching the pattern in the directory."""
    expanded_dir = os.path.expanduser(directory)
    search_pattern = os.path.join(expanded_dir, f"*{pattern}*.csv")
    files = glob.glob(search_pattern)

    if not files:
        return None

    # Sort files by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def process_and_save_files(glucose_path: str | None, food_path: str | None):
    """Parse the files and save them to Supabase. Returns list of metadata for successfully saved files."""
    glucose_df = None
    food_df = None
    results = [] # List of {'type': 'glucose'|'food', 'name': str, 'date': str}

    # Process Glucose
    if glucose_path:
        try:
            with open(glucose_path, 'r', encoding='utf-8') as f:
                content = f.read()
            glucose_df = parse_libre_csv(content)

            # Save to DB immediately
            glucose_with_velocity = calculate_glucose_velocity(glucose_df)
            crash_events = detect_crash_events(glucose_with_velocity)

            glucose_schema_cols = ['timestamp', 'glucose_mg_dl', 'velocity', 'velocity_smoothed', 'is_danger_zone']
            glucose_cols = [c for c in glucose_schema_cols if c in glucose_with_velocity.columns]
            glucose_clean = glucose_with_velocity[glucose_cols].replace({np.nan: None})
            glucose_records = glucose_clean.to_dict('records')

            for record in glucose_records:
                if 'timestamp' in record and record['timestamp'] is not None:
                    record['timestamp'] = record['timestamp'].isoformat()

            if save_glucose_readings(glucose_records):
                results.append({
                    'type': 'glucose',
                    'name': os.path.basename(glucose_path),
                    'date': datetime.fromtimestamp(os.path.getmtime(glucose_path)).strftime('%Y-%m-%d %H:%M')
                })
                # Update session state
                st.session_state['glucose_df'] = glucose_with_velocity
                st.session_state['crash_events'] = crash_events

                # Save crashes if any
                if crash_events:
                    crash_schema_cols = ['start_time', 'end_time', 'start_glucose', 'end_glucose', 'drop_magnitude', 'average_velocity', 'max_velocity', 'duration_minutes']
                    crash_records = []
                    for crash in crash_events:
                        crash_record = {k: v for k, v in crash.items() if k in crash_schema_cols}
                        for key in ['start_time', 'end_time']:
                            if key in crash_record and hasattr(crash_record[key], 'isoformat'):
                                crash_record[key] = crash_record[key].isoformat()
                        crash_records.append(crash_record)
                    save_crash_events(crash_records)
        except Exception as e:
            st.error(f"Error parsing auto-imported glucose file: {e}")

    # Process Food
    if food_path:
        try:
            with open(food_path, 'r', encoding='utf-8') as f:
                content = f.read()
            food_df = parse_cronometer_csv(content)

            food_schema_cols = ['timestamp', 'food_name', 'group', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g', 'sugar_g']
            food_cols = [c for c in food_schema_cols if c in food_df.columns]
            food_clean = food_df[food_cols].replace({np.nan: None})
            food_records = food_clean.to_dict('records')

            for record in food_records:
                if 'group' in record:
                    record['meal_group'] = record.pop('group')
                if 'timestamp' in record and record['timestamp'] is not None:
                    record['timestamp'] = record['timestamp'].isoformat()

            if save_food_logs(food_records):
                results.append({
                    'type': 'food',
                    'name': os.path.basename(food_path),
                    'date': datetime.fromtimestamp(os.path.getmtime(food_path)).strftime('%Y-%m-%d %H:%M')
                })
                # Update session state
                st.session_state['food_df'] = food_df

                # Also try to update merged data if glucose is present
                g_df = st.session_state.get('glucose_df')
                if g_df is not None:
                    meals_df = group_foods_into_meals(food_df)
                    st.session_state['merged_data'] = merge_meals_with_glucose(g_df, meals_df)
        except Exception as e:
            st.error(f"Error parsing auto-imported food file: {e}")

    return results

def check_and_perform_auto_import():
    """Main entry point to check for and import files."""
    if not AUTO_IMPORT_ENABLED:
        return

    # Check if we've already tried importing in this session
    if st.session_state.get('auto_import_checked', False):
        return

    # Validate that auto-import settings are configured in .env
    missing_vars = []
    if not DOWNLOADS_DIR: missing_vars.append("DOWNLOADS_DIR")
    if not GLUCOSE_FILE_PATTERN: missing_vars.append("GLUCOSE_FILE_PATTERN")
    if not FOOD_FILE_PATTERN: missing_vars.append("FOOD_FILE_PATTERN")

    if missing_vars:
        st.warning(f"⚠️ Auto-import is enabled but these settings are missing from your `.env` file: {', '.join(missing_vars)}")
        st.session_state['auto_import_checked'] = True
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Auto-import: Checking for new files in {DOWNLOADS_DIR}...")

    with st.status("🔍 Checking for new data files...", expanded=False) as status:
        glucose_file = get_latest_file(DOWNLOADS_DIR, GLUCOSE_FILE_PATTERN)
        food_file = get_latest_file(DOWNLOADS_DIR, FOOD_FILE_PATTERN)

        files_to_import = []
        if glucose_file:
            mtime = os.path.getmtime(glucose_file)
            if not is_file_already_imported(os.path.basename(glucose_file), mtime):
                files_to_import.append(('glucose', glucose_file, mtime))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✨ Found new glucose file: {os.path.basename(glucose_file)}")

        if food_file:
            mtime = os.path.getmtime(food_file)
            if not is_file_already_imported(os.path.basename(food_file), mtime):
                files_to_import.append(('food', food_file, mtime))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✨ Found new food file: {os.path.basename(food_file)}")

        if files_to_import:
            status.update(label="🚀 Importing new data files...", state="running", expanded=True)

            g_path = next((path for f_type, path, mt in files_to_import if f_type == 'glucose'), None)
            f_path = next((path for f_type, path, mt in files_to_import if f_type == 'food'), None)

            imported_results = process_and_save_files(g_path, f_path)

            if imported_results:
                # Record in database only the ones that were successfully saved
                for result in imported_results:
                    # Find the mtime from our files_to_import list
                    mtime = next((mt for f_type, path, mt in files_to_import if f_type == result['type']), 0)
                    record_imported_file(result['name'], mtime, result['type'])
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Successfully imported: {result['name']}")

                st.session_state['last_imported_files'] = imported_results

                success_msg = "✅ Auto-imported data:\n"
                for f in imported_results:
                    success_msg += f"- **{f['name']}** (Added: {f['date']})\n"

                status.update(label="✅ Data import complete!", state="complete")
                st.toast(success_msg, icon="📥")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ New files were found but import failed.")
                status.update(label="⚠️ Data import failed", state="error")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 No new files to import.")
            status.update(label="✅ No new data files found.", state="complete")
            # If nothing new to import, fetch the latest from database to show in the UI
            db_recent = get_recently_imported_files(limit=2)
            if db_recent:
                st.session_state['last_imported_files'] = [
                    {
                        'name': f['file_name'],
                        'date': datetime.fromtimestamp(f['file_mtime']).strftime('%Y-%m-%d %H:%M')
                    }
                    for f in db_recent
                ]

    st.session_state['auto_import_checked'] = True
