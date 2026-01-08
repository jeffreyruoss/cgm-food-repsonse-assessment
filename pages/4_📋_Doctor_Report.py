"""Doctor's Report Export page."""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from services import generate_doctor_report, save_report_to_file
from utils import get_crash_summary_stats
from utils.auth import check_password
from database import get_crash_events, get_glucose_readings, get_food_logs

st.set_page_config(page_title="Doctor's Report", page_icon="📋", layout="wide")

# Authentication check
if not check_password():
    st.stop()

st.title("📋 Doctor's Note Export")
st.markdown("Generate a professional PDF summary for your physician.")

# Get data
glucose_df = st.session_state.get('glucose_df')
crash_events = st.session_state.get('crash_events', [])
food_df = st.session_state.get('food_df')

# Load from database if not in session
if glucose_df is None:
    glucose_data = get_glucose_readings()
    if glucose_data:
        glucose_df = pd.DataFrame(glucose_data)
        glucose_df['timestamp'] = pd.to_datetime(glucose_df['timestamp'])

if not crash_events:
    crash_data = get_crash_events()
    if crash_data:
        crash_events = crash_data
        for event in crash_events:
            for key in ['start_time', 'end_time']:
                if key in event and isinstance(event[key], str):
                    event[key] = pd.to_datetime(event[key])

if food_df is None:
    food_data = get_food_logs()
    if food_data:
        food_df = pd.DataFrame(food_data)
        food_df['timestamp'] = pd.to_datetime(food_df['timestamp'])

# Check if we have data
if glucose_df is None or glucose_df.empty:
    st.info("👋 Upload your CGM data first to generate a report.")
    st.stop()

# Report configuration
st.subheader("📝 Report Configuration")

col1, col2 = st.columns(2)

with col1:
    # Date range
    min_date = glucose_df['timestamp'].min().date()
    max_date = glucose_df['timestamp'].max().date()

    report_start = st.date_input("Report Start Date", min_date)
    report_end = st.date_input("Report End Date", max_date)

    # Calculate days
    days = (report_end - report_start).days + 1
    st.info(f"📅 Report covers **{days} days**")

with col2:
    # Patient notes
    patient_notes = st.text_area(
        "Patient Notes (optional)",
        placeholder="Add any additional notes for your doctor...\n\nExamples:\n- Symptoms you've experienced\n- Medication changes\n- Lifestyle factors",
        height=150
    )

# Preview section
st.divider()
st.subheader("📊 Report Preview")

# Filter data by date range
mask = (glucose_df['timestamp'].dt.date >= report_start) & (glucose_df['timestamp'].dt.date <= report_end)
filtered_glucose = glucose_df[mask]

# Filter crash events
filtered_crashes = []
if crash_events:
    for crash in crash_events:
        crash_date = crash['start_time'].date() if hasattr(crash['start_time'], 'date') else pd.to_datetime(crash['start_time']).date()
        if report_start <= crash_date <= report_end:
            filtered_crashes.append(crash)

# Summary stats
stats = get_crash_summary_stats(filtered_crashes)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Crash Events", stats['total_crashes'])
with col2:
    st.metric("Avg Drop", f"{stats['avg_drop_magnitude']:.1f} mg/dL")
with col3:
    st.metric("Avg Duration", f"{stats['avg_duration']:.0f} min")
with col4:
    if filtered_crashes:
        st.metric("Worst Velocity", f"{abs(stats['worst_velocity']):.2f} mg/dL/min")
    else:
        st.metric("Worst Velocity", "N/A")

# Crash events preview
if filtered_crashes:
    st.markdown("### 🚨 Crash Events to Include")

    crash_df = pd.DataFrame(filtered_crashes)
    if 'start_time' in crash_df.columns:
        crash_df['start_time'] = pd.to_datetime(crash_df['start_time'])
        crash_df_display = crash_df[['start_time', 'drop_magnitude', 'max_velocity', 'duration_minutes']].copy()
        crash_df_display.columns = ['Time', 'Drop (mg/dL)', 'Max Velocity (mg/dL/min)', 'Duration (min)']
        crash_df_display['Time'] = crash_df_display['Time'].dt.strftime('%Y-%m-%d %I:%M %p')
        crash_df_display['Drop (mg/dL)'] = crash_df_display['Drop (mg/dL)'].apply(lambda x: f"{x:.1f}")
        crash_df_display['Max Velocity (mg/dL/min)'] = crash_df_display['Max Velocity (mg/dL/min)'].apply(lambda x: f"{abs(x):.2f}")
        crash_df_display['Duration (min)'] = crash_df_display['Duration (min)'].apply(lambda x: f"{x:.0f}")

        st.dataframe(crash_df_display, use_container_width=True, hide_index=True)
else:
    st.success("✅ No crash events in selected period!")

# Food triggers analysis
if food_df is not None and not food_df.empty and filtered_crashes:
    st.markdown("### 🍽️ Potential Food Triggers")

    # Simple trigger analysis - foods eaten before crashes
    food_triggers = []

    for crash in filtered_crashes:
        crash_time = crash['start_time']
        if isinstance(crash_time, str):
            crash_time = pd.to_datetime(crash_time)

        # Look for foods 30-180 min before crash
        for _, food in food_df.iterrows():
            food_time = food['timestamp']
            if isinstance(food_time, str):
                food_time = pd.to_datetime(food_time)

            time_diff = (crash_time - food_time).total_seconds() / 60
            if 30 <= time_diff <= 180:
                food_triggers.append({
                    'food_name': food.get('food_name', 'Unknown'),
                    'crash_velocity': crash.get('max_velocity', 0)
                })

    if food_triggers:
        # Aggregate by food
        trigger_df = pd.DataFrame(food_triggers)
        trigger_summary = trigger_df.groupby('food_name').agg({
            'crash_velocity': ['count', 'mean']
        }).reset_index()
        trigger_summary.columns = ['Food', 'Crash Count', 'Avg Velocity']
        trigger_summary = trigger_summary.sort_values('Crash Count', ascending=False)
        trigger_summary['Avg Velocity'] = trigger_summary['Avg Velocity'].apply(lambda x: f"{abs(x):.2f}")

        st.dataframe(trigger_summary.head(5), use_container_width=True, hide_index=True)

        # Convert to format for PDF
        food_trigger_list = [
            {'food_name': row['Food'], 'crash_count': row['Crash Count'], 'avg_velocity': float(row['Avg Velocity'])}
            for _, row in trigger_summary.head(5).iterrows()
        ]
    else:
        food_trigger_list = None
else:
    food_trigger_list = None

# Generate report button
st.divider()

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if st.button("📄 Generate PDF Report", type="primary", use_container_width=True):
        with st.spinner("Generating report..."):
            try:
                pdf_bytes = generate_doctor_report(
                    summary_stats=stats,
                    crash_events=filtered_crashes,
                    food_triggers=food_trigger_list,
                    date_range=(str(report_start), str(report_end)),
                    patient_notes=patient_notes if patient_notes else None
                )

                # Offer download
                filename = f"cgm_report_{report_start}_{report_end}.pdf"

                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

                st.success("✅ Report generated successfully!")

            except Exception as e:
                st.error(f"Error generating report: {e}")

# Tips
with st.sidebar:
    st.header("💡 Tips")
    st.markdown("""
    **What to discuss with your doctor:**

    1. **Frequency** - How often crashes occur
    2. **Triggers** - Foods that seem to cause issues
    3. **Timing** - When crashes typically happen
    4. **Symptoms** - What you feel during crashes
    5. **Mitigation** - What helps prevent/stop crashes

    **Potential Tests to Request:**
    - Oral Glucose Tolerance Test (OGTT)
    - Fasting insulin levels
    - HbA1c
    - Metabolic panel
    """)
