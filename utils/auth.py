import streamlit as st

def check_password():
    """
    Returns True if the user had the correct password.
    Uses st.secrets for the shared password.
    """
    def password_entered():
        if st.session_state["password"] == st.secrets.get("SHARED_PASSWORD"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct"):
        return True

    # Show input for password
    st.title("🔐 Access Restricted")
    st.text_input(
        "Please enter the access password",
        type="password",
        on_change=password_entered,
        key="password"
    )

    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")

    # Help text for local dev
    if not st.secrets.get("SHARED_PASSWORD"):
        st.info("💡 No SHARED_PASSWORD found in secrets. Add it to .streamlit/secrets.toml")

    return False
