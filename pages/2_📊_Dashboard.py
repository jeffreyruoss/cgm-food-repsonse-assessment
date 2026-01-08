"""Dashboard with glucose visualizations and crash analysis."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from utils import calculate_glucose_velocity, detect_crash_events, get_crash_summary_stats, group_foods_into_meals, merge_meals_with_glucose, analyze_meal_response
from utils.auto_import import check_and_perform_auto_import
from database import get_glucose_readings, get_food_logs, get_crash_events, get_meal_ai_assessment, save_meal_ai_assessment, get_all_meal_ai_assessments
from services.gemini_service import analyze_meal_with_ai
from config import DANGER_ZONE_THRESHOLD

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

# Run auto-import check on page load
check_and_perform_auto_import()

# Show last imported files if they exist
if 'last_imported_files' in st.session_state:
    with st.expander("📥 Recently Auto-Imported Files", expanded=False):
        for f in st.session_state['last_imported_files']:
            st.write(f"- **{f['name']}** ({f['date']})")

st.title("📊 Glucose Dashboard")


@st.cache_data(show_spinner="Fetching glucose data...")
def get_cached_glucose():
    """Fetch and process glucose data from database with caching."""
    glucose_data = get_glucose_readings()
    if not glucose_data:
        return None
    df = pd.DataFrame(glucose_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Initial velocity calculation for the whole dataset
    return calculate_glucose_velocity(df)


@st.cache_data(show_spinner="Fetching food logs...")
def get_cached_food():
    """Fetch and process food logs from database with caching."""
    food_data = get_food_logs()
    if not food_data:
        return None
    df = pd.DataFrame(food_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Map meal_group back to group for grouping functions
    if 'meal_group' in df.columns:
        df['group'] = df['meal_group']
    elif 'group' not in df.columns:
        df['group'] = 'Uncategorized'
    # Add day column for grouping
    df['day'] = df['timestamp'].dt.date
    return df


@st.cache_data(show_spinner="Analyzing crashes...")
def get_cached_crashes(glucose_df):
    """Detect crash events with caching."""
    if glucose_df is None or glucose_df.empty:
        return []
    return detect_crash_events(glucose_df)


def load_data():
    """Load data from session state or database."""
    glucose_df = st.session_state.get('glucose_df')
    food_df = st.session_state.get('food_df')
    crash_events = st.session_state.get('crash_events')

    # If no session data, try loading from database
    if glucose_df is None:
        glucose_df = get_cached_glucose()

    if food_df is None:
        food_df = get_cached_food()

    if crash_events is None and glucose_df is not None:
        crash_events = get_cached_crashes(glucose_df)

    return glucose_df, food_df, crash_events


glucose_df, food_df, crash_events = load_data()

if glucose_df is None or glucose_df.empty:
    st.info("👋 Welcome! Upload your CGM and food data on the **Upload Data** page to see your dashboard.")
    st.stop()

# Date filter
st.sidebar.header("🗓️ Date Range")
min_date = glucose_df['timestamp'].min().date()
max_date = glucose_df['timestamp'].max().date()
today = datetime.now().date()

# Date range shortcut buttons
row1_cols = st.sidebar.columns(2)
with row1_cols[0]:
    if st.button("Today", width="stretch"):
        st.session_state['date_range'] = (today, today)
        st.rerun()
with row1_cols[1]:
    if st.button("Yesterday", width="stretch"):
        yesterday = today - timedelta(days=1)
        st.session_state['date_range'] = (yesterday, yesterday)
        st.rerun()

row2_cols = st.sidebar.columns(2)
with row2_cols[0]:
    if st.button("Last 7 Days", width="stretch"):
        st.session_state['date_range'] = (today - timedelta(days=6), today)
        st.rerun()
with row2_cols[1]:
    if st.button("Last 30 Days", width="stretch"):
        st.session_state['date_range'] = (today - timedelta(days=29), today)
        st.rerun()

# Get date range from session state or default to all data
default_range = st.session_state.get('date_range', (min_date, max_date))
# Clamp to available data range
default_start = max(min_date, min(default_range[0], max_date))
default_end = max(min_date, min(default_range[1], max_date))

date_range = st.sidebar.date_input(
    "Select date range",
    value=(default_start, default_end),
    min_value=min_date,
    max_value=max_date
)

if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (glucose_df['timestamp'].dt.date >= start_date) & (glucose_df['timestamp'].dt.date <= end_date)
    filtered_glucose = glucose_df[mask].copy()
else:
    filtered_glucose = glucose_df.copy()

# Summary metrics
st.subheader("📈 Summary Metrics")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    avg_glucose = filtered_glucose['glucose_mg_dl'].mean()
    st.metric("Avg Glucose", f"{avg_glucose:.0f} mg/dL")

with col2:
    time_in_range = ((filtered_glucose['glucose_mg_dl'] >= 70) & (filtered_glucose['glucose_mg_dl'] <= 140)).mean() * 100
    st.metric("Time in Range", f"{time_in_range:.0f}%", help="70-140 mg/dL")

with col3:
    time_low = (filtered_glucose['glucose_mg_dl'] < 70).mean() * 100
    st.metric("Time Low", f"{time_low:.1f}%", help="<70 mg/dL")

with col4:
    crash_count = len([c for c in crash_events if start_date <= c['start_time'].date() <= end_date]) if crash_events else 0
    st.metric("Crash Events", crash_count)

with col5:
    if crash_events:
        stats = get_crash_summary_stats(crash_events)
        st.metric("Avg Drop", f"{stats['avg_drop_magnitude']:.0f} mg/dL")
    else:
        st.metric("Avg Drop", "N/A")

st.divider()

# Main glucose chart
st.subheader("🩸 Glucose Over Time")

# Performance optimization: Downsample if data is too dense (more than ~3 days of 5-min data)
# 12 readings/hour * 24 hours * 3 days = 864 readings
chart_df = filtered_glucose.copy()
if len(chart_df) > 1000:
    # Resample to 15-min intervals for the chart if many days selected
    chart_df = chart_df.set_index('timestamp').resample('15T').agg({
        'glucose_mg_dl': 'mean',
        'velocity_smoothed': 'mean',
        'is_danger_zone': 'max'
    }).reset_index().dropna(subset=['glucose_mg_dl'])

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.1,
    row_heights=[0.7, 0.3],
    subplot_titles=("Glucose Level", "Glucose Velocity")
)

# Glucose trace - Use Scattergl for performance
fig.add_trace(
    go.Scattergl(
        x=chart_df['timestamp'],
        y=chart_df['glucose_mg_dl'],
        mode='lines',
        name='Glucose',
        line=dict(color='#1f77b4', width=2),
        hovertemplate='%{x|%b %d, %I:%M %p}<br>Glucose: %{y:.0f} mg/dL<extra></extra>'
    ),
    row=1, col=1
)

# Add target range (Shapes are okay if limited in number)
fig.add_hrect(y0=70, y1=140, line_width=0, fillcolor="green", opacity=0.1, row=1, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="orange", opacity=0.5, row=1, col=1)
fig.add_hline(y=140, line_dash="dash", line_color="orange", opacity=0.5, row=1, col=1)

# Mark crash events
if crash_events:
    for crash in crash_events:
        crash_start = crash['start_time']
        if hasattr(crash_start, 'date') and start_date <= crash_start.date() <= end_date:
            fig.add_vrect(
                x0=crash['start_time'],
                x1=crash['end_time'],
                fillcolor="red",
                opacity=0.2,
                line_width=0,
                row=1, col=1
            )

# Add food markers if available
if food_df is not None and not food_df.empty:
    food_mask = (food_df['timestamp'].dt.date >= start_date) & (food_df['timestamp'].dt.date <= end_date)
    filtered_food = food_df[food_mask]

    if not filtered_food.empty:
        # Performance optimization: Use a single trace for vertical lines instead of many add_vline calls
        y_min = chart_df['glucose_mg_dl'].min()
        y_max = chart_df['glucose_mg_dl'].max()

        line_x = []
        line_y = []
        for ts in filtered_food['timestamp']:
            line_x.extend([ts, ts, None])
            line_y.extend([y_min, y_max, None])

        fig.add_trace(
            go.Scattergl(
                x=line_x,
                y=line_y,
                mode='lines',
                line=dict(color='green', width=1, dash='dot'),
                opacity=0.2,
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )

        # Add scatter markers at top for food names on hover
        fig.add_trace(
            go.Scattergl(
                x=filtered_food['timestamp'],
                y=[y_max + 5] * len(filtered_food),
                mode='markers',
                name='Foods',
                marker=dict(color='green', size=8, symbol='triangle-down'),
                text=filtered_food['food_name'],
                hovertemplate='%{x|%I:%M %p}<br>%{text}<extra></extra>'
            ),
            row=1, col=1
        )

# Velocity trace
if 'velocity_smoothed' in chart_df.columns:
    fig.add_trace(
        go.Scattergl(
            x=chart_df['timestamp'],
            y=chart_df['velocity_smoothed'],
            mode='lines',
            name='Velocity',
            line=dict(color='purple', width=1.5),
            hovertemplate='%{x|%b %d, %I:%M %p}<br>Velocity: %{y:.2f} mg/dL/min<extra></extra>'
        ),
        row=2, col=1
    )

    # Danger zone threshold
    fig.add_hline(y=-DANGER_ZONE_THRESHOLD, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.3, row=2, col=1)

fig.update_layout(
    height=600,
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode='x unified'
)

fig.update_yaxes(title_text="mg/dL", row=1, col=1)
fig.update_yaxes(title_text="mg/dL/min", row=2, col=1)
fig.update_xaxes(title_text="Time", row=2, col=1, tickformat='%I:%M %p')  # 12-hour format

st.plotly_chart(fig, width="stretch")

# Meal Response Assessment section
if food_df is not None and not food_df.empty:
    st.divider()
    st.subheader("🍽️ Meal Response Assessment")

    # Group foods into meals (by Day + Group)
    meals_df = group_foods_into_meals(food_df)

    if not meals_df.empty:
        # Merge meals with glucose data
        merged_meals = merge_meals_with_glucose(filtered_glucose, meals_df)

        if not merged_meals.empty:
            # Load existing AI assessments from database (cached for this render)
            if 'ai_assessments_cache' not in st.session_state:
                st.session_state['ai_assessments_cache'] = get_all_meal_ai_assessments()
            ai_assessments = st.session_state['ai_assessments_cache']

            # Filter by date range
            merged_meals['meal_time'] = pd.to_datetime(merged_meals['meal_time'])
            meal_mask = (merged_meals['meal_time'].dt.date >= start_date) & (merged_meals['meal_time'].dt.date <= end_date)
            filtered_meals = merged_meals[meal_mask]

            if not filtered_meals.empty:
                # Pre-calculate analysis for all meals (required for sorting/filtering)
                meal_analyses = {}
                for idx, meal in filtered_meals.iterrows():
                    glucose_readings = meal.get('glucose_readings', [])
                    has_any_data = len(glucose_readings) > 0
                    analysis = analyze_meal_response(meal.to_dict()) if has_any_data else {}

                    # Store analysis and basic stats
                    analysis['has_any_data'] = has_any_data

                    # Risk Level (Refined logic: Issues show even if partial)
                    data_complete = meal.get('data_complete', True)

                    if not has_any_data:
                        risk = "Awaiting Data"
                    else:
                        m_rise_v = analysis.get('max_rise_velocity', 0)
                        m_rise_d = analysis.get('glucose_rise', 0)
                        m_peak = analysis.get('peak_glucose', 0)
                        m_drop_v = abs(analysis.get('max_drop_velocity', 0))
                        m_floor = analysis.get('min_glucose', 100)

                        is_bad = (m_rise_v > 2.5 or m_rise_d > 50 or m_peak > 140 or m_drop_v > 1.5 or m_floor < 65)
                        is_normal = (
                            (1.5 <= m_rise_v <= 2.5) or
                            (30 <= m_rise_d <= 50) or
                            (120 <= m_peak <= 140) or
                            (1.0 <= m_drop_v <= 1.5) or
                            (65 <= m_floor <= 75)
                        )

                        if is_bad:
                            risk = "Reactive"
                        elif not data_complete:
                            risk = "Partial Data"
                        elif is_normal:
                            risk = "Normal"
                        else:
                            risk = "Great"

                    analysis['risk_category'] = risk
                    analysis['data_complete'] = data_complete
                    meal_analyses[idx] = analysis

                # Sorting and Filtering UI
                st.markdown("##### 🔍 Filter & Sort Meals")

                # Risk level checkboxes
                st.markdown("**Risk Level Filters:**")
                st.markdown("""
                <div style="font-size: 0.9em; color: gray; margin-bottom: 20px;">
                <b>Rise Velocity</b>: The fastest rate of glucose increase (mg/dL per minute). Higher values indicate faster absorption.<br>
                <b>Rise Delta</b>: The total change from your baseline (starting) glucose to the highest peak.<br>
                <b>Peak Glucose</b>: The maximum glucose level reached within 3 hours after eating.<br>
                <b>Max Drop Velocity</b>: The fastest rate of glucose decline. Very fast drops can cause 'crash' symptoms.<br>
                <b>Min Floor</b>: The lowest glucose value reached after the peak. Values below baseline indicate a reactive dip.
                </div>
                """, unsafe_allow_html=True)
                selected_risks = []

                # Helper to render styled filter
                def render_risk_filter(label, criteria, risk_val, key):
                    # Replace commas with spaced pipes for better digestion
                    styled_criteria = criteria.replace(", ", " &nbsp; | &nbsp; ")

                    c1, c2 = st.columns([0.05, 0.95])
                    with c1:
                        checked = st.checkbox("", value=True, key=key, label_visibility="collapsed")
                    with c2:
                        st.markdown(f"{label}")
                        st.markdown(f"<p style='margin-top: -15px; color: gray; font-size: 1em;'>{styled_criteria}</p>", unsafe_allow_html=True)
                    return checked

                # Define the filters
                filters = [
                    ("🟢 **Great (Stable)**", "Rise < 1.5 mg/dL/min, Delta < 30 mg/dL, Peak < 120 mg/dL, Drop < 1.0 mg/dL/min, Floor > 75 mg/dL", "Great", "risk_great"),
                    ("🟡 **Normal (Good)**", "Rise 1.5-2.5 mg/dL/min, Delta 30-50 mg/dL, Peak 120-140 mg/dL, Drop 1.0-1.5 mg/dL/min, Floor 65-75 mg/dL", "Normal", "risk_normal"),
                    ("🔴 **Reactive (Bad)**", "Rise > 2.5 mg/dL/min, Delta > 50 mg/dL, Peak > 140 mg/dL, Drop > 1.5 mg/dL/min, Floor < 65 mg/dL", "Reactive", "risk_bad"),
                    ("🔄 **Partial Data**", "< 180 min coverage (and no 'Bad' metrics detected yet)", "Partial Data", "risk_partial"),
                    ("⏳ **Awaiting Data**", "No glucose readings available for this meal period yet", "Awaiting Data", "risk_await")
                ]

                # Render filters and collect selections
                for label, criteria, val, key in filters:
                    if render_risk_filter(label, criteria, val, key):
                        selected_risks.append(val)

                if not selected_risks:
                    st.warning("⚠️ No risk levels selected. Filtered results will be empty.")

                fcol1, fcol2 = st.columns([1, 1])
                with fcol1:
                    sort_on = st.selectbox("Sort By", options=[
                        "Meal Time", "Max Drop Velocity", "Rise Duration", "Drop Duration", "Glucose Rise", "Total Drop"
                    ])
                with fcol2:
                    sort_dir = st.radio("Direction", options=["Ascending", "Descending"], horizontal=True, index=1 if "Velocity" in sort_on or "Time" in sort_on else 0)

                # Advanced Filters in expander
                with st.expander("More Filters (Velocity & Duration)"):
                    acol1, acol2, acol3 = st.columns(3)
                    with acol1:
                        v_limit = st.slider("Min Max Drop Velocity (abs)", 0.0, 5.0, 0.0, step=0.1, help="Show meals where the fastest drop was at least this many mg/dL/min")
                    with acol2:
                        rise_limit = st.slider("Min Rise Duration (min)", 0, 180, 0)
                    with acol3:
                        drop_limit = st.slider("Min Drop Duration (min)", 0, 180, 0)

                # Add helper columns for filtering/sorting
                df_to_sort = filtered_meals.copy()
                df_to_sort['risk_category'] = [meal_analyses[i]['risk_category'] for i in df_to_sort.index]
                df_to_sort['v_abs'] = [abs(meal_analyses[i].get('max_drop_velocity') or 0) for i in df_to_sort.index]
                df_to_sort['rise_dur'] = [meal_analyses[i].get('time_to_peak_minutes') or 0 for i in df_to_sort.index]
                df_to_sort['drop_dur'] = [meal_analyses[i].get('drop_duration_minutes') or 0 for i in df_to_sort.index]
                df_to_sort['rise_mag'] = [meal_analyses[i].get('glucose_rise') or 0 for i in df_to_sort.index]
                df_to_sort['drop_mag'] = [meal_analyses[i].get('total_drop') or 0 for i in df_to_sort.index]

                # Apply Filters
                mask = df_to_sort['risk_category'].isin(selected_risks)
                mask &= df_to_sort['v_abs'] >= v_limit
                mask &= df_to_sort['rise_dur'] >= rise_limit
                mask &= df_to_sort['drop_dur'] >= drop_limit

                display_meals = df_to_sort[mask].copy()

                # Map UI names to columns
                sort_map = {
                    "Meal Time": "meal_time",
                    "Max Drop Velocity": "v_abs",
                    "Rise Duration": "rise_dur",
                    "Drop Duration": "drop_dur",
                    "Glucose Rise": "rise_mag",
                    "Total Drop": "drop_mag"
                }

                is_asc = sort_dir == "Ascending"
                display_meals = display_meals.sort_values(sort_map[sort_on], ascending=is_asc)

                if display_meals.empty:
                    st.info("No meals match the selected filters.")
                else:
                    # Meal group icons
                    MEAL_ICONS = {
                        'Breakfast': '🌅',
                        'Lunch': '☀️',
                        'Dinner': '🌙',
                        'Snack': '🍎',
                        'Snack 1': '🍎',
                        'Snack 2': '🍎',
                        'Snack 3': '🍎',
                    }
                    DEFAULT_MEAL_ICON = '🍽️'

                    current_date = None

                    for idx, meal in display_meals.iterrows():
                        # Add date heading when date changes (only if sorting by time)
                        if sort_on == "Meal Time":
                            meal_date = meal['meal_time'].date()
                            if meal_date != current_date:
                                current_date = meal_date
                                st.markdown(f"### 📅 {meal_date.strftime('%A, %B %d, %Y')}")

                        # Use pre-calculated analysis
                        analysis = meal_analyses[idx]
                        has_any_data = analysis['has_any_data']
                        data_complete = analysis['data_complete']
                        data_coverage_minutes = meal.get('data_coverage_minutes', 0)
                        minutes_until_complete = meal.get('minutes_until_complete', 0)
                        glucose_readings = meal.get('glucose_readings', [])

                        meal_time = meal['meal_time']
                        group_name = meal.get('group', 'Unknown')
                        food_count = meal.get('food_count', 0)

                        # Create unique meal key for database
                        meal_key = f"{meal_time.strftime('%Y-%m-%d')}_{group_name}"

                        # Extract stats from pre-calculated analysis
                        max_drop_velocity = analysis.get('max_drop_velocity', 0)
                        total_drop = analysis.get('total_drop', 0)
                        drop_duration_minutes = analysis.get('drop_duration_minutes')

                        # Determine risk level and color (using pre-calculated category)
                        risk_text = analysis['risk_category']
                        if risk_text == "Reactive":
                            risk_emoji = "🔴"
                        elif risk_text == "Normal":
                            risk_emoji = "🟡"
                        elif risk_text == "Great":
                            risk_emoji = "🟢"
                        elif risk_text == "Partial Data":
                            risk_emoji = "🔄"
                            risk_text = f"Partial ({int(data_coverage_minutes)} min)"
                        elif risk_text == "Awaiting Data":
                            risk_emoji = "⏳"
                        else:
                            risk_emoji = "⚪"

                        # Check if we have an AI assessment already
                        existing_assessment = ai_assessments.get(meal_key)
                        has_ai = existing_assessment is not None and existing_assessment.get('ai_assessment')
                        ai_icon = "🤖" if has_ai else ""

                        # Get meal group icon
                        meal_icon = MEAL_ICONS.get(group_name, DEFAULT_MEAL_ICON)
                        # Format date and time for the expander title
                        meal_date_display = meal_time.strftime('%a, %b %d')
                        meal_time_display = meal_time.strftime('%I:%M %p').lstrip('0')  # 12-hour format, strip leading zero

                        with st.expander(f"{risk_emoji} {meal_date_display} • {meal_time_display} {meal_icon} {group_name} ({food_count} foods) - {risk_text} {ai_icon}", expanded=False):
                            # Show data status message for incomplete data
                            if not has_any_data:
                                st.warning(f"⏳ No glucose data available yet. Sync your CGM to see response data.")
                            elif not data_complete:
                                hours_left = int(minutes_until_complete // 60)
                                mins_left = int(minutes_until_complete % 60)
                                if hours_left > 0:
                                    time_str = f"{hours_left}h {mins_left}m"
                                else:
                                    time_str = f"{mins_left} min"
                                st.info(f"🔄 Partial data: {int(data_coverage_minutes)} min of 180 min. Full data available in ~{time_str} after CGM sync.")

                            # Show foods in this meal with timestamps in a grid
                            foods_with_times = meal.get('foods_with_times', [])
                            if foods_with_times:
                                st.markdown("**🍽️ Foods in this meal:**")
                                # Create grid with 3 columns
                                food_cols = st.columns(3)
                                for i, food_item in enumerate(foods_with_times):
                                    with food_cols[i % 3]:
                                        food_time = food_item['timestamp']
                                        if hasattr(food_time, 'strftime'):
                                            time_str = food_time.strftime('%I:%M %p').lstrip('0')
                                        else:
                                            time_str = str(food_time)
                                        # Distinct colors for time and food, no bullets
                                        st.markdown(f":gray[{time_str}] **{food_item['name']}**")
                            else:
                                # Fallback to simple list if no timestamps available
                                foods_list = meal.get('foods', [])
                                if foods_list:
                                    st.markdown(f"**Foods:** {', '.join(foods_list)}")

                            # Summary Statistics Row
                            st.markdown("---")
                            mcol1, mcol2, mcol3, mcol4 = st.columns(4)

                            with mcol1:
                                st.markdown("##### 📈 Rise Analysis")
                                if has_any_data:
                                    peak = analysis.get('peak_glucose') or 0
                                    rise_delta = analysis.get('glucose_rise') or 0
                                    rise_vel = analysis.get('max_rise_velocity') or 0
                                    rise_dur = analysis.get('time_to_peak_minutes') or 0

                                    peak_color = "red" if peak > 140 else "orange" if peak >= 120 else "green"
                                    delta_color = "red" if rise_delta > 50 else "orange" if rise_delta >= 30 else "green"
                                    vel_color = "red" if rise_vel > 2.5 else "orange" if rise_vel >= 1.5 else "green"

                                    st.markdown(f"Peak: **:{peak_color}[{peak:.0f} mg/dL]**")
                                    st.markdown(f"Rise Delta: **:{delta_color}[+{rise_delta:.0f} mg/dL]**")
                                    st.markdown(f"Rise Velocity: **:{vel_color}[{rise_vel:.2f} mg/dL/min]**")
                                    st.markdown(f"Duration: **{rise_dur:.0f} min**")
                                else:
                                    st.markdown("No data available")

                            with mcol2:
                                st.markdown("##### 📉 Drop Analysis")
                                if has_any_data:
                                    floor = analysis.get('min_glucose') or 0
                                    drop_vel = abs(analysis.get('max_drop_velocity') or 0)
                                    total_drop = analysis.get('total_drop') or 0
                                    drop_dur = analysis.get('drop_duration_minutes') or 0

                                    floor_color = "red" if floor < 65 else "orange" if floor <= 75 else "green"
                                    drop_vel_color = "red" if drop_vel > 1.5 else "orange" if drop_vel >= 1.0 else "green"

                                    st.markdown(f"Min Floor: **:{floor_color}[{floor:.0f} mg/dL]**")
                                    st.markdown(f"Max Drop Vel: **:{drop_vel_color}[{drop_vel:.2f} mg/dL/min]**")
                                    st.markdown(f"Total Drop: **{total_drop:.0f} mg/dL**")
                                    st.markdown(f"Duration: **{drop_dur:.0f} min**")
                                else:
                                    st.markdown("No data available")

                            with mcol3:
                                st.markdown("##### 🍎 Macros")
                                st.markdown(f"Carbs: **{meal.get('carbs_g', 0):.1f}g**")
                                st.markdown(f"Protein: **{meal.get('protein_g', 0):.1f}g**")
                                st.markdown(f"Fat: **{meal.get('fat_g', 0):.1f}g**")
                                st.markdown(f"Calories: **{meal.get('calories', 0):.0f} kcal**")

                            with mcol4:
                                st.markdown("##### 📊 Ratios & More")
                                carbs = meal.get('carbs_g', 0)
                                protein = meal.get('protein_g', 0)
                                fiber = meal.get('fiber_g', 0)
                                sugar = meal.get('sugar_g', 0)
                                p_c_ratio = protein / carbs if carbs > 0 else 0

                                fiber_color = "green" if fiber >= 5 else "orange" if fiber >= 2 else "gray"
                                sugar_color = "red" if sugar > 15 else "orange" if sugar > 5 else "green"

                                st.markdown(f"P:C Ratio: **{p_c_ratio:.2f}**")
                                st.markdown(f"Fiber: **:{fiber_color}[{fiber:.1f}g]**")
                                st.markdown(f"Sugar: **:{sugar_color}[{sugar:.1f}g]**")
                                st.markdown(f"Food Items: **{food_count}**")

                            # AI Assessment Section (only show if we have glucose data)
                            if has_any_data:
                                st.divider()
                                if has_ai:
                                    st.markdown("### 🤖 AI Assessment")
                                    st.markdown(existing_assessment.get('ai_assessment', ''))
                                else:
                                    # Button to generate AI assessment
                                    if st.button(f"🤖 Generate AI Assessment", key=f"ai_btn_{meal_key}"):
                                        with st.spinner("Generating AI assessment..."):
                                            # Get foods list for AI
                                            foods_for_ai = meal.get('foods', [])
                                            # Prepare meal data for AI
                                            meal_data_for_ai = {
                                                'meal_key': meal_key,
                                                'meal_time': meal_time.isoformat(),
                                                'group_name': group_name,
                                                'foods': foods_for_ai,
                                                'carbs_g': float(meal.get('carbs_g', 0)),
                                                'protein_g': float(meal.get('protein_g', 0)),
                                                'fat_g': float(meal.get('fat_g', 0)),
                                                'fiber_g': float(meal.get('fiber_g', 0)),
                                                'sugar_g': float(meal.get('sugar_g', 0)),
                                                'baseline_glucose': float(analysis.get('baseline_glucose', 0)),
                                                'peak_glucose': float(analysis.get('peak_glucose', 0)),
                                                'glucose_rise': float(analysis.get('glucose_rise', 0)),
                                                'max_drop_velocity': float(max_drop_velocity),
                                                'total_drop': float(total_drop),
                                                'crash_detected': analysis.get('crash_detected', False),
                                            }

                                            # Call Gemini API
                                            ai_text = analyze_meal_with_ai(meal_data_for_ai)
                                            meal_data_for_ai['ai_assessment'] = ai_text

                                            # Save to database
                                            if save_meal_ai_assessment(meal_data_for_ai):
                                                # Update cache and rerun
                                                st.session_state['ai_assessments_cache'][meal_key] = meal_data_for_ai
                                                st.success("AI assessment saved!")
                                                st.rerun()
                                            else:
                                                # Still show the assessment even if save failed
                                                st.warning("Could not save to database, but here's the assessment:")
                                                st.markdown(ai_text)

                            # Mini chart for this meal with velocity
                            if glucose_readings:
                                meal_glucose_df = pd.DataFrame(glucose_readings)

                                # Create subplot with glucose and velocity
                                from plotly.subplots import make_subplots
                                fig_meal = make_subplots(
                                    rows=2, cols=1,
                                    shared_xaxes=True,
                                    vertical_spacing=0.1,
                                    row_heights=[0.7, 0.3],
                                    subplot_titles=(f"Glucose Response: {group_name}", "Velocity (mg/dL/min)")
                                )

                                # Glucose trace - Use Scattergl
                                fig_meal.add_trace(
                                    go.Scattergl(
                                        x=meal_glucose_df['minutes_from_meal'],
                                        y=meal_glucose_df['glucose_mg_dl'],
                                        mode='lines+markers',
                                        name='Glucose',
                                        line=dict(color='#1f77b4', width=2)
                                    ),
                                    row=1, col=1
                                )
                                fig_meal.add_hline(y=70, line_dash="dash", line_color="orange", opacity=0.5, row=1, col=1)
                                fig_meal.add_hline(y=140, line_dash="dash", line_color="orange", opacity=0.5, row=1, col=1)

                                # Velocity trace if available
                                if 'velocity_smoothed' in meal_glucose_df.columns:
                                    fig_meal.add_trace(
                                        go.Scattergl(
                                            x=meal_glucose_df['minutes_from_meal'],
                                            y=meal_glucose_df['velocity_smoothed'],
                                            mode='lines',
                                            name='Velocity',
                                            line=dict(color='purple', width=1.5)
                                        ),
                                        row=2, col=1
                                    )
                                    fig_meal.add_hline(y=-DANGER_ZONE_THRESHOLD, line_dash="dash", line_color="red", row=2, col=1)
                                    fig_meal.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.3, row=2, col=1)

                                fig_meal.update_xaxes(title_text="Minutes from Meal", row=2, col=1)
                                fig_meal.update_yaxes(title_text="mg/dL", row=1, col=1)
                                fig_meal.update_yaxes(title_text="mg/dL/min", row=2, col=1)
                                st.plotly_chart(fig_meal, width="stretch")
            else:
                st.info("No meals found in the selected date range.")
        else:
            st.info("No glucose data matched with meals.")
    else:
        st.info("Upload food data to see meal assessments.")

# Crash analysis section
if crash_events:
    st.divider()
    st.subheader("🚨 Crash Event Analysis")

    col1, col2 = st.columns(2)

    with col1:
        # Crash events table
        crash_df = pd.DataFrame(crash_events)
        crash_df['start_time'] = pd.to_datetime(crash_df['start_time'])
        crash_df_display = crash_df[['start_time', 'drop_magnitude', 'max_velocity', 'duration_minutes']].copy()
        crash_df_display.columns = ['Time', 'Drop (mg/dL)', 'Max Velocity', 'Duration (min)']
        crash_df_display['Time'] = crash_df_display['Time'].dt.strftime('%Y-%m-%d %I:%M %p')
        crash_df_display['Max Velocity'] = crash_df_display['Max Velocity'].apply(lambda x: f"{abs(x):.2f}")
        crash_df_display['Drop (mg/dL)'] = crash_df_display['Drop (mg/dL)'].apply(lambda x: f"{x:.1f}")
        crash_df_display['Duration (min)'] = crash_df_display['Duration (min)'].apply(lambda x: f"{x:.0f}")

        st.dataframe(crash_df_display, width="stretch", hide_index=True)

    with col2:
        # Crash distribution chart
        fig_dist = px.histogram(
            crash_df,
            x='drop_magnitude',
            nbins=10,
            title='Crash Magnitude Distribution',
            labels={'drop_magnitude': 'Drop Magnitude (mg/dL)'}
        )
        st.plotly_chart(fig_dist, width="stretch")

# Macro correlation section
if food_df is not None and not food_df.empty and crash_events:
    st.divider()
    st.subheader("🥗 Macro-Nutrient Correlations")

    col1, col2 = st.columns(2)

    with col1:
        # Protein to Carb ratio analysis
        food_df_analysis = food_df.copy()
        food_df_analysis['protein_carb_ratio'] = food_df_analysis['protein_g'] / food_df_analysis['carbs_g'].replace(0, 1)

        fig_ratio = px.scatter(
            food_df_analysis,
            x='carbs_g',
            y='protein_g',
            color='sugar_g',
            size='calories',
            hover_data=['food_name'],
            title='Protein vs Carbs (colored by Sugar)',
            labels={'carbs_g': 'Carbs (g)', 'protein_g': 'Protein (g)', 'sugar_g': 'Sugar (g)'}
        )
        st.plotly_chart(fig_ratio, width="stretch")

    with col2:
        # Daily macro breakdown
        daily_macros = food_df.groupby(food_df['timestamp'].dt.date).agg({
            'carbs_g': 'sum',
            'protein_g': 'sum',
            'fat_g': 'sum',
            'fiber_g': 'sum'
        }).reset_index()
        daily_macros.columns = ['Date', 'Carbs', 'Protein', 'Fat', 'Fiber']

        fig_macros = px.bar(
            daily_macros,
            x='Date',
            y=['Carbs', 'Protein', 'Fat', 'Fiber'],
            title='Daily Macro Breakdown',
            barmode='group'
        )
        st.plotly_chart(fig_macros, width="stretch")

# Sidebar stats
with st.sidebar:
    st.header("📊 Quick Stats")

    if crash_events:
        stats = get_crash_summary_stats(crash_events)
        st.metric("Total Crashes", stats['total_crashes'])
        st.metric("Avg Duration", f"{stats['avg_duration']:.0f} min")
        st.metric("Worst Velocity", f"{abs(stats['worst_velocity']):.2f} mg/dL/min")
