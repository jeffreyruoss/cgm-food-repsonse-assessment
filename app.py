"""
CGM Food Response Assessment
A Streamlit app for analyzing CGM data and correlating it with food intake
to detect and understand reactive hypoglycemia patterns.
"""
import streamlit as st
from config import SUPABASE_URL, GEMINI_API_KEY

st.set_page_config(
    page_title="CGM Food Response Assessment",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🩸 CGM Food Response Assessment")

st.markdown("""
Welcome to your personal CGM analysis dashboard! This app helps you:

- 📤 **Upload** daily CGM data from FreeStyle Libre and food logs from Cronometer
- 🔄 **Merge** timestamps to see exactly what you ate when glucose changes occurred
- 🚨 **Detect** dangerous glucose crashes (velocity > 2.0 mg/dL per minute)
- 📊 **Visualize** trends, patterns, and macro-nutrient correlations
- 🤖 **AI Analysis** with Gemini to understand why crashes happen
- 📋 **Export** professional reports for your physician
""")

st.divider()

# Quick status
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔧 Configuration Status")

    if SUPABASE_URL:
        st.success("✅ Supabase Connected")
    else:
        st.warning("⚠️ Supabase not configured")
        st.caption("Add `SUPABASE_URL` and `SUPABASE_KEY` to your `.env` file")

    if GEMINI_API_KEY:
        st.success("✅ Gemini AI Ready")
    else:
        st.warning("⚠️ Gemini API not configured")
        st.caption("Add `GEMINI_API_KEY` to your `.env` file")

with col2:
    st.subheader("🚀 Getting Started")
    st.markdown("""
    1. **Configure** - Set up your `.env` file with API keys
    2. **Upload** - Go to Upload Data page and drop your CSVs
    3. **Analyze** - View the Dashboard for insights
    4. **Chat** - Ask the AI Assistant questions
    5. **Export** - Generate reports for your doctor
    """)

st.divider()

# Navigation cards
st.subheader("📍 Quick Navigation")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    ### 📤 Upload Data
    Upload your daily CGM and food logs
    """)

with col2:
    st.markdown("""
    ### 📊 Dashboard
    View glucose trends and crash analysis
    """)

with col3:
    st.markdown("""
    ### 🤖 AI Assistant
    Get AI-powered insights and predictions
    """)

with col4:
    st.markdown("""
    ### 📋 Doctor Report
    Generate PDF reports for physicians
    """)

# Footer
st.divider()
st.caption("💡 Tip: Use the sidebar to navigate between pages")

with st.sidebar:
    st.header("📖 About")
    st.markdown("""
    This app analyzes CGM data to help understand
    **reactive hypoglycemia** patterns.

    **Key Features:**
    - Crash detection (velocity analysis)
    - Food-glucose correlation
    - AI-powered explanations
    - Professional reports

    ---

    *Not medical advice. Consult your healthcare provider.*
    """)
