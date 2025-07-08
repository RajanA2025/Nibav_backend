import streamlit as st
from w1 import load_faq
from w3 import get_answer, compute_question_embeddings
from db import setup_database, save_user_info, get_user_count, save_interaction, user_exists
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import time

# Initialize DB
setup_database()

# Load and cache the FAQ and embeddings
@st.cache_resource
def setup_bot():
    questions, concise, detailed = load_faq("data/faq.csv")
    compute_question_embeddings(questions)
    return questions, concise, detailed

# Page setup
st.set_page_config(page_title="Nibav Lift Chatbot", page_icon="🏠")
st.title("🏠 Nibav Lift - FAQ Chatbot")
st.markdown("👋 Welcome to Nibav Lift Assistant! I'm here to help you.")

# Step 1: Collect and validate email
if "email" not in st.session_state or not st.session_state.email:
    st.markdown("🧾 **I would like to know you to serve you better.**")
    email = st.text_input("📧 Can I know your email ID?")
    if email.strip():
        if "@" in email and "." in email:
            st.session_state.email = email.strip()
            st.rerun()
        else:
            st.warning("❗ Please enter a valid email address.")
    st.stop()

# Step 2: Collect phone and save info
if "phone" not in st.session_state or not st.session_state.phone:
    st.markdown("🧾 **I would like to know you to serve you better.**")
    phone = st.text_input("📱 Can I know your phone number?")
    if phone.strip():
        if phone.isdigit() and len(phone) == 10:
            st.session_state.phone = phone.strip()

            # Check if user already exists
            if user_exists(st.session_state.email, st.session_state.phone):
                st.success("👋 Welcome back, good to see you!")
            else:
                # Save user to DB with intent as "N/A"
                st.session_state.intent = "N/A"
                save_user_info(st.session_state.email, st.session_state.phone, st.session_state.intent)
                st.success("✅ You're now connected with the assistant.")

            # Show user count
            st.info(f"👥 Total unique users interacted: {get_user_count()}")
            time.sleep(3)  # Pause briefly before continuing

            st.session_state.last_active = datetime.now()
            st.rerun()
        else:
            st.warning("❗ Please enter a valid 10-digit phone number.")
    st.stop()

# Track inactivity
if "last_active" not in st.session_state:
    st.session_state.last_active = datetime.now()

# End session handling
if st.session_state.get("chat_ended", False):
    st.success("👋 Thank you for chatting with me. Have a great day!")
    st.stop()

# Load chatbot data
questions, concise, detailed = setup_bot()

# Chat interface
st.markdown("---")
st.markdown("💬 **Ask me anything about Nibav Home Lifts**  \n_(e.g., warranty, safety, installation, noise)_")

# Input reset handling
if "chat_input_key" not in st.session_state:
    st.session_state.chat_input_key = str(time.time())

def reset_input():
    st.session_state.chat_input = ""
    st.session_state.chat_input_key = str(time.time())

user_query = st.text_input("💬 You:", key=st.session_state.chat_input_key)

if user_query:
    st.session_state.last_active = datetime.now()
    short_ans, long_ans = get_answer(user_query, questions, concise, detailed)
    # Store the interaction (must have email)
    email = st.session_state.get("email", None)
    if email:
        bot_response = short_ans if short_ans else "No matching answer found."
        save_interaction(email, user_query, bot_response)
    if short_ans:
        st.success("🤖: " + short_ans)
        if st.button("📘 Tell me more"):
            st.info(long_ans)
        st.markdown("#### 🙋 Do you need anything else?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, I have more questions"):
                reset_input()
               
        with col2:
            if st.button("❌ No, I'm done"):
                st.session_state.chat_ended = True

    else:
        st.warning("🤖: Sorry, I couldn't find an answer to that. Just ask regarding the Nibav Lift")

# Auto-refresh to check inactivity
st_autorefresh(interval=50000, limit=None, key="refresh")

# Handle inactivity
# Handle inactivity
if datetime.now() - st.session_state.last_active > timedelta(seconds=90):
    st.markdown("---")
    st.success("⏱️ It seems you've been idle. Thank you for connecting with me. Have a wonderful day!")
    st.stop()