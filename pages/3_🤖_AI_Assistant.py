"""AI Chat page with Gemini integration."""
import streamlit as st
import pandas as pd
from datetime import datetime
from services import analyze_crash_event, predict_crash_timing, analyze_symptom_mapping, chat_with_context
from database import get_chat_history, save_chat_message, get_glucose_readings, get_food_logs
from config import GEMINI_API_KEY
from utils.auth import check_password

st.set_page_config(page_title="AI Assistant", page_icon="🤖", layout="wide")

# Authentication check
if not check_password():
    st.stop()

st.title("🤖 AI Analysis Assistant")
st.markdown("Ask questions about your glucose data, get crash explanations, and receive personalized insights.")

# Check API key
if not GEMINI_API_KEY:
    st.warning("⚠️ Gemini API key not configured. Please add `GEMINI_API_KEY` to your `.env` file.")
    st.code("GEMINI_API_KEY=your_api_key_here", language="bash")
    st.stop()

# Initialize chat history
if 'messages' not in st.session_state:
    # Try to load from database
    db_history = get_chat_history(limit=20)
    if db_history:
        st.session_state.messages = [{"role": m['role'], "content": m['content']} for m in db_history]
    else:
        st.session_state.messages = []

# Sidebar with analysis tools
with st.sidebar:
    st.header("🔧 Quick Analysis Tools")

    analysis_type = st.selectbox(
        "Select Analysis Type",
        ["💬 General Chat", "🚨 Analyze Crash", "🔮 Predict Crash", "🩺 Symptom Mapping"]
    )

    st.divider()

    if analysis_type == "🚨 Analyze Crash":
        st.subheader("Crash Event Details")

        # Get crash events from session
        crash_events = st.session_state.get('crash_events', [])

        if crash_events:
            crash_options = [f"Crash at {c['start_time']}" for c in crash_events]
            selected_crash_idx = st.selectbox("Select crash to analyze", range(len(crash_options)), format_func=lambda x: crash_options[x])

            if st.button("🔍 Analyze Selected Crash", type="primary"):
                selected_crash = crash_events[selected_crash_idx]

                # Find related food
                food_df = st.session_state.get('food_df')
                food_context = None
                if food_df is not None:
                    crash_time = selected_crash['start_time']
                    # Find food eaten 30-180 min before crash
                    for _, food in food_df.iterrows():
                        time_diff = (crash_time - food['timestamp']).total_seconds() / 60
                        if 30 <= time_diff <= 180:
                            food_context = food.to_dict()
                            break

                with st.spinner("Analyzing crash event..."):
                    analysis = analyze_crash_event(selected_crash, food_context)
                    st.session_state.messages.append({"role": "assistant", "content": analysis})
                    save_chat_message("assistant", analysis)
        else:
            st.info("No crash events loaded. Upload data first.")

    elif analysis_type == "🔮 Predict Crash":
        st.subheader("Meal Details for Prediction")

        food_name = st.text_input("Food Name", "")
        col1, col2 = st.columns(2)
        with col1:
            carbs = st.number_input("Carbs (g)", 0, 500, 30)
            protein = st.number_input("Protein (g)", 0, 200, 10)
            fiber = st.number_input("Fiber (g)", 0, 100, 2)
        with col2:
            fat = st.number_input("Fat (g)", 0, 200, 5)
            sugar = st.number_input("Sugar (g)", 0, 200, 15)

        if st.button("🔮 Predict Crash Timing", type="primary"):
            meal_data = {
                'food_name': food_name,
                'carbs_g': carbs,
                'protein_g': protein,
                'fat_g': fat,
                'fiber_g': fiber,
                'sugar_g': sugar
            }

            with st.spinner("Generating prediction..."):
                prediction = predict_crash_timing(meal_data)
                st.session_state.messages.append({"role": "assistant", "content": prediction})
                save_chat_message("assistant", prediction)

    elif analysis_type == "🩺 Symptom Mapping":
        st.subheader("Symptom Details")

        symptom = st.text_input("Describe your symptom", "Felt dizzy")
        symptom_time = st.time_input("When did it occur?", datetime.now().time())
        symptom_date = st.date_input("Date", datetime.now().date())

        if st.button("🩺 Analyze Symptom", type="primary"):
            symptom_datetime = datetime.combine(symptom_date, symptom_time)

            # Get glucose data around symptom time
            glucose_df = st.session_state.get('glucose_df')
            glucose_context = []

            if glucose_df is not None:
                # Get readings 60 min before to 30 min after
                mask = (
                    (glucose_df['timestamp'] >= symptom_datetime - pd.Timedelta(minutes=60)) &
                    (glucose_df['timestamp'] <= symptom_datetime + pd.Timedelta(minutes=30))
                )
                glucose_context = glucose_df[mask].to_dict('records')

            with st.spinner("Analyzing symptom pattern..."):
                analysis = analyze_symptom_mapping(symptom, str(symptom_datetime), glucose_context)
                st.session_state.messages.append({"role": "assistant", "content": analysis})
                save_chat_message("assistant", analysis)

    st.divider()

    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Main chat interface
st.subheader("💬 Chat")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me anything about your glucose data..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat_message("user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Prepare context
            glucose_context = None
            food_context = None

            glucose_df = st.session_state.get('glucose_df')
            if glucose_df is not None:
                # Get last 24 hours of data for context
                recent = glucose_df.tail(50)
                glucose_context = recent[['timestamp', 'glucose_mg_dl']].to_string()

            food_df = st.session_state.get('food_df')
            if food_df is not None:
                recent_food = food_df.tail(10)
                food_context = recent_food[['timestamp', 'food_name', 'carbs_g', 'protein_g']].to_string()

            response = chat_with_context(
                prompt,
                st.session_state.messages[:-1],  # Exclude current message
                glucose_context,
                food_context
            )

            st.markdown(response)

    # Add assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_chat_message("assistant", response)

# Suggested prompts
if not st.session_state.messages:
    st.markdown("### 💡 Suggested Questions")

    suggestions = [
        "What patterns do you see in my glucose data?",
        "Why do I crash after breakfast?",
        "What foods should I eat to prevent crashes?",
        "How can I improve my protein-to-carb ratio?",
        "What time of day are my glucose levels most stable?",
    ]

    cols = st.columns(2)
    for i, suggestion in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(suggestion, key=f"suggest_{i}"):
                st.session_state.messages.append({"role": "user", "content": suggestion})
                st.rerun()
