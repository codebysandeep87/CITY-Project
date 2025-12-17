import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# =============================
# PAGE CONFIG (Real Company Style)
# =============================
st.set_page_config(
    page_title="Anu Solutions | Enterprise Dashboard",
    page_icon="🏢",
    layout="wide"
)

# =============================
# COMPANY THEME HEADER
# =============================
st.markdown(
    """
    <style>
    .main-title {
        font-size: 36px;
        font-weight: 700;
        color: #1f4e79;
    }
    .sub-title {
        font-size: 18px;
        color: gray;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =============================
# INITIAL ENTERPRISE DATA
# =============================
if "employees" not in st.session_state:
    st.session_state.employees = pd.DataFrame({
        "Employee ID": [1001, 1002, 1003, 1004, 1005],
        "Name": ["Ravi Kumar", "Anjali Sharma", "Suresh Reddy", "Meena Patel", "Arjun Singh"],
        "Department": ["IT", "HR", "Finance", "IT", "Marketing"],
        "Role": ["Software Engineer", "HR Manager", "Accountant", "QA Engineer", "Marketing Executive"],
        "Salary": [75000, 65000, 60000, 55000, 50000],
        "Date Joined": ["2021-06-01", "2020-08-15", "2019-03-10", "2022-01-05", "2023-07-12"]
    })

# =============================
# SIDEBAR (Corporate Navigation)
# =============================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
st.sidebar.title("Anu Solutions")
st.sidebar.caption("Enterprise HR Dashboard")

menu = st.sidebar.radio(
    "Menu",
    [
        "Executive Summary",
        "Company Overview",
        "Departments",
        "Employee Management",
        "Compensation Analytics",
        "Add Employee"
    ]
)

# =============================
# EXECUTIVE SUMMARY (CEO VIEW)
# =============================
if menu == "Executive Summary":
    st.markdown('<div class="main-title">Executive Summary</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">High-level business insights</div>', unsafe_allow_html=True)

    total_emp = len(st.session_state.employees)
    avg_salary = int(st.session_state.employees["Salary"].mean())
    dept_count = st.session_state.employees["Department"].nunique()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Employees", total_emp)
    col2.metric("Average Salary", f"₹ {avg_salary}")
    col3.metric("Departments", dept_count)

    st.divider()

    dept_data = st.session_state.employees["Department"].value_counts()
    fig, ax = plt.subplots()
    ax.pie(dept_data, labels=dept_data.index, autopct="%1.1f%%")
    ax.set_title("Workforce Distribution")
    st.pyplot(fig)

# =============================
# COMPANY OVERVIEW
# =============================
elif menu == "Company Overview":
    st.markdown('<div class="main-title">About Anu Solutions</div>', unsafe_allow_html=True)

    st.write(
        """
        **Anu Solutions** is a mid-scale enterprise delivering IT services,
        HR consulting, finance operations, and digital marketing solutions.

        **Mission:** Deliver reliable, scalable, and secure solutions.
        
        **Vision:** Become a trusted global technology partner.
        """
    )

# =============================
# DEPARTMENTS VIEW
# =============================
elif menu == "Departments":
    st.markdown('<div class="main-title">Department Analytics</div>', unsafe_allow_html=True)

    dept_summary = st.session_state.employees.groupby("Department").agg({
        "Employee ID": "count",
        "Salary": "mean"
    }).rename(columns={"Employee ID": "Employee Count", "Salary": "Avg Salary"})

    st.dataframe(dept_summary)

    fig, ax = plt.subplots()
    ax.bar(dept_summary.index, dept_summary["Employee Count"])
    ax.set_ylabel("Employees")
    ax.set_title("Employees by Department")
    st.pyplot(fig)

# =============================
# EMPLOYEE MANAGEMENT (HR VIEW)
# =============================
elif menu == "Employee Management":
    st.markdown('<div class="main-title">Employee Directory</div>', unsafe_allow_html=True)

    search = st.text_input("Search Employee (Name / Department)")
    df = st.session_state.employees

    if search:
        df = df[df.apply(lambda row: search.lower() in row.astype(str).str.lower().to_string(), axis=1)]

    st.dataframe(df)

# =============================
# COMPENSATION ANALYTICS (FINANCE VIEW)
# =============================
elif menu == "Compensation Analytics":
    st.markdown('<div class="main-title">Salary & Compensation</div>', unsafe_allow_html=True)

    role_salary = st.session_state.employees.groupby("Role")["Salary"].mean().sort_values(ascending=False)

    st.dataframe(role_salary.reset_index(name="Average Salary"))

    fig, ax = plt.subplots()
    ax.barh(role_salary.index, role_salary.values)
    ax.set_xlabel("Salary (INR)")
    ax.set_title("Average Salary by Role")
    st.pyplot(fig)

# =============================
# ADD EMPLOYEE (DATA ENTRY FORM)
# =============================
elif menu == "Add Employee":
    st.markdown('<div class="main-title">Add New Employee</div>', unsafe_allow_html=True)

    with st.form("add_employee_form"):
        emp_id = st.number_input("Employee ID", min_value=1000, step=1)
        name = st.text_input("Full Name")
        department = st.selectbox("Department", ["IT", "HR", "Finance", "Marketing", "Operations"])
        role = st.text_input("Role")
        salary = st.number_input("Salary (INR)", min_value=0, step=1000)
        date_joined = st.date_input("Date Joined", datetime.today())

        submit = st.form_submit_button("Add Employee")

    if submit:
        new_row = pd.DataFrame({
            "Employee ID": [emp_id],
            "Name": [name],
            "Department": [department],
            "Role": [role],
            "Salary": [salary],
            "Date Joined": [str(date_joined)]
        })

        st.session_state.employees = pd.concat(
            [st.session_state.employees, new_row], ignore_index=True
        )

        st.success("Employee record added successfully")
        st.info("All dashboards and analytics have been updated in real time")
