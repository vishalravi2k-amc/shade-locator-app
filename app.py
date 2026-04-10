import streamlit as st
import sqlite3
import hashlib
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
from datetime import datetime

# -------------------- DATABASE SETUP --------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    spot_name TEXT,
    date TEXT,
    time_slot TEXT,
    booked_at TEXT
)
""")
conn.commit()

# -------------------- PASSWORD HASH --------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------- USER FUNCTIONS --------------------
def add_user(username, password):
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?",
              (username, hash_password(password)))
    return c.fetchone()

# -------------------- BOOKING FUNCTIONS --------------------
def book_spot(username, spot_name, date, time_slot):
    booked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO bookings (username, spot_name, date, time_slot, booked_at) VALUES (?, ?, ?, ?, ?)",
        (username, spot_name, date, time_slot, booked_at)
    )
    conn.commit()

def get_user_bookings(username):
    c.execute("SELECT spot_name, date, time_slot, booked_at FROM bookings WHERE username=? ORDER BY booked_at DESC", (username,))
    return c.fetchall()

def is_slot_taken(spot_name, date, time_slot):
    c.execute(
        "SELECT COUNT(*) FROM bookings WHERE spot_name=? AND date=? AND time_slot=?",
        (spot_name, date, time_slot)
    )
    return c.fetchone()[0] > 0

def cancel_booking(username, spot_name, date, time_slot):
    c.execute(
        "DELETE FROM bookings WHERE username=? AND spot_name=? AND date=? AND time_slot=? AND id IN (SELECT id FROM bookings WHERE username=? AND spot_name=? AND date=? AND time_slot=? LIMIT 1)",
        (username, spot_name, date, time_slot, username, spot_name, date, time_slot)
    )
    conn.commit()

# -------------------- SHADE SPOTS DATA --------------------
SHADE_SPOTS = [
    {"name": "Cubbon Park Shade Zone",      "lat": 12.9763, "lon": 77.5929, "intensity": 90, "capacity": 10},
    {"name": "Lalbagh Tree Cluster",        "lat": 12.9507, "lon": 77.5848, "intensity": 85, "capacity": 8},
    {"name": "MG Road Bus Stop Shelter",    "lat": 12.9754, "lon": 77.6069, "intensity": 60, "capacity": 5},
    {"name": "Indiranagar Park Canopy",     "lat": 12.9784, "lon": 77.6408, "intensity": 75, "capacity": 6},
    {"name": "Koramangala Mall Entrance",   "lat": 12.9352, "lon": 77.6245, "intensity": 70, "capacity": 4},
    {"name": "Bannerghatta Road Tree Line", "lat": 12.8938, "lon": 77.5974, "intensity": 80, "capacity": 7},
]

TIME_SLOTS = ["6:00 AM", "8:00 AM", "10:00 AM", "12:00 PM", "2:00 PM", "4:00 PM", "6:00 PM"]

# -------------------- SESSION --------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Shade Locator ULTRA", layout="wide")
st.markdown("""
<style>
.big-title { font-size:38px; font-weight:bold; text-align:center; margin-bottom: 10px; }
.spot-card {
    background: #1e2a1e;
    border-left: 4px solid #4caf50;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.booking-row {
    background: #1a2433;
    border-left: 4px solid #2196f3;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

# -------------------- LOGIN SYSTEM --------------------
if not st.session_state.logged_in:
    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray;'>Find & book shaded spots around Bangalore</p>", unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        choice = st.radio("", ["Login", "Sign Up"], horizontal=True)

        if choice == "Sign Up":
            st.subheader("Create Account")
            new_user = st.text_input("Choose a Username")
            new_pass = st.text_input("Choose a Password", type='password')
            if st.button("Create Account", use_container_width=True):
                if new_user and new_pass:
                    if add_user(new_user, new_pass):
                        st.success("Account created! Please log in.")
                    else:
                        st.error("Username already taken. Try another.")
                else:
                    st.warning("Please fill in both fields.")

        else:
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            if st.button("Login", use_container_width=True):
                result = login_user(username, password)
                if result:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(f"Welcome back, {username}! 🎉")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

# -------------------- MAIN APP --------------------
else:
    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)

    col_title, col_logout = st.columns([5, 1])
    with col_logout:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()
    with col_title:
        st.markdown(f"<p style='color:#aaa;'>Logged in as <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["🗺️ Shade Map", "📋 Book a Spot", "🎫 My Bookings"])

    with tab1:
        st.subheader("Live Shade Map — Bangalore")
        m = folium.Map(location=[12.9716, 77.5946], zoom_start=12)

        heat_data = []
        for spot in SHADE_SPOTS:
            shade_color = "green" if spot["intensity"] >= 75 else "orange" if spot["intensity"] >= 50 else "red"
            folium.Marker(
                [spot["lat"], spot["lon"]],
                popup=folium.Popup(
                    f"<b>{spot['name']}</b><br>Shade: {spot['intensity']}%<br>Capacity: {spot['capacity']} slots",
                    max_width=200
                ),
                icon=folium.Icon(color=shade_color, icon="tree-deciduous", prefix="glyphicon")
            ).add_to(m)
            heat_data.append([spot["lat"], spot["lon"], spot["intensity"] / 100])

        HeatMap(heat_data, radius=40, blur=25).add_to(m)
        st_folium(m, width=None, height=480)

        st.success("✅ Live shade + heatmap loaded")
        st.markdown("**Legend:** 🟢 High shade (≥75%) &nbsp; 🟠 Medium (50–74%) &nbsp; 🔴 Low (<50%)")

    with tab2:
        st.subheader("📋 Book a Shaded Spot")

        col_a, col_b = st.columns(2)
        with col_a:
            spot_names = [s["name"] for s in SHADE_SPOTS]
            selected_spot = st.selectbox("Choose a Shade Spot", spot_names)

        with col_b:
            selected_date = st.date_input("Choose Date", min_value=datetime.today().date())

        spot_info = next(s for s in SHADE_SPOTS if s["name"] == selected_spot)
        st.markdown(f"""
        <div class="spot-card">
            🌿 <b>{spot_info['name']}</b><br>
            ☀️ Shade Level: <b>{spot_info['intensity']}%</b> &nbsp;|&nbsp;
            👥 Capacity: <b>{spot_info['capacity']} slots per time</b>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Select a Time Slot:**")
        available_slots = []
        taken_slots = []
        for slot in TIME_SLOTS:
            if is_slot_taken(selected_spot, str(selected_date), slot):
                taken_slots.append(slot)
            else:
                available_slots.append(slot)

        if available_slots:
            selected_slot = st.radio("Available slots", available_slots, horizontal=True)
        else:
            st.warning("⚠️ All slots are taken for this spot on this date. Please choose another day or spot.")
            selected_slot = None

        if taken_slots:
            st.markdown(f"<span style='color:#888;font-size:13px;'>Already booked: {', '.join(taken_slots)}</span>", unsafe_allow_html=True)

        st.divider()
        if selected_slot:
            if st.button("✅ Confirm Booking", use_container_width=True, type="primary"):
                if is_slot_taken(selected_spot, str(selected_date), selected_slot):
                    st.error("This slot was just booked by someone else. Please pick another.")
                else:
                    book_spot(st.session_state.username, selected_spot, str(selected_date), selected_slot)
                    st.success(f"🎉 Booked **{selected_spot}** on **{selected_date}** at **{selected_slot}**!")
                    st.balloons()

    with tab3:
        st.subheader(f"🎫 My Bookings — {st.session_state.username}")

        bookings = get_user_bookings(st.session_state.username)

        if not bookings:
            st.info("You haven't booked any shade spots yet. Go to the **Book a Spot** tab to get started!")
        else:
            st.markdown(f"**Total bookings: {len(bookings)}**")
            st.divider()

            for b in bookings:
                spot_name, date, time_slot, booked_at = b
                col_info, col_cancel = st.columns([4, 1])
                with col_info:
                    st.markdown(f"""
                    <div class="booking-row">
                        🌿 <b>{spot_name}</b><br>
                        📅 {date} &nbsp;|&nbsp; ⏰ {time_slot}<br>
                        <span style='color:#666;font-size:12px;'>Booked at {booked_at}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with col_cancel:
                    st.write("")
                    st.write("")
                    if st.button("❌ Cancel", key=f"cancel_{spot_name}_{date}_{time_slot}"):
                        cancel_booking(st.session_state.username, spot_name, date, time_slot)
                        st.success("Booking cancelled.")
                        st.rerun()

    st.divider()
    st.info("🚀 Next upgrade: GPS tracking + real-time shade detection via satellite")
```

Just select all, copy, and paste it into your `app.py`. Replace the entire file contents with this.
