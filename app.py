import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import pandas as pd
from geopy.distance import geodesic
import requests
import streamlit.components.v1 as components

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
    type TEXT,
    capacity INTEGER,
    region TEXT,
    lat REAL,
    lon REAL
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY,
    user TEXT,
    location TEXT
)''')

conn.commit()

# ---------------- DEFAULT USER ----------------
cursor.execute("INSERT INTO users VALUES ('admin','123')")
conn.commit()

# ---------------- CONFIG ----------------
st.set_page_config(layout="wide")
st.markdown("<h1 style='text-align:center;'>🌳 Shade Locator PRO</h1>", unsafe_allow_html=True)

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        result = cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()

        if result:
            st.session_state.user = username
            st.success("Logged in")
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ---------------- GPS ----------------
def get_gps():
    gps_html = """
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
    components.html(gps_html)

params = st.query_params
user_lat = float(params.get("lat", 12.97))
user_lon = float(params.get("lon", 77.59))

# ---------------- SIDEBAR ----------------
menu = st.sidebar.selectbox("Menu", ["Dashboard","Add Location","Explore","Analytics","Logout"])

# ---------------- DASHBOARD ----------------
if menu == "Dashboard":
    st.subheader("📊 Dashboard")

    total_locations = cursor.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    total_bookings = cursor.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

    col1, col2 = st.columns(2)

    col1.metric("Total Locations", total_locations)
    col2.metric("Total Bookings", total_bookings)

# ---------------- ADD LOCATION ----------------
elif menu == "Add Location":
    st.subheader("➕ Add Location")

    query = st.text_input("🔍 Search")

    lat, lon = None, None
    name = ""

    if query:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
        results = requests.get(url).json()[:5]

        options = [r["display_name"] for r in results]
        selected = st.selectbox("Suggestions", options)

        data = next(r for r in results if r["display_name"] == selected)

        lat = float(data["lat"])
        lon = float(data["lon"])
        name = selected

    if st.button("Add") and lat:
        cursor.execute(
            "INSERT INTO locations (name,type,capacity,region,lat,lon) VALUES (?,?,?,?,?,?)",
            (name, "Tree", 5, "Central", lat, lon)
        )
        conn.commit()
        st.success("Added")

# ---------------- EXPLORE ----------------
elif menu == "Explore":
    st.subheader("🗺️ Explore")

    st.button("📍 Detect Location", on_click=get_gps)
    st.info(f"Location: {user_lat}, {user_lon}")

    data = cursor.execute("SELECT name, lat, lon FROM locations").fetchall()

    m = folium.Map(location=[user_lat, user_lon], zoom_start=13)

    folium.Marker([user_lat, user_lon], popup="You", icon=folium.Icon(color="blue")).add_to(m)

    nearest = None
    min_dist = 999999

    for name, lat, lon in data:
        dist = geodesic((user_lat, user_lon), (lat, lon)).km

        if dist < min_dist:
            min_dist = dist
            nearest = (name, lat, lon)

        folium.Marker([lat, lon], popup=name).add_to(m)

    if nearest:
        st.success(f"Nearest: {nearest[0]} ({min_dist:.2f} km)")

        folium.Marker(
            [nearest[1], nearest[2]],
            popup="Nearest",
            icon=folium.Icon(color="green")
        ).add_to(m)

        folium.PolyLine(
            [(user_lat, user_lon), (nearest[1], nearest[2])],
            color="blue"
        ).add_to(m)

    st_folium(m, height=600)

# ---------------- ANALYTICS ----------------
elif menu == "Analytics":
    st.subheader("📈 Analytics")

    df = pd.read_sql_query("SELECT location, COUNT(*) as bookings FROM bookings GROUP BY location", conn)

    if not df.empty:
        st.bar_chart(df.set_index("location"))
    else:
        st.warning("No data")

# ---------------- LOGOUT ----------------
elif menu == "Logout":
    st.session_state.user = None
    st.rerun()
