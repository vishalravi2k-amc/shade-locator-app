import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import sqlite3
import pandas as pd
from geopy.distance import geodesic
import requests
import streamlit.components.v1 as components
import time

# ---------------- DATABASE ----------------
conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT,
    password TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    lat REAL,
    lon REAL
)''')

conn.commit()

cursor.execute("INSERT OR IGNORE INTO users VALUES ('admin','123')")
conn.commit()

# ---------------- CONFIG ----------------
st.set_page_config(layout="wide")
st.markdown("<h1 style='text-align:center;'>🌳 Shade Locator ULTRA</h1>", unsafe_allow_html=True)

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.subheader("🔐 Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        result = cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (u, p)
        ).fetchone()

        if result:
            st.session_state.user = u
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ---------------- GPS ----------------
def get_gps():
    html = """
    <script>
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const url = new URL(window.location);
            url.searchParams.set("lat", lat);
            url.searchParams.set("lon", lon);
            window.location.href = url.toString();
        }
    );
    </script>
    """
    components.html(html)

params = st.query_params
user_lat = float(params.get("lat", 12.97))
user_lon = float(params.get("lon", 77.59))

# ---------------- SIDEBAR ----------------
menu = st.sidebar.selectbox("Menu", ["Dashboard","Add Location","Explore","Analytics","Logout"])

# ---------------- SEARCH FUNCTION ----------------
def search_location(query):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
    return requests.get(url).json()[:5]

# ---------------- DASHBOARD ----------------
if menu == "Dashboard":
    st.subheader("📊 Dashboard")
    total = cursor.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    st.metric("Total Locations", total)

# ---------------- ADD LOCATION ----------------
elif menu == "Add Location":
    st.subheader("➕ Add Location")

    query = st.text_input("🔍 Search Location")

    lat, lon = None, None
    name = ""
    results = []

    if query:
        results = search_location(query)

        if results:
            options = [r["display_name"] for r in results]
            selected = st.selectbox("Suggestions", options)

            data = next(r for r in results if r["display_name"] == selected)

            lat = float(data["lat"])
            lon = float(data["lon"])
            name = selected

            st.success(name)

    if st.button("Add Location") and lat:
        cursor.execute(
            "INSERT INTO locations (name,lat,lon) VALUES (?,?,?)",
            (name, lat, lon)
        )
        conn.commit()
        st.success("Location Added")

    m = folium.Map(location=[lat or 12.97, lon or 77.59], zoom_start=13)

    if lat:
        folium.Marker([lat, lon], popup="Selected").add_to(m)

    st_folium(m, height=500)

# ---------------- EXPLORE ----------------
elif menu == "Explore":
    st.subheader("🗺️ Smart Map")

    col1, col2 = st.columns([1,2])

    with col1:
        st.button("📍 Detect My Location", on_click=get_gps)
        st.write(f"📍 {user_lat}, {user_lon}")
        auto_refresh = st.checkbox("🔄 Live Tracking")

    data = cursor.execute("SELECT name, lat, lon FROM locations").fetchall()

    m = folium.Map(location=[user_lat, user_lon], zoom_start=13)

    # USER MARKER
    folium.Marker(
        [user_lat, user_lon],
        popup="You",
        icon=folium.Icon(color="blue")
    ).add_to(m)

    heat_data = []
    nearest = None
    min_dist = 9999

    for name, lat, lon in data:
        heat_data.append([lat, lon])

        dist = geodesic((user_lat, user_lon), (lat, lon)).km

        if dist < min_dist:
            min_dist = dist
            nearest = (name, lat, lon)

        folium.Marker([lat, lon], popup=name).add_to(m)

    # HEATMAP
    if heat_data:
        HeatMap(heat_data).add_to(m)

    # NEAREST + ROUTE
    if nearest:
        st.success(f"🧭 Nearest: {nearest[0]} ({min_dist:.2f} km)")

        folium.Marker(
            [nearest[1], nearest[2]],
            popup="Nearest",
            icon=folium.Icon(color="green")
        ).add_to(m)

        folium.PolyLine(
            [(user_lat, user_lon), (nearest[1], nearest[2])],
            color="blue",
            weight=4
        ).add_to(m)

        # GOOGLE MAPS NAVIGATION
        nav_url = f"https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lon}&destination={nearest[1]},{nearest[2]}"
        st.markdown(f"[🚗 Navigate using Google Maps]({nav_url})")

    with col2:
        st_folium(m, height=600)

    # LIVE TRACKING
    if auto_refresh:
        time.sleep(5)
        st.rerun()

# ---------------- ANALYTICS ----------------
elif menu == "Analytics":
    st.subheader("📊 Analytics")

    df = pd.read_sql_query("SELECT * FROM locations", conn)

    st.metric("Total Locations", len(df))

    if not df.empty:
        st.map(df.rename(columns={"lat":"latitude","lon":"longitude"}))

# ---------------- LOGOUT ----------------
elif menu == "Logout":
    st.session_state.user = None
    st.rerun()
