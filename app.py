import streamlit as st
import sqlite3
import hashlib
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap

# -------------------- DATABASE SETUP --------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT,
    password TEXT
)
""")
conn.commit()

# -------------------- PASSWORD HASH --------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------- USER FUNCTIONS --------------------
def add_user(username, password):
    c.execute("INSERT INTO users VALUES (?, ?)", (username, hash_password(password)))
    conn.commit()

def login_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", 
              (username, hash_password(password)))
    return c.fetchone()

# -------------------- SESSION --------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# -------------------- UI DESIGN --------------------
st.set_page_config(page_title="Shade Locator ULTRA", layout="wide")

st.markdown("""
<style>
.big-title {
    font-size:40px;
    font-weight:bold;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)

# -------------------- LOGIN SYSTEM --------------------
if not st.session_state.logged_in:

    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)

    menu = ["Login", "Signup"]
    choice = st.radio("Select Option", menu)

    if choice == "Signup":
        st.subheader("Create Account")

        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type='password')

        if st.button("Signup"):
            add_user(new_user, new_pass)
            st.success("Account created! Now login.")

    elif choice == "Login":
        st.subheader("Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type='password')

        if st.button("Login"):
            result = login_user(username, password)

            if result:
                st.session_state.logged_in = True
                st.success(f"Welcome {username} 🎉")
                st.rerun()
            else:
                st.error("Invalid credentials")

# -------------------- MAIN APP --------------------
else:
    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.subheader("🗺️ Live Shade Map")

    # Default location (Bangalore)
    center_lat = 12.9716
    center_lon = 77.5946

    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # Dummy Shade Locations
    locations = [
        ("Park Area", 12.9716, 77.5946, 80),
        ("Bus Stop Shade", 12.9616, 77.5846, 60),
        ("Mall Entrance", 12.9816, 77.6046, 90),
        ("Tree Cluster", 12.9916, 77.6146, 70)
    ]

    heat_data = []

    for name, lat, lon, intensity in locations:
        folium.Marker(
            [lat, lon],
            popup=f"{name} | Shade: {intensity}%",
            icon=folium.Icon(color="green")
        ).add_to(m)

        heat_data.append([lat, lon, intensity / 100])

    # Heatmap
    HeatMap(heat_data).add_to(m)

    # Display map
    st_folium(m, width=1000, height=500)

    st.success("✅ Live shade + heatmap loaded")

    st.info("🚀 Next upgrade: GPS tracking + real navigation")
