import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Shade Locator ULTRA", layout="wide")

# ---------------- SESSION STATE ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------- USER DATABASE ----------------
users = {
    "vishal": "1234",
    "admin": "admin"
}

# ---------------- LOGIN FUNCTION ----------------
def login():
    st.markdown("<h1 style='text-align: center;'>🌳 Shade Locator ULTRA</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>🔐 Login</h3>", unsafe_allow_html=True)

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", use_container_width=True):
        if username in users and users[username] == password:
            st.session_state.logged_in = True
            st.success("Login successful ✅")
            st.rerun()
        else:
            st.error("Invalid credentials ❌")

# ---------------- MAIN APP ----------------
def main_app():
    st.markdown("<h1 style='text-align: center;'>🌳 Shade Locator ULTRA</h1>", unsafe_allow_html=True)
    st.success("Welcome! You are logged in 🎉")

    st.subheader("🗺️ Live Shade Map")

    # Sample shade locations (you can replace with real DB later)
    locations = [
        ("Park Area", 12.9716, 77.5946, 50),
        ("Bus Stop Shade", 12.9750, 77.5990, 30),
        ("Tree Cluster", 12.9680, 77.5900, 80),
        ("Mall Entrance", 12.9730, 77.6020, 60)
    ]

    # Create map
    m = folium.Map(location=[12.9716, 77.5946], zoom_start=13)

    heat_data = []

    for name, lat, lon, intensity in locations:
        folium.Marker(
            location=[lat, lon],
            popup=f"{name} (Shade: {intensity}%)",
            tooltip=name
        ).add_to(m)

        heat_data.append([lat, lon, intensity])

    # Add heatmap
    HeatMap(heat_data).add_to(m)

    # Display map
    st_folium(m, width=900, height=500)

    # Logout
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# ---------------- APP FLOW ----------------
if not st.session_state.logged_in:
    login()
else:
    main_app()
