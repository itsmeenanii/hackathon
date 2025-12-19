import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import sqlite3

# -----------------------------
# App config
# -----------------------------
st.set_page_config(page_title="Parent-Child Education Analytics", layout="wide")
st.title("👨‍👩‍👧 Parent-Child Education Analytics Dashboard")

# -----------------------------
# Demo authentication
# -----------------------------
with st.sidebar:
    st.header("🔐 Login")
    username = st.text_input("Parent username", value="")
    password = st.text_input("Password", type="password", value="")
    login = st.button("Login")

if not (username == "parent" and password == "1234"):
    #st.info("Use demo credentials → username: parent, password: 1234")
    st.stop()
st.success("✅ Logged in successfully")

# -----------------------------
# Child profiles
# -----------------------------
children = ["Baala", "Mounika", "Varshitha"]
selected_child = st.selectbox("Select child profile", children, index=0)

# -----------------------------
# Apps & categories
# -----------------------------
apps = ["YouTube", "Google Classroom", "WhatsApp", "VS-Code", "Instagram", "MS Teams"]
categories = {
    "YouTube": "Non-Educational",
    "Google Classroom": "Educational",
    "WhatsApp": "Non-Educational",
    "VS-Code": "Educational",
    "Instagram": "Non-Educational",
    "MS Teams": "Educational",
}
app_baselines = {
    "YouTube": (80, 30),
    "Google Classroom": (70, 25),
    "WhatsApp": (60, 20),
    "VS-Code": (65, 25),
    "Instagram": (75, 30),
    "MS Teams": (60, 20),
}

# -----------------------------
# Database setup
# -----------------------------
conn = sqlite3.connect("child_usage.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS usage_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child TEXT,
    date TEXT,
    app TEXT,
    category TEXT,
    usage_minutes INTEGER
)
""")
conn.commit()

# Seed initial data if child has no records
cursor.execute("SELECT COUNT(*) FROM usage_data WHERE child=?", (selected_child,))
if cursor.fetchone()[0] == 0:
    np.random.seed(abs(hash(selected_child)) % (2**32))
    for day in pd.date_range(start="2025-12-13", periods=7):
        for app in apps:
            base, spread = app_baselines[app]
            usage = max(0, int(np.random.normal(loc=base, scale=spread)))
            usage = int(np.clip(usage, 20, 180))
            cursor.execute("""
                INSERT INTO usage_data (child, date, app, category, usage_minutes)
                VALUES (?, ?, ?, ?, ?)
            """, (selected_child, str(day.date()), app, categories[app], usage))
    conn.commit()

# -----------------------------
# Fetch data
# -----------------------------
df = pd.read_sql_query("SELECT * FROM usage_data WHERE child=?", conn, params=(selected_child,))
df["Date"] = pd.to_datetime(df["date"])

# -----------------------------
# Sidebar filters
# -----------------------------
with st.sidebar:
    st.header("Filters")
    day_options = ["All days"] + list(df["Date"].dt.strftime("%Y-%m-%d").unique())
    selected_day = st.selectbox("Select day", options=day_options, index=0)
    selected_apps = st.multiselect("Select apps", options=apps, default=apps)
    st.header("🚨 Alerts thresholds")
    daily_limit = st.slider("Daily per app limit (minutes)", min_value=20, max_value=240, value=120, step=10)
    weekly_limit = st.slider("Weekly per app limit (minutes)", min_value=150, max_value=1200, value=600, step=50)

# Apply filters
filtered_df = df[df["app"].isin(selected_apps)].copy()
if selected_day != "All days":
    filtered_df = filtered_df[filtered_df["Date"].dt.strftime("%Y-%m-%d") == selected_day]

# -----------------------------
# Healthy balance score
# -----------------------------
total_study = filtered_df[filtered_df["category"] == "Educational"]["usage_minutes"].sum()
total_distract = filtered_df[filtered_df["category"] == "Non-Educational"]["usage_minutes"].sum()
total_all = total_study + total_distract
balance_ratio = (total_study / total_all) if total_all > 0 else 0
healthy_balance_score = int(balance_ratio * 100)

# -----------------------------
# Metrics
# -----------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Study minutes", f"{total_study}")
col2.metric("Distraction minutes", f"{total_distract}")
col3.metric("Total minutes", f"{total_all}")
col4.metric("Healthy balance score", f"{healthy_balance_score}/100")
st.divider()

# -----------------------------
# Visualizations
# -----------------------------
left, right = st.columns([1,1])
with left:
    st.subheader("Study vs Distraction Trend")
    if selected_day == "All days":
        daily_usage = filtered_df.groupby(["Date", "category"])["usage_minutes"].sum().unstack().fillna(0)
        fig1, ax1 = plt.subplots(figsize=(7,4))
        daily_usage.plot(kind="bar", stacked=True, ax=ax1, color=["#66b3ff", "#ff9999"])
        ax1.set_title("Daily study vs distraction")
        ax1.set_ylabel("Minutes")
        ax1.legend(["Educational", "Non-Educational"])
        st.pyplot(fig1)
    else:
        category_usage = filtered_df.groupby("category")["usage_minutes"].sum().reindex(["Educational", "Non-Educational"]).fillna(0)
        fig2, ax2 = plt.subplots(figsize=(5,5))
        ax2.pie(category_usage, labels=category_usage.index, autopct="%1.1f%%", colors=["#66b3ff","#ff9999"], startangle=90)
        ax2.set_title(f"Study vs distraction on {selected_day}")
        st.pyplot(fig2)

with right:
    st.subheader("App usage totals")
    weekly_usage = filtered_df.groupby("app")["usage_minutes"].sum().reindex(selected_apps).fillna(0)
    fig3, ax3 = plt.subplots(figsize=(7,4))
    colors = ["#ff9999" if categories[a]=="Non-Educational" else "#66b3ff" for a in weekly_usage.index]
    ax3.bar(weekly_usage.index, weekly_usage.values, color=colors)
    ax3.set_title("App usage")
    ax3.set_ylabel("Minutes")
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig3)

st.divider()

# -----------------------------
# Alerts
# -----------------------------
st.subheader("Alerts")
alerts_count = 0

# Daily alerts
if selected_day != "All days":
    per_day = filtered_df.groupby(["Date","app"])["usage_minutes"].sum()
    for (date, app), minutes in per_day.items():
        if minutes > daily_limit:
            st.error(f"{app} exceeded {daily_limit} mins on {date.strftime('%Y-%m-%d')} (used {minutes} mins)")
            alerts_count +=1

# Weekly alerts
for app in weekly_usage.index:
    minutes = int(weekly_usage[app])
    if minutes > weekly_limit:
        st.error(f"{app} exceeded weekly limit of {weekly_limit} mins (used {minutes} mins)")
        alerts_count += 1

if alerts_count == 0:
    st.success("No alerts. Usage within healthy limits.")
st.divider()

# -----------------------------
# Forecasts (linear regression)
# -----------------------------
st.subheader("🎯 Predictive forecasts")
forecast_app = st.selectbox("Select app to forecast", options=selected_apps, index=0)
app_data = df[(df["child"]==selected_child) & (df["app"]==forecast_app)].sort_values("Date")
app_data["DayIndex"] = range(len(app_data))
X = app_data[["DayIndex"]]
y = app_data["usage_minutes"]

model = LinearRegression()
model.fit(X, y)

future_idx = np.arange(len(app_data), len(app_data)+7).reshape(-1,1)
predictions = model.predict(future_idx)
future_dates = pd.date_range(start=app_data["Date"].max()+pd.Timedelta(days=1), periods=7)

figf, axf = plt.subplots(figsize=(8,4))
axf.plot(app_data["Date"], y, marker="o", label="Actual")
axf.plot(future_dates, predictions, marker="x", linestyle="--", color="red", label="Forecast")
axf.set_title(f"Usage forecast for {forecast_app}")
axf.set_ylabel("Minutes")
axf.legend()
st.pyplot(figf)

avg_forecast = float(np.mean(predictions))
if avg_forecast > daily_limit:
    st.error(f"Projected average for {forecast_app} next week: {avg_forecast:.0f} mins/day (> {daily_limit} limit)")
else:
    st.info(f"Projected average for {forecast_app} next week: {avg_forecast:.0f} mins/day (within limit)")
st.divider()

# -----------------------------
# Adaptive recommendations
# -----------------------------
st.subheader("🎯 Adaptive recommendations")
def suggest_substitution(app_name:str)->str:
    if app_name in ["Instagram","YouTube","WhatsApp"]:
        return "VS-Code"
    return "Google Classroom"

if total_distract > total_study:
    st.warning("Distraction outweighs study time. Recommend fixed study blocks: 2×45 mins daily.")
    st.info("Consider app limits for social apps and a reward system after study blocks.")
elif total_study >= total_distract and total_all >0:
    st.success("Good balance. Maintain consistency with 90-min focused study sessions daily.")

if categories[forecast_app]=="Non-Educational" and avg_forecast > daily_limit:
    alt_app = suggest_substitution(forecast_app)
    st.info(f"Replace 30 mins of {forecast_app} with {alt_app} next week to improve balance.")
elif categories[forecast_app]=="Educational" and avg_forecast >= (daily_limit*0.8):
    st.success(f"{forecast_app} study time looks solid. Encourage spaced repetition or quizzes.")

st.subheader("🎯 Usage Suggestions")
for app in selected_apps:
    minutes = int(weekly_usage.get(app,0))
    if categories[app]=="Non-Educational" and minutes > weekly_limit:
        st.write(f"- {app}: Consider daily cap of {daily_limit} mins and shift 20-30 mins to {suggest_substitution(app)}.")
    elif categories[app]=="Educational" and minutes < 300:
        st.write(f"- {app}: Try adding a 20-min focused session after dinner for steady progress.")
st.divider()

# -----------------------------
# Raw data view & editing
# -----------------------------
st.subheader("Raw usage data (filtered)")
st.dataframe(filtered_df.reset_index(drop=True))

st.subheader("Edit usage data")
editable_df = st.data_editor(filtered_df[["id","app","Date","category","usage_minutes"]], num_rows="dynamic")
if st.button("💾 Save Changes"):
    for _, row in editable_df.iterrows():
        cursor.execute("""
            UPDATE usage_data
            SET usage_minutes=?, category=?
            WHERE id=?
        """, (int(row["usage_minutes"]), row["category"], int(row["id"])))
    conn.commit()
    st.success("Changes saved! Refresh to see updated metrics.")

# -----------------------------
# Add new usage record
# -----------------------------
st.subheader("Add new usage record")
with st.form("add_form"):
    new_date = st.date_input("Date")
    new_app = st.selectbox("App", apps)
    new_usage = st.number_input("Usage minutes", min_value=0, max_value=300, step=10)
    submitted = st.form_submit_button("Add Record")
    if submitted:
        cursor.execute("""
            INSERT INTO usage_data (child, date, app, category, usage_minutes)
            VALUES (?, ?, ?, ?, ?)
        """, (selected_child, str(new_date), new_app, categories[new_app], int(new_usage)))
        conn.commit()
        st.success("New record added successfully!")

# Close DB connection at the end
# conn.close()  # optional if persistent during session