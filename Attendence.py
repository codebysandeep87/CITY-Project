import streamlit as st
import pandas as pd
import os
from datetime import date

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="CITY College Attendance System",
    page_icon="📘",
    layout="centered"
)

ATTENDANCE_FILE = "attendance.csv"

# Hardcoded students (RollNo : Password)
STUDENTS = {
    "101": "city101",
    "102": "city102",
    "103": "city103"
}

# ---------------- FUNCTIONS ----------------
def init_csv():
    if not os.path.exists(ATTENDANCE_FILE):
        df = pd.DataFrame(columns=["RollNo", "Date", "Status"])
        df.to_csv(ATTENDANCE_FILE, index=False)

def authenticate(roll, password):
    return roll in STUDENTS and STUDENTS[roll] == password

def mark_attendance(roll, selected_date, status):
    df = pd.read_csv(ATTENDANCE_FILE)

    # Check duplicate entry
    if ((df["RollNo"] == roll) & (df["Date"] == str(selected_date))).any():
        return False

    new_entry = {
        "RollNo": roll,
        "Date": str(selected_date),
        "Status": status
    }

    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
    df.to_csv(ATTENDANCE_FILE, index=False)
    return True

def get_student_attendance(roll):
    df = pd.read_csv(ATTENDANCE_FILE)
    return df[df["RollNo"] == roll]

# ---------------- INIT ----------------
init_csv()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- UI ----------------
st.title("📘 CITY College Attendance Management System")

# ---------- LOGIN PAGE ----------
if not st.session_state.logged_in:
    st.subheader("🔐 Student Login")

    roll = st.text_input("Roll Number")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if authenticate(roll, password):
            st.session_state.logged_in = True
            st.session_state.roll = roll
            st.success("Login successful ✅")
            st.rerun()
        else:
            st.error("Invalid Roll Number or Password ❌")

# ---------- DASHBOARD ----------
else:
    st.success(f"Welcome Student Roll No: {st.session_state.roll}")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📅 Mark Attendance")
        selected_date = st.date_input(
            "Select Date",
            value=date.today(),
            max_value=date.today()
        )

        status = st.radio("Attendance Status", ["Present", "Absent"])

        if st.button("Submit Attendance"):
            success = mark_attendance(
                st.session_state.roll,
                selected_date,
                status
            )

            if success:
                st.success("Attendance marked successfully ✅")
            else:
                st.warning("Attendance already marked for this date ⚠")

    with col2:
        st.subheader("📊 Your Attendance Records")
        student_data = get_student_attendance(st.session_state.roll)
        st.dataframe(student_data, use_container_width=True)

    st.divider()

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.roll = None
        st.rerun()

# ---------------- FOOTER ----------------
st.markdown(
    "<center>© CITY College | Attendance Management System</center>",
    unsafe_allow_html=True
)