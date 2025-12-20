import streamlit as st
from email import policy
from email.parser import BytesParser
from PIL import Image
import pytesseract
from openai import OpenAI
import re
import matplotlib.pyplot as plt
import sqlite3
import io
import os
import base64
import csv

# ---------- OCR PATH FIX (WINDOWS) ----------
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="AI Fraud Detection", layout="wide")

# ---------- DEMO LOGIN CREDENTIALS ----------
VALID_USERNAME = "admin"
VALID_PASSWORD = "1234"

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect("fraud_detection.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_type TEXT,
            content TEXT,
            classification TEXT,
            confidence INTEGER,
            reason TEXT,
            recommendation TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------- SAVE TO DATABASE ----------
def save_analysis(input_type, content, classification, confidence, reason, recommendation):
    conn = sqlite3.connect("fraud_detection.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO analysis (input_type, content, classification, confidence, reason, recommendation)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (input_type, content, classification, confidence, reason, recommendation))
    conn.commit()
    conn.close()

# ---------- SAVE TO CSV ----------
CSV_FILE = "fraud_detection_data.csv"

def save_to_csv(input_type, content, classification, confidence, reason, recommendation):
    # Create the file with headers if not present
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Input Type", "Content", "Classification", "Confidence", "Reason", "Recommendation"])
        writer.writerow([input_type, content, classification, confidence, reason, recommendation])

# ---------- PERSISTENT LOGIN HANDLER ----------
LOGIN_FILE = "login_state.txt"

def save_login_state(state: bool):
    with open(LOGIN_FILE, "w") as f:
        f.write("logged_in" if state else "logged_out")

def load_login_state() -> bool:
    if os.path.exists(LOGIN_FILE):
        with open(LOGIN_FILE, "r") as f:
            return f.read().strip() == "logged_in"
    return False

# ---------- SESSION STATE ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = load_login_state()

if "history" not in st.session_state:
    st.session_state.history = []

if "input_usage" not in st.session_state:
    st.session_state.input_usage = {"Text": 0, "Email (.eml)": 0, "Image": 0}

# ---------- SIDEBAR LOGIN ----------
with st.sidebar:
    st.header("🔐 Login")

    if not st.session_state.logged_in:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.button("Login")

        if login_btn:
            if username == VALID_USERNAME and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                save_login_state(True)
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
    else:
        st.success(f"👋 Logged in as {VALID_USERNAME}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            save_login_state(False)
            st.rerun()

# ---------- MAIN APP ----------
if st.session_state.logged_in:
    client = OpenAI(api_key="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")

    st.title("🚨 AI Fraud Detection Dashboard 🚨")
    st.write("Detects fraud in **Text, Email, and Images** ")
    st.divider()

    left, right = st.columns([2, 1])

    with left:
        st.subheader("📥 Input Section")

        input_type = st.selectbox("Select Input Type", ["Text", "Email (.eml)", "Image"])
        extracted_text = ""

        # ---------- TEXT ----------
        if input_type == "Text":
            extracted_text = st.text_area("Enter message text")

        # ---------- EMAIL ----------
        elif input_type == "Email (.eml)":
            uploaded_email = st.file_uploader("Upload .eml file", type=["eml"])
            if uploaded_email:
                msg = BytesParser(policy=policy.default).parse(uploaded_email)
                body = msg.get_body(preferencelist=('plain'))
                if body:
                    extracted_text = body.get_content()

        # ---------- IMAGE ----------
        elif input_type == "Image":
            uploaded_image = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])
            if uploaded_image:
                image = Image.open(uploaded_image)
                st.image(image, caption="Uploaded Image", use_column_width=True)
                extracted_text = pytesseract.image_to_string(image)

        if extracted_text:
            st.session_state.input_usage[input_type] += 1
            st.subheader("📤 Extracted Text")
            st.write(extracted_text)

        detect = st.button("🚀 Detect Fraud")

    with right:
        st.subheader("📊 Live Analytics")

        # ---------- Classification Bar Chart ----------
        if st.session_state.history:
            counts = {
                "Legit": st.session_state.history.count("Legit"),
                "Spam": st.session_state.history.count("Spam"),
                "Fraud": st.session_state.history.count("Fraud")
            }
            st.bar_chart(counts)

        # ---------- Input Usage Pie Chart ----------
        if sum(st.session_state.input_usage.values()) > 0:
            fig, ax = plt.subplots()
            ax.pie(
                st.session_state.input_usage.values(),
                labels=st.session_state.input_usage.keys(),
                autopct="%1.1f%%"
            )
            ax.set_title("Input Type Usage")
            st.pyplot(fig)

    # ================= LLM PROCESS =================
    if detect and extracted_text:
        prompt = f"""
        You are an AI fraud detection system.
        Analyze the message and return:
        Classification: Legit / Spam / Fraud
        Confidence: number from 0 to 100
        Reason: one line

        Message:
        "{extracted_text}"
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        # ---------- Parse values ----------
        cls_match = re.search(r'Classification:\s*(\w+)', result)
        conf_match = re.search(r'Confidence:\s*(\d+)', result)
        reason_match = re.search(r'Reason:\s*(.*)', result)

        classification = cls_match.group(1) if cls_match else "Unknown"
        confidence = int(conf_match.group(1)) if conf_match else 0
        reason = reason_match.group(1).strip() if reason_match else "Not provided"

        st.session_state.history.append(classification)

        # ---------- RECOMMENDATIONS ----------
        if classification == "Fraud":
            recommendation = "⚠️ Do not click suspicious links or share personal info. Report this to authorities."
        elif classification == "Spam":
            recommendation = "🚫 Avoid replying or engaging with spam content. Block the sender if possible."
        else:
            recommendation = "✅ Message seems safe. Always double-check unknown sources."

        # ---------- SAVE TO DATABASE AND CSV ----------
        save_analysis(input_type, extracted_text, classification, confidence, reason, recommendation)
        save_to_csv(input_type, extracted_text, classification, confidence, reason, recommendation)

        # ---------- DISPLAY RESULTS ----------
        st.divider()
        st.subheader("🤖 AI Result")

        col1, col2 = st.columns(2)
        with col1:
            st.write(result)
            st.progress(confidence / 100)
        with col2:
            st.metric("Confidence Score", f"{confidence}%")
            if confidence >= 80:
                st.error("🔴 High Risk Fraud")
            elif confidence >= 50:
                st.warning("🟡 Medium Risk")
            else:
                st.success("🟢 Low Risk / Legit")

        st.info(f"💡 **Recommendation:** {recommendation}")

    # ---------- HISTORY VIEW ----------
    st.divider()
    st.subheader("📚 Analysis History (from Database)")
    conn = sqlite3.connect("fraud_detection.db")
    try:
        data = conn.execute("SELECT id, input_type, classification, confidence, recommendation, timestamp FROM analysis ORDER BY id DESC").fetchall()
        st.dataframe(data, use_container_width=True)
    except Exception as e:
        st.error(f"Database error: {e}")
    conn.close()

    # ---------- DOWNLOAD CSV BUTTON ----------
    st.subheader("📦 Export Data")
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "rb") as f:
            st.download_button("⬇️ Download CSV Data", f, file_name="fraud_detection_data.csv", mime="text/csv")

else:

    st.warning("🔒 Please log in from the sidebar to access the Fraud Detection Dashboard.")
